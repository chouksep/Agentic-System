"""Tests for the TriviaQA loader."""
from __future__ import annotations

from benchmarks.runner.datasets.base import EntityIndex
from benchmarks.runner.datasets.triviaqa import (
    TECH_KEYWORDS,
    load_triviaqa,
)


def test_keyword_prefilter_drops_off_topic(wiki_root):
    rows = [
        {"question": "Who founded OpenAI?"},
        {"question": "Which planet is closest to the sun?"},
        {"question": "Who is the CEO of Anthropic?"},
        {"question": "What is the boiling point of water?"},
    ]
    idx = EntityIndex.from_wiki(wiki_root)
    cases = load_triviaqa(entity_index=idx, dataset_iter=iter(rows))
    assert len(cases) == 2
    questions = [c.question for c in cases]
    assert any("OpenAI" in q for q in questions)
    assert any("Anthropic" in q for q in questions)


def test_tech_keywords_includes_core_terms():
    # Quick sanity — these terms must be in the allowlist for our domain.
    assert "openai" in TECH_KEYWORDS
    assert "anthropic" in TECH_KEYWORDS
    assert "claude" in TECH_KEYWORDS


def test_n_max_caps_output(wiki_root):
    rows = [{"question": "Who founded OpenAI?"}] * 30
    idx = EntityIndex.from_wiki(wiki_root)
    cases = load_triviaqa(entity_index=idx, dataset_iter=iter(rows), n_max=7)
    assert len(cases) == 7


def test_verifier_drops_rejected_rows(wiki_root):
    """LLM verifier can veto candidate rows that pass the keyword+entity filters."""
    rows = [
        {"question": "Who founded OpenAI?"},
        {"question": "Give either the year or venue when Jean Claude Killy won gold"},
        {"question": "Who is Sam Altman?"},
    ]
    idx = EntityIndex.from_wiki(wiki_root)
    # Simulate an LLM that rejects the Killy question as an unrelated Claude entity
    def verifier(question: str, entity_key: tuple) -> bool:
        return "Jean Claude" not in question

    cases = load_triviaqa(
        entity_index=idx, dataset_iter=iter(rows), verifier_fn=verifier,
    )
    questions = [c.question for c in cases]
    assert "Who founded OpenAI?" in questions
    assert not any("Jean Claude" in q for q in questions)
