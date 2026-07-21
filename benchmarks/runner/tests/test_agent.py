"""Tests for AgentRunner + record-only TraceDispatcher.

The agent must:
  - capture every tool call in BFCL's {func_name: {param: value}} shape
  - never execute real wiki I/O (dispatcher returns a stub response)
  - surface API errors as AgentRecord(error=...) rather than raising
"""
from __future__ import annotations

import json

import pytest

from benchmarks.runner.agent import (
    AgentRunner,
    TraceDispatcher,
    _build_tool_schemas_subset,
)
from benchmarks.runner.datasets.base import BfclCase
from benchmarks.runner.types import AgentRecord


class _FakeBlock:
    def __init__(self, type_: str, **kw):
        self.type = type_
        for k, v in kw.items():
            setattr(self, k, v)


class _FakeUsage:
    def __init__(self, in_tok: int, out_tok: int):
        self.input_tokens = in_tok
        self.output_tokens = out_tok


class _FakeResponse:
    def __init__(self, content: list, stop_reason: str, usage: _FakeUsage):
        self.content = content
        self.stop_reason = stop_reason
        self.usage = usage


class _FakeAnthropicMessages:
    """Stand-in for anthropic.Anthropic().messages — supports .create()."""
    def __init__(self, scripted: list[_FakeResponse]):
        self._scripted = list(scripted)
        self.calls: list[dict] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if not self._scripted:
            raise RuntimeError("scripted responses exhausted")
        return self._scripted.pop(0)


class _FakeAnthropicClient:
    def __init__(self, scripted):
        self.messages = _FakeAnthropicMessages(scripted)


def _bfcl_case() -> BfclCase:
    return BfclCase(
        id="t1",
        category="simple",
        functions=["read_wiki_page"],
        question="Read the OpenAI page.",
        possible_answer=[{"read_wiki_page": {"slug": ["openai"], "page_type": ["company"]}}],
    )


def test_trace_dispatcher_records_without_executing():
    from benchmarks.runner.agent import ToolCall  # local alias
    disp = TraceDispatcher()
    out = disp.dispatch(ToolCall(id="x", name="write_wiki_page", input={
        "slug": "openai", "page_type": "company", "content": "ANY"
    }))
    assert disp.records == [
        {"write_wiki_page": {"slug": "openai", "page_type": "company", "content": "ANY"}}
    ]
    # Stub response must be valid JSON and indicate stub mode.
    parsed = json.loads(out)
    assert parsed["stub"] is True


def test_agent_runner_captures_one_tool_call():
    case = _bfcl_case()
    # Script: model emits one tool_use block, then ends.
    tool_use = _FakeBlock(
        "tool_use", id="tu1", name="read_wiki_page",
        input={"slug": "openai", "page_type": "company"},
    )
    end_text = _FakeBlock("text", text="done")
    scripted = [
        _FakeResponse([tool_use], stop_reason="tool_use", usage=_FakeUsage(100, 20)),
        _FakeResponse([end_text], stop_reason="end_turn", usage=_FakeUsage(30, 10)),
    ]
    runner = AgentRunner(model_id="claude-sonnet-4-5", anthropic_client=_FakeAnthropicClient(scripted))
    record = runner.run_case(case)
    assert isinstance(record, AgentRecord)
    assert record.error is None
    assert record.calls == [
        {"read_wiki_page": {"slug": "openai", "page_type": "company"}}
    ]
    assert record.tokens_used == 100 + 20 + 30 + 10
    assert record.cost_usd > 0
    assert record.latency_seconds >= 0


def test_agent_runner_records_error_without_raising():
    case = _bfcl_case()

    class _BrokenClient:
        class messages:
            @staticmethod
            def create(**_):
                raise RuntimeError("API exploded")

    runner = AgentRunner(model_id="claude-sonnet-4-5", anthropic_client=_BrokenClient())
    record = runner.run_case(case)
    assert record.calls == []
    assert record.error is not None
    assert "API exploded" in record.error


def test_tool_schemas_subset_includes_only_requested():
    schemas = _build_tool_schemas_subset(["read_wiki_page", "search_wiki"])
    names = [s["name"] for s in schemas]
    assert names == ["read_wiki_page", "search_wiki"]
