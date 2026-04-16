"""LLM client with agentic tool loop and rate limiting.

Supports two backends selected automatically from configuration:

* **Databricks** (default): routes through Databricks Model Serving using
  WorkspaceClient. Reads ``~/.databrickscfg`` automatically. Requires
  ``DATABRICKS_HOST`` / ``DATABRICKS_TOKEN`` or a valid databrickscfg profile.

* **Anthropic** (direct): uses the Anthropic SDK when ``ANTHROPIC_API_KEY`` is
  set. Calls the Anthropic Messages API natively — no Databricks dependency
  needed for local use.
"""
from __future__ import annotations

import json
import sys
from typing import TYPE_CHECKING

from databricks.sdk import WorkspaceClient

from ci_wiki.config import Config
from ci_wiki.llm.tools import ToolCall, ToolDispatcher
from ci_wiki.utils.ratelimit import RateLimiter

if TYPE_CHECKING:
    import anthropic as _anthropic_t

_ESTIMATE_TOKENS_PER_WORD = 1.3


def _estimate_tokens(text: str) -> int:
    return max(1, int(len(text.split()) * _ESTIMATE_TOKENS_PER_WORD))


def _to_openai_tools(tools: list[dict]) -> list[dict]:
    """Convert Anthropic-style tool schema (input_schema) to OpenAI function format."""
    return [
        {
            "type": "function",
            "function": {
                "name": t["name"],
                "description": t.get("description", ""),
                "parameters": t.get("input_schema", {"type": "object", "properties": {}}),
            },
        }
        for t in tools
    ]


def _extract_system_text(system: str | list[dict]) -> str:
    """Flatten Anthropic system prompt (string or cache-block list) to plain string."""
    if isinstance(system, str):
        return system
    return "\n".join(b.get("text", "") for b in system if b.get("type") == "text")


def _token_count(response: dict) -> int:
    usage = response.get("usage", {}) or {}
    return (usage.get("prompt_tokens") or 0) + (usage.get("completion_tokens") or 0)


def _anthropic_block_to_dict(block) -> dict:
    """Convert an Anthropic SDK ContentBlock to a plain serialisable dict."""
    if block.type == "text":
        return {"type": "text", "text": block.text}
    if block.type == "tool_use":
        return {"type": "tool_use", "id": block.id, "name": block.name, "input": block.input}
    return {"type": block.type}


class LLMClient:
    def __init__(self, config: Config) -> None:
        self._config = config
        self._ws: WorkspaceClient | None = None
        self._anthropic: _anthropic_t.Anthropic | None = None  # lazy — avoids import when using Databricks
        self._rate_limiter = RateLimiter(
            rpm=config.rate_limit_rpm,
            tpm=config.rate_limit_tpm,
        )

    # ------------------------------------------------------------------
    # Backend selection
    # ------------------------------------------------------------------

    @property
    def _use_anthropic(self) -> bool:
        return self._config.use_anthropic

    # ------------------------------------------------------------------
    # Databricks backend
    # ------------------------------------------------------------------

    @property
    def _client(self) -> WorkspaceClient:
        if self._ws is None:
            if self._config.databricks_token:
                # Explicit token override (e.g. from DATABRICKS_TOKEN env var)
                self._ws = WorkspaceClient(
                    host=self._config.databricks_host,
                    token=self._config.databricks_token,
                )
            else:
                # Default credential chain: reads ~/.databrickscfg [DEFAULT] profile.
                # Do NOT pass host — conflicts with cfg-file credential resolution.
                self._ws = WorkspaceClient()
        return self._ws

    def _query(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        max_tokens: int | None = None,
    ) -> dict:
        """POST to the Databricks serving endpoint via api_client.do() — supports full OpenAI payload."""
        body: dict = {
            "messages": messages,
            "max_tokens": max_tokens or self._config.max_tokens,
        }
        if tools:
            body["tools"] = tools
            body["tool_choice"] = "auto"

        path = f"/serving-endpoints/{self._config.model}/invocations"
        return self._client.api_client.do("POST", path=path, body=body)  # type: ignore[return-value]

    # ------------------------------------------------------------------
    # Anthropic backend
    # ------------------------------------------------------------------

    @property
    def _anthropic_client(self) -> _anthropic_t.Anthropic:
        if self._anthropic is None:
            import anthropic as _anthropic_module
            self._anthropic = _anthropic_module.Anthropic(
                api_key=self._config.anthropic_api_key
            )
        return self._anthropic

    def _query_anthropic(
        self,
        system: str,
        messages: list[dict],
        tools: list[dict] | None = None,
        max_tokens: int | None = None,
    ) -> dict:
        """Call the Anthropic Messages API and normalise the response to OpenAI-compatible format."""
        kwargs: dict = {
            "model": self._config.model,
            "max_tokens": max_tokens or self._config.max_tokens,
            "system": system,
            "messages": messages,
        }
        if tools:
            kwargs["tools"] = tools

        response = self._anthropic_client.messages.create(**kwargs)

        # Extract text from the first text block
        text_content = ""
        for block in response.content:
            if block.type == "text":
                text_content = block.text
                break

        # Normalise to OpenAI-compatible dict so single-turn callers need no change
        return {
            "choices": [
                {
                    "message": {"role": "assistant", "content": text_content},
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": response.usage.input_tokens,
                "completion_tokens": response.usage.output_tokens,
            },
        }

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def complete(
        self,
        system: str | list[dict],
        messages: list[dict],
        tools: list[dict] | None = None,
        max_tokens: int | None = None,
        use_thinking: bool = False,
    ) -> dict:
        """Single-turn completion (no tool loop). Returns raw response dict."""
        estimated = _estimate_tokens(str(messages))
        self._rate_limiter.acquire_request(estimated_tokens=estimated)

        system_text = _extract_system_text(system)
        if self._use_anthropic:
            response = self._query_anthropic(
                system_text, messages, tools=tools, max_tokens=max_tokens
            )
        else:
            all_messages = [{"role": "system", "content": system_text}] + messages
            oai_tools = _to_openai_tools(tools) if tools else None
            response = self._query(all_messages, tools=oai_tools, max_tokens=max_tokens)

        self._rate_limiter.record_actual_tokens(estimated, _token_count(response))
        return response

    def complete_with_tools(
        self,
        system: str | list[dict],
        initial_user_message: str,
        tools: list[dict],
        dispatcher: ToolDispatcher,
        max_iterations: int = 10,
        use_thinking: bool = False,
    ) -> tuple[str, int]:
        """Run the agentic tool loop until stop or max_iterations.

        Routes to the Anthropic or Databricks backend depending on configuration.

        Returns:
            (final_text, total_tokens_used)
        """
        if self._use_anthropic:
            return self._complete_with_tools_anthropic(
                system, initial_user_message, tools, dispatcher, max_iterations
            )
        return self._complete_with_tools_databricks(
            system, initial_user_message, tools, dispatcher, max_iterations
        )

    def _complete_with_tools_databricks(
        self,
        system: str | list[dict],
        initial_user_message: str,
        tools: list[dict],
        dispatcher: ToolDispatcher,
        max_iterations: int,
    ) -> tuple[str, int]:
        """Databricks / OpenAI-compatible agentic tool loop."""
        messages: list[dict] = [
            {"role": "system", "content": _extract_system_text(system)},
            {"role": "user", "content": initial_user_message},
        ]
        oai_tools = _to_openai_tools(tools)
        total_tokens = 0
        final_text = ""

        for _ in range(max_iterations):
            estimated = _estimate_tokens(str(messages))
            self._rate_limiter.acquire_request(estimated_tokens=estimated)

            response = self._query(messages, tools=oai_tools)
            total_tokens += _token_count(response)
            self._rate_limiter.record_actual_tokens(estimated, _token_count(response))

            choice = response["choices"][0]
            msg = choice["message"]
            finish_reason = choice.get("finish_reason", "stop")

            text_content = msg.get("content") or ""
            if text_content:
                final_text = text_content

            raw_tool_calls = msg.get("tool_calls") or []

            # Append assistant turn to history
            assistant_msg: dict = {"role": "assistant", "content": text_content}
            if raw_tool_calls:
                assistant_msg["tool_calls"] = raw_tool_calls
            messages.append(assistant_msg)

            if finish_reason == "stop" or not raw_tool_calls:
                break

            # Execute each tool and append results
            for tc in raw_tool_calls:
                tc_id = tc["id"]
                tc_name = tc["function"]["name"]
                tc_args = json.loads(tc["function"]["arguments"])
                result_text = dispatcher.dispatch(ToolCall(id=tc_id, name=tc_name, input=tc_args))
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc_id,
                    "content": result_text,
                })

        return final_text, total_tokens

    def _complete_with_tools_anthropic(
        self,
        system: str | list[dict],
        initial_user_message: str,
        tools: list[dict],
        dispatcher: ToolDispatcher,
        max_iterations: int,
    ) -> tuple[str, int]:
        """Anthropic-native agentic tool loop.

        Uses the Anthropic Messages API directly (no OpenAI shim). Tool
        definitions are already in Anthropic format (``input_schema``) so no
        conversion is needed. Tool results are returned as a ``user`` role
        message with ``tool_result`` content blocks, which is required by the
        Anthropic API.
        """
        system_text = _extract_system_text(system)
        messages: list[dict] = [{"role": "user", "content": initial_user_message}]
        total_tokens = 0
        final_text = ""

        for _ in range(max_iterations):
            estimated = _estimate_tokens(str(messages))
            self._rate_limiter.acquire_request(estimated_tokens=estimated)

            response = self._anthropic_client.messages.create(
                model=self._config.model,
                max_tokens=self._config.max_tokens,
                system=system_text,
                messages=messages,
                tools=tools,
            )

            tokens = response.usage.input_tokens + response.usage.output_tokens
            total_tokens += tokens
            self._rate_limiter.record_actual_tokens(estimated, tokens)

            # Separate text blocks from tool-use blocks
            text_content = ""
            tool_use_blocks = []
            for block in response.content:
                if block.type == "text":
                    text_content = block.text
                    final_text = text_content
                elif block.type == "tool_use":
                    tool_use_blocks.append(block)

            # Append assistant turn as plain dicts (required for subsequent API calls)
            messages.append({
                "role": "assistant",
                "content": [_anthropic_block_to_dict(b) for b in response.content],
            })

            if response.stop_reason == "end_turn" or not tool_use_blocks:
                break

            # Execute tools; all results must be in a single user message (Anthropic requirement)
            tool_results = []
            for block in tool_use_blocks:
                result_text = dispatcher.dispatch(
                    ToolCall(id=block.id, name=block.name, input=block.input)
                )
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result_text,
                })
            messages.append({"role": "user", "content": tool_results})

        return final_text, total_tokens

    def stream_complete(
        self,
        system: str | list[dict],
        messages: list[dict],
    ) -> str:
        """Complete and write output to stdout. Returns full response text."""
        system_text = _extract_system_text(system)
        estimated = _estimate_tokens(str(messages))
        self._rate_limiter.acquire_request(estimated_tokens=estimated)

        if self._use_anthropic:
            response = self._query_anthropic(system_text, messages)
        else:
            all_messages = [{"role": "system", "content": system_text}] + messages
            response = self._query(all_messages)

        self._rate_limiter.record_actual_tokens(estimated, _token_count(response))

        text = response["choices"][0]["message"].get("content") or ""
        sys.stdout.write(text)
        sys.stdout.write("\n")
        sys.stdout.flush()
        return text
