"""Tests for BfclCase dataclass and EntityIndex.

EntityIndex scans wiki/**/*.md and builds an alias->(slug, page_type) map so
loaders can detect wiki-resolvable entities mentioned in question text.
"""
from __future__ import annotations

from benchmarks.runner.datasets.base import BfclCase, EntityIndex


def test_bfcl_case_round_trip():
    case = BfclCase(
        id="simple_read_openai",
        category="simple",
        functions=["read_wiki_page"],
        question="Read the wiki page for OpenAI.",
        possible_answer=[{"read_wiki_page": {"slug": ["openai"], "page_type": ["company"]}}],
    )
    assert case.id == "simple_read_openai"
    assert case.functions == ["read_wiki_page"]
    assert case.possible_answer[0]["read_wiki_page"]["slug"] == ["openai"]


def test_entity_index_matches_known_companies(wiki_root):
    idx = EntityIndex.from_wiki(wiki_root)
    matches = idx.match("What is OpenAI's funding history?")
    assert ("openai", "company") in matches


def test_entity_index_matches_people(wiki_root):
    idx = EntityIndex.from_wiki(wiki_root)
    matches = idx.match("Who is Dario Amodei?")
    assert ("dario-amodei", "person") in matches


def test_entity_index_matches_products(wiki_root):
    idx = EntityIndex.from_wiki(wiki_root)
    matches = idx.match("Claude is an AI assistant.")
    assert ("claude", "product") in matches


def test_entity_index_returns_empty_for_unknown(wiki_root):
    idx = EntityIndex.from_wiki(wiki_root)
    assert idx.match("Where is Tesla headquartered?") == []


def test_entity_index_multi_match(wiki_root):
    idx = EntityIndex.from_wiki(wiki_root)
    matches = idx.match("Anthropic was founded by Dario Amodei.")
    slugs = {slug for slug, _ in matches}
    assert "anthropic" in slugs
    assert "dario-amodei" in slugs
