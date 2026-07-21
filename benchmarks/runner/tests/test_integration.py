"""End-to-end integration test using a MockLLMClient.

Asserts that AgentRunner -> Comparator -> BFCL evaluator handoff works on the
12 committed fixtures, producing an accuracy that matches the mock's intent
(seeded to fail on exactly one case so accuracy = 11/12).
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from benchmarks.runner.agent import AgentRunner
from benchmarks.runner.cache import Cache
from benchmarks.runner.comparator import Comparator
from benchmarks.runner.datasets.fixtures import load_committed_fixtures


class _Block:
    def __init__(self, type_, **kw):
        self.type = type_
        for k, v in kw.items():
            setattr(self, k, v)


class _Usage:
    def __init__(self, i, o):
        self.input_tokens = i
        self.output_tokens = o


class _Resp:
    def __init__(self, content, stop_reason, usage):
        self.content = content
        self.stop_reason = stop_reason
        self.usage = usage


class _MockMessages:
    """Returns the FIRST possible_answer as the model's call, unless this is
    `simple_search_funding` -- for that case, emit a wrong slug to force a fail.
    """
    def __init__(self, cases_by_question):
        self.cases_by_question = cases_by_question
        self.call_count = 0

    def create(self, **kwargs):
        self.call_count += 1
        msgs = kwargs["messages"]
        # If the conversation already contains a tool_result, we have already
        # emitted our tool_use turn -- now wrap up with end_turn so the
        # AgentRunner loop exits and the recorded calls match expectations.
        for m in msgs:
            if m["role"] == "user" and isinstance(m["content"], list):
                if any(b.get("type") == "tool_result" for b in m["content"]):
                    return _Resp(
                        [_Block("text", text="done")],
                        stop_reason="end_turn",
                        usage=_Usage(5, 2),
                    )
        # Identify the case by the user's question text.
        user_text = msgs[0]["content"]
        case = self.cases_by_question.get(user_text)
        if case is None:
            return _Resp(
                [_Block("text", text="no idea")],
                stop_reason="end_turn",
                usage=_Usage(10, 5),
            )
        pa = case.possible_answer
        if not pa:
            # irrelevance case -- abstain.
            return _Resp([_Block("text", text="not applicable")],
                         stop_reason="end_turn", usage=_Usage(10, 5))

        # For parallel cases, emit ALL expected calls in one assistant turn.
        blocks = []
        for idx, ans in enumerate(pa):
            func_name = next(iter(ans))
            input_args = {}
            for k, v in ans[func_name].items():
                if isinstance(v, list):
                    if v and v[0] != "":
                        input_args[k] = v[0]
                else:
                    input_args[k] = v

            # Deliberately wrong slug for one case to assert non-trivial accuracy.
            if case.id == "simple_search_funding":
                input_args = {"query": "totally-wrong-query", "top_k": 5}

            blocks.append(_Block(
                "tool_use", id=f"tu{idx}", name=func_name, input=input_args,
            ))

        return _Resp(blocks, stop_reason="tool_use", usage=_Usage(80, 20))


class _MockClient:
    def __init__(self, cases):
        self.messages = _MockMessages({c.question: c for c in cases})


def test_full_flow_against_12_fixtures(tmp_path, repo_root):
    cases = load_committed_fixtures(repo_root=repo_root)
    mock = _MockClient(cases)

    def factory(model_id):
        return AgentRunner(model_id="claude-sonnet-4-5", anthropic_client=mock)

    cmp = Comparator(cache=Cache(tmp_path / "cache"))
    records = cmp.run_agent_phase(
        models=["mock-model"], cases=cases, agent_factory=factory, max_cost=10.0,
    )
    assert len(records["mock-model"]) == len(cases)

    run_dir = tmp_path / "out"
    run_dir.mkdir()
    results = cmp.run_evaluation_phase(
        repo_root=repo_root, records=records, cases=cases, run_dir=run_dir,
    )
    assert results.cases_evaluated == len(cases)
    [m] = results.models
    # We deliberately broke 1 case (simple_search_funding) -- accuracy < 1.
    assert 0.5 < m.accuracy < 1.0
    # The broken case should appear as invalid in per_case.
    broken = [pc for pc in m.per_case if pc["id"] == "simple_search_funding"]
    assert broken and broken[0]["valid"] is False
