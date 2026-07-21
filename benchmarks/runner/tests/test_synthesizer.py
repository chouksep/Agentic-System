"""Tests for the case synthesizer (simple → multiple/irrelevance variants)."""
from __future__ import annotations

import pytest

from benchmarks.runner.datasets.base import BfclCase
from benchmarks.runner.datasets.synthesizer import (
    ALL_WIKI_FUNCTIONS,
    Synthesizer,
)


def _simple_case(idx: int) -> BfclCase:
    return BfclCase(
        id=f"simple_{idx}",
        category="simple",
        functions=["read_wiki_page"],
        question=f"Read page {idx}.",
        possible_answer=[{"read_wiki_page": {"slug": [f"slug{idx}"], "page_type": ["company"]}}],
    )


def test_to_multiple_pads_distractors():
    synth = Synthesizer(seed=0)
    cases = [_simple_case(i) for i in range(3)]
    out = synth.to_multiple(cases, n_distractors=3)
    assert len(out) == 3
    for case in out:
        assert case.category == "multiple"
        # Original function still present.
        assert "read_wiki_page" in case.functions
        # At least 2 extra distractors added (>= 1 distractor + original = 4 total).
        assert len(case.functions) >= 4
        # All function names are valid wiki tools.
        assert all(f in ALL_WIKI_FUNCTIONS for f in case.functions)


def test_to_multiple_is_deterministic_with_seed():
    cases = [_simple_case(i) for i in range(5)]
    a = Synthesizer(seed=42).to_multiple(cases, n_distractors=2)
    b = Synthesizer(seed=42).to_multiple(cases, n_distractors=2)
    assert [c.functions for c in a] == [c.functions for c in b]


def test_to_irrelevance_returns_empty_answer():
    synth = Synthesizer(seed=0)
    off_topic = ["What is the capital of France?", "How many planets are in the solar system?"]
    out = synth.to_irrelevance(off_topic, tools_subset=["read_wiki_page", "search_wiki"])
    assert len(out) == 2
    for case in out:
        assert case.category == "irrelevance"
        assert case.possible_answer == []
        assert len(case.functions) >= 1
        assert all(f in ALL_WIKI_FUNCTIONS for f in case.functions)


def test_to_multiple_preserves_original_id_with_suffix():
    synth = Synthesizer(seed=0)
    out = synth.to_multiple([_simple_case(7)], n_distractors=1)
    assert out[0].id.startswith("simple_7")
    assert out[0].id != "simple_7"  # synthesized variants get a distinct ID


def test_to_irrelevance_raises_on_empty_tools():
    synth = Synthesizer(seed=0)
    with pytest.raises(ValueError, match="non-empty"):
        synth.to_irrelevance(["q1"], tools_subset=[])
