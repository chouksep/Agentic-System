from __future__ import annotations

import pytest
from datetime import datetime
from pathlib import Path

from ci_wiki.wiki.search import WikiSearch, _tokenize
from ci_wiki.models import WikiPage


def make_page(slug, page_type, name, body):
    return WikiPage(
        path=Path(f"/wiki/{page_type}s/{slug}.md"),
        slug=slug,
        page_type=page_type,
        frontmatter={"name": name},
        body=body,
        last_updated=datetime(2026, 4, 8),
    )


PAGES = [
    make_page("openai", "company", "OpenAI", "OpenAI develops GPT models for AI research. Pricing starts at $0.01 per 1K tokens."),
    make_page("anthropic", "company", "Anthropic", "Anthropic is an AI safety company building Claude. Focus on alignment research."),
    make_page("gpt-4o", "product", "GPT-4o", "GPT-4o is OpenAI's flagship model with multimodal capabilities and competitive pricing."),
    make_page("claude-3", "product", "Claude 3", "Claude 3 by Anthropic features advanced reasoning and safety properties."),
    make_page("llm-commoditization", "trend", "LLM Commoditization", "LLM pricing is dropping as competition increases among providers."),
    make_page("sam-altman", "person", "Sam Altman", "Sam Altman is the CEO of OpenAI. Previously ran Y Combinator."),
    make_page("dario-amodei", "person", "Dario Amodei", "Dario Amodei is the CEO of Anthropic. Former VP of Research at OpenAI."),
    make_page("mistral", "company", "Mistral", "Mistral AI is a French AI startup offering open-weight models."),
    make_page("google-gemini", "product", "Gemini", "Gemini is Google's multimodal LLM competing with GPT-4o and Claude."),
    make_page("funding-trends", "trend", "AI Funding", "Venture capital investment in AI companies continues to grow."),
]


@pytest.fixture
def search():
    s = WikiSearch(PAGES)
    s.build_index()
    return s


def test_search_returns_relevant_page(search):
    results = search.search("OpenAI pricing", top_k=3)
    slugs = [p.slug for p, _ in results]
    assert "openai" in slugs or "gpt-4o" in slugs


def test_search_empty_wiki():
    s = WikiSearch([])
    results = s.search("anything")
    assert results == []


def test_tokenizer_strips_markdown():
    tokens = _tokenize("## **Bold Header** and `code`")
    assert "bold" in tokens
    assert "header" in tokens
    assert "code" in tokens
    assert "##" not in tokens
    assert "**" not in tokens


def test_bm25_scores_decrease_with_rank(search):
    results = search.search("OpenAI pricing GPT model", top_k=5)
    if len(results) > 1:
        scores = [s for _, s in results]
        assert scores == sorted(scores, reverse=True)


def test_search_irrelevant_query_returns_low_scores(search):
    results = search.search("quantum physics nuclear reactor submarine")
    # All scores should be 0 (no matches) or empty
    assert all(s == 0 for _, s in results) or len(results) == 0


def test_search_person(search):
    results = search.search("CEO OpenAI Sam", top_k=3)
    slugs = [p.slug for p, _ in results]
    assert "sam-altman" in slugs


def test_search_by_company_name(search):
    results = search.search("Anthropic Claude alignment safety", top_k=3)
    slugs = [p.slug for p, _ in results]
    assert "anthropic" in slugs or "claude-3" in slugs


def test_get_snippets_returns_dicts(search):
    snippets = search.get_snippets("OpenAI", top_k=2)
    assert len(snippets) <= 2
    for s in snippets:
        assert "slug" in s
        assert "snippet" in s
        assert "score" in s
