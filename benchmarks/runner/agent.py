"""AgentRunner — drives ci_wiki against one BfclCase, captures parameter shapes.

The TraceDispatcher records every tool call in BFCL's {func_name: {param: value}}
shape and returns a deterministic stub response — it never executes real wiki
I/O. This protects the wiki from `write_wiki_page` calls during evaluation;
BFCL's AST checker only scores parameter shapes anyway.

If the model emits multiple tool calls in one assistant turn (parallel category),
each is recorded; the order matches the order the model emitted them.

This module uses the Anthropic SDK directly (not LLMClient) because BFCL mode
needs a tighter loop with per-step block introspection that the existing
agentic loop doesn't expose. Tests inject a fake `anthropic_client`.
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass

from ci_wiki.llm.tools import (
    FLAG_CONTRADICTION,
    LIST_WIKI_PAGES,
    READ_WIKI_PAGE,
    SEARCH_WIKI,
    WRITE_WIKI_PAGE,
)

from benchmarks.runner.datasets.base import BfclCase
from benchmarks.runner.pricing import compute_cost_usd
from benchmarks.runner.types import AgentRecord

log = logging.getLogger(__name__)

# Lookup by canonical tool name → Anthropic-formatted schema (with `input_schema`).
_TOOL_SCHEMAS: dict[str, dict] = {
    "read_wiki_page": READ_WIKI_PAGE,
    "write_wiki_page": WRITE_WIKI_PAGE,
    "search_wiki": SEARCH_WIKI,
    "list_wiki_pages": LIST_WIKI_PAGES,
    "flag_contradiction": FLAG_CONTRADICTION,
}

_SYSTEM_PROMPT = (
    "You are a benchmark agent. Answer the user's question using the available "
    "tools. Emit tool calls with correct parameter shapes; the tool runtime is "
    "stubbed for this evaluation."
)
_MAX_ITERATIONS = 10


@dataclass
class ToolCall:
    """Minimal tool-call shape consumed by TraceDispatcher."""
    id: str
    name: str
    input: dict


class TraceDispatcher:
    """Records calls in BFCL prediction shape; never touches the real wiki."""

    def __init__(self) -> None:
        self.records: list[dict] = []

    def dispatch(self, call: ToolCall) -> str:
        self.records.append({call.name: dict(call.input)})
        return json.dumps({"ok": True, "stub": True, "mode": "bfcl-eval"})


def _build_tool_schemas_subset(function_names: list[str]) -> list[dict]:
    """Return Anthropic-formatted tool schemas for the requested function names."""
    out: list[dict] = []
    for name in function_names:
        if name not in _TOOL_SCHEMAS:
            raise KeyError(f"Unknown function name in case: {name!r}")
        out.append(_TOOL_SCHEMAS[name])
    return out


class AgentRunner:
    """Runs one BFCL case against an Anthropic-style client.

    The client must expose `.messages.create(**kwargs)` returning an object with
    `.content` (list of blocks), `.stop_reason` (str), and `.usage` (object with
    `input_tokens`/`output_tokens`). Real Anthropic SDK satisfies this; tests
    inject a fake.
    """

    def __init__(
        self,
        *,
        model_id: str,
        anthropic_client=None,
        max_tokens: int = 4096,
    ) -> None:
        self._model_id = model_id
        self._max_tokens = max_tokens
        if anthropic_client is None:
            anthropic_client = self._default_anthropic_client()
        self._client = anthropic_client

    @staticmethod
    def _default_anthropic_client():
        # Lazy import so unit tests never reach this path.
        import anthropic
        from ci_wiki.config import Config
        cfg = Config.from_env()
        if not cfg.anthropic_api_key:
            raise RuntimeError(
                "AgentRunner requires ANTHROPIC_API_KEY (loaded by ci_wiki.config). "
                "Either pass `anthropic_client=` explicitly or set the env var."
            )
        # max_retries=3 satisfies the spec's "exponential backoff up to 3
        # retries" requirement; the SDK handles backoff for 429/5xx/timeouts.
        return anthropic.Anthropic(api_key=cfg.anthropic_api_key, max_retries=3)

    def run_case(self, case: BfclCase) -> AgentRecord:
        try:
            tools = _build_tool_schemas_subset(case.functions)
        except KeyError as exc:
            return AgentRecord(error=f"setup_error: {exc}")

        dispatcher = TraceDispatcher()
        messages: list[dict] = [{"role": "user", "content": case.question}]
        total_in = 0
        total_out = 0
        t0 = time.monotonic()
        try:
            for _ in range(_MAX_ITERATIONS):
                resp = self._client.messages.create(
                    model=self._model_id,
                    max_tokens=self._max_tokens,
                    system=_SYSTEM_PROMPT,
                    messages=messages,
                    tools=tools,
                )
                total_in += resp.usage.input_tokens
                total_out += resp.usage.output_tokens

                tool_uses: list = []
                content_dicts: list[dict] = []
                for block in resp.content:
                    btype = block.type
                    if btype == "text":
                        content_dicts.append({"type": "text", "text": block.text})
                    elif btype == "tool_use":
                        tool_uses.append(block)
                        content_dicts.append({
                            "type": "tool_use",
                            "id": block.id,
                            "name": block.name,
                            "input": block.input,
                        })

                messages.append({"role": "assistant", "content": content_dicts})

                if resp.stop_reason == "end_turn" or not tool_uses:
                    break

                # Stub-dispatch each tool_use and append results in one user turn.
                tool_results = []
                for tu in tool_uses:
                    result_text = dispatcher.dispatch(
                        ToolCall(id=tu.id, name=tu.name, input=dict(tu.input))
                    )
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tu.id,
                        "content": result_text,
                    })
                messages.append({"role": "user", "content": tool_results})
        except Exception as exc:  # broad: convert any API failure to AgentRecord
            elapsed = time.monotonic() - t0
            return AgentRecord(
                calls=dispatcher.records,
                tokens_used=total_in + total_out,
                latency_seconds=elapsed,
                cost_usd=self._safe_cost(total_in, total_out),
                error=f"{type(exc).__name__}: {exc}",
            )

        elapsed = time.monotonic() - t0
        return AgentRecord(
            calls=dispatcher.records,
            tokens_used=total_in + total_out,
            latency_seconds=elapsed,
            cost_usd=self._safe_cost(total_in, total_out),
            error=None,
        )

    def _safe_cost(self, input_tokens: int, output_tokens: int) -> float:
        try:
            return compute_cost_usd(
                model_id=self._model_id,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            )
        except KeyError:
            log.warning("no price for model %s — recording cost_usd=0", self._model_id)
            return 0.0
