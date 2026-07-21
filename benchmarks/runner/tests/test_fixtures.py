"""Tests for the fixtures dataset loader (committed BFCL test_cases.json)."""
from __future__ import annotations

from benchmarks.runner.datasets.fixtures import load_committed_fixtures


def test_loads_12_committed_cases(repo_root):
    cases = load_committed_fixtures(repo_root=repo_root)
    assert len(cases) >= 12  # repo currently ships 12; allow growth
    categories = {c.category for c in cases}
    assert categories.issuperset({"simple", "multiple", "parallel"})


def test_committed_cases_have_valid_shape(repo_root):
    cases = load_committed_fixtures(repo_root=repo_root)
    for case in cases:
        assert case.id
        assert case.category
        assert isinstance(case.functions, list) and case.functions
        assert isinstance(case.question, str) and case.question.strip()
        assert isinstance(case.possible_answer, list)
