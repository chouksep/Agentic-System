from __future__ import annotations

import pytest
from datetime import datetime
from pathlib import Path

from ci_wiki.wiki.page import WikiPageIO
from ci_wiki.models import WikiPage
from ci_wiki.utils import markdown


@pytest.fixture
def wiki_dir(tmp_path):
    d = tmp_path / "wiki"
    for sub in ("companies", "products", "people", "trends"):
        (d / sub).mkdir(parents=True)
    return d


@pytest.fixture
def page_io(wiki_dir):
    return WikiPageIO(wiki_dir)


def make_page(wiki_dir, slug="openai", page_type="company"):
    path = wiki_dir / "companies" / f"{slug}.md"
    return WikiPage(
        path=path,
        slug=slug,
        page_type=page_type,
        frontmatter={
            "name": "OpenAI",
            "type": "company",
            "founded": 2015,
            "last_updated": "2026-04-08",
            "sources": ["http://example.com"],
        },
        body="# OpenAI\n\n## Overview\nAn AI company.\n",
        last_updated=datetime(2026, 4, 8),
    )


def test_write_then_read_round_trips_frontmatter(page_io, wiki_dir):
    page = make_page(wiki_dir)
    page_io.write(page)

    loaded = page_io.read(page.path)
    assert loaded.slug == "openai"
    assert loaded.page_type == "company"
    assert loaded.frontmatter["name"] == "OpenAI"
    assert loaded.frontmatter["founded"] == 2015
    assert loaded.body.strip().startswith("# OpenAI")


def test_atomic_write_leaves_no_temp_file(page_io, wiki_dir):
    page = make_page(wiki_dir)
    page_io.write(page)
    tmp = page.path.with_suffix(".md.tmp")
    assert not tmp.exists()
    assert page.path.exists()


def test_read_nonexistent_page_raises(page_io, wiki_dir):
    path = wiki_dir / "companies" / "missing.md"
    with pytest.raises(FileNotFoundError):
        page_io.read(path)


def test_slug_to_path_mapping(page_io, wiki_dir):
    path = page_io.slug_to_path("anthropic", "company")
    assert path == wiki_dir / "companies" / "anthropic.md"

    path2 = page_io.slug_to_path("gpt-4o", "product")
    assert path2 == wiki_dir / "products" / "gpt-4o.md"

    path3 = page_io.slug_to_path("sam-altman", "person")
    assert path3 == wiki_dir / "people" / "sam-altman.md"

    path4 = page_io.slug_to_path("llm-commoditization", "trend")
    assert path4 == wiki_dir / "trends" / "llm-commoditization.md"


def test_write_content_creates_page(page_io, wiki_dir):
    content = """---
name: Anthropic
type: company
founded: 2021
last_updated: 2026-04-08
sources: [http://anthropic.com]
---
# Anthropic

## Overview
AI safety company.
"""
    page = page_io.write_content("anthropic", "company", content)
    assert page.slug == "anthropic"
    assert (wiki_dir / "companies" / "anthropic.md").exists()


def test_read_all_returns_all_pages(page_io, wiki_dir):
    page1 = make_page(wiki_dir, "openai", "company")
    page2 = make_page(wiki_dir, "anthropic", "company")
    page2.path = wiki_dir / "companies" / "anthropic.md"
    page_io.write(page1)
    page_io.write(page2)

    all_pages = page_io.read_all()
    slugs = [p.slug for p in all_pages]
    assert "openai" in slugs
    assert "anthropic" in slugs


def test_markdown_parse_dump_roundtrip():
    fm = {
        "name": "OpenAI",
        "founded": 2015,
        "sources": ["http://a.com", "http://b.com"],
        "last_updated": "2026-04-08",
    }
    body = "# OpenAI\n\n## Overview\nSome text.\n"
    text = markdown.dump(fm, body)
    parsed_fm, parsed_body = markdown.parse(text)
    assert parsed_fm["name"] == "OpenAI"
    assert parsed_fm["founded"] == 2015
    assert isinstance(parsed_fm["sources"], list)
    assert len(parsed_fm["sources"]) == 2
    assert parsed_body == body
