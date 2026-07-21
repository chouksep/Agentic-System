"""Tests for the EntityQuestions loader.

Real HF download is exercised only by the opt-in smoke run. Unit tests pass an
in-memory `dataset_iter` of rows that mimic the HF dataset shape:
    {"question": str, "answers": list[str], "entity": str, ...}
"""
from __future__ import annotations

from benchmarks.runner.datasets.base import EntityIndex
from benchmarks.runner.datasets.entity_questions import load_entity_questions


def test_filters_to_wiki_resolvable_entities(wiki_root):
    rows = [
        {"question": "Where was OpenAI founded?", "answers": ["San Francisco"]},
        {"question": "Who founded Anthropic?", "answers": ["Dario Amodei"]},
        {"question": "What is the capital of France?", "answers": ["Paris"]},
        {"question": "Who is Demis Hassabis?", "answers": ["DeepMind CEO"]},
        {"question": "What is the population of Tokyo?", "answers": ["13M"]},
    ]
    idx = EntityIndex.from_wiki(wiki_root)
    cases = load_entity_questions(entity_index=idx, dataset_iter=iter(rows))
    # 3 wiki-resolvable: OpenAI, Anthropic, Demis Hassabis. Tokyo + France not.
    assert len(cases) == 3
    for case in cases:
        assert case.category == "simple"
        assert case.functions == ["read_wiki_page"]
        assert case.possible_answer[0]["read_wiki_page"]["slug"]


def test_n_max_caps_output(wiki_root):
    rows = [{"question": "Who founded Anthropic?"}] * 20
    idx = EntityIndex.from_wiki(wiki_root)
    cases = load_entity_questions(entity_index=idx, dataset_iter=iter(rows), n_max=5)
    assert len(cases) == 5


def test_skips_rows_without_question(wiki_root):
    rows = [
        {"question": "Who founded OpenAI?"},
        {"answers": ["foo"]},  # no question key
        {"question": ""},      # empty question
        {"question": "Who is Sam Altman?"},
    ]
    idx = EntityIndex.from_wiki(wiki_root)
    cases = load_entity_questions(entity_index=idx, dataset_iter=iter(rows))
    assert len(cases) == 2
