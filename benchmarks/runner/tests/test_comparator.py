"""Tests for Comparator.run — multi-model orchestration with cost ceiling."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from benchmarks.runner.cache import Cache
from benchmarks.runner.comparator import Comparator, CostCeilingExceeded
from benchmarks.runner.datasets.base import BfclCase
from benchmarks.runner.types import AgentRecord


def _case(idx: int) -> BfclCase:
    return BfclCase(
        id=f"c{idx}",
        category="simple",
        functions=["read_wiki_page"],
        question=f"Q{idx}",
        possible_answer=[{"read_wiki_page": {"slug": [f"s{idx}"], "page_type": ["company"]}}],
    )


class _StubRunner:
    """Records calls; returns one tool_call per case at fixed cost."""
    def __init__(self, model_id: str, cost_per_call: float = 0.001):
        self.model_id = model_id
        self.cost_per_call = cost_per_call
        self.invocations = 0

    def run_case(self, case: BfclCase) -> AgentRecord:
        self.invocations += 1
        return AgentRecord(
            calls=[{"read_wiki_page": {"slug": f"s{case.id[1:]}", "page_type": "company"}}],
            tokens_used=100,
            latency_seconds=0.1,
            cost_usd=self.cost_per_call,
        )


@pytest.fixture
def stub_factory():
    created: dict[str, _StubRunner] = {}

    def factory(model_id: str) -> _StubRunner:
        created.setdefault(model_id, _StubRunner(model_id))
        return created[model_id]

    factory.created = created  # type: ignore[attr-defined]
    return factory


def test_cache_populated_on_first_run(tmp_cache, stub_factory):
    cmp = Comparator(cache=Cache(tmp_cache))
    cases = [_case(i) for i in range(3)]
    cmp.run_agent_phase(
        models=["mA", "mB"], cases=cases, agent_factory=stub_factory, max_cost=10.0,
    )
    assert stub_factory.created["mA"].invocations == 3
    assert stub_factory.created["mB"].invocations == 3


def test_second_run_hits_cache(tmp_cache, stub_factory):
    cache = Cache(tmp_cache)
    cases = [_case(i) for i in range(3)]
    Comparator(cache=cache).run_agent_phase(
        models=["mA", "mB"], cases=cases, agent_factory=stub_factory, max_cost=10.0,
    )
    # Second factory: invocations should stay at 0 for both models.
    factory2_invoked: dict[str, int] = {}

    def factory2(model_id: str):
        factory2_invoked[model_id] = 0

        class _R:
            def run_case(self, case):
                factory2_invoked[model_id] += 1
                return AgentRecord(calls=[], tokens_used=0, cost_usd=0.0)

        return _R()

    Comparator(cache=cache).run_agent_phase(
        models=["mA", "mB"], cases=cases, agent_factory=factory2, max_cost=10.0,
    )
    assert factory2_invoked == {"mA": 0, "mB": 0}


def test_cost_ceiling_aborts_before_next_call(tmp_cache, stub_factory):
    cmp = Comparator(cache=Cache(tmp_cache))
    cases = [_case(i) for i in range(10)]
    with pytest.raises(CostCeilingExceeded):
        cmp.run_agent_phase(
            models=["mA"],
            cases=cases,
            agent_factory=stub_factory,
            max_cost=0.003,  # at $0.001/call, allows 3 calls then aborts
        )
    runner = stub_factory.created["mA"]
    assert runner.invocations <= 3


def test_emit_predictions_writes_bfcl_shape(tmp_path, tmp_cache, stub_factory):
    cmp = Comparator(cache=Cache(tmp_cache))
    cases = [_case(i) for i in range(2)]
    records = cmp.run_agent_phase(
        models=["mA"], cases=cases, agent_factory=stub_factory, max_cost=10.0,
    )
    pred_path = tmp_path / "preds.json"
    cmp.emit_predictions(records["mA"], pred_path)
    data = json.loads(pred_path.read_text(encoding="utf-8"))
    assert set(data.keys()) == {"c0", "c1"}
    assert isinstance(data["c0"], list)
    assert "read_wiki_page" in data["c0"][0]


def test_emit_test_cases_slice_writes_meta_and_subset(tmp_path, stub_factory):
    cmp = Comparator(cache=Cache(tmp_path / "cache"))
    cases = [_case(i) for i in range(2)]
    slice_path = tmp_path / "tc_slice.json"
    cmp.emit_test_cases_slice(cases, slice_path)
    data = json.loads(slice_path.read_text(encoding="utf-8"))
    assert "_meta" in data
    assert len(data["test_cases"]) == 2
    assert data["test_cases"][0]["id"] == "c0"
