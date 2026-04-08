"""Shared pytest fixtures for ci-wiki tests."""
from __future__ import annotations

import json
import pytest
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

from ci_wiki.config import Config
from ci_wiki.db import Database
from ci_wiki.models import WikiPage
from ci_wiki.wiki.page import WikiPageIO
from ci_wiki.wiki.index import WikiIndex
from ci_wiki.wiki.search import WikiSearch


@pytest.fixture
def tmp_wiki_dir(tmp_path):
    wiki = tmp_path / "wiki"
    for sub in ("companies", "products", "people", "trends"):
        (wiki / sub).mkdir(parents=True)
    (wiki / "index.md").write_text("# Index\n")
    return wiki


@pytest.fixture
def tmp_sources_dir(tmp_path):
    d = tmp_path / "sources"
    d.mkdir()
    return d


@pytest.fixture
def tmp_schema_file(tmp_path):
    schema = tmp_path / "schema" / "wiki_schema.md"
    schema.parent.mkdir()
    schema.write_text("# Wiki Schema\nYou are a competitive intelligence analyst.")
    return schema


@pytest.fixture
def test_db(tmp_path):
    db = Database(":memory:")
    db.connect()
    yield db
    db.close()


@pytest.fixture
def test_config(tmp_path, tmp_wiki_dir, tmp_sources_dir, tmp_schema_file):
    (tmp_path / "data").mkdir(exist_ok=True)
    return Config(
        repo_root=tmp_path,
        wiki_dir=tmp_wiki_dir,
        sources_dir=tmp_sources_dir,
        schema_file=tmp_schema_file,
        db_path=tmp_path / "data" / "test.db",
        anthropic_api_key="test-key",
        model="claude-sonnet-4-6",
    )


@pytest.fixture
def page_io(tmp_wiki_dir):
    return WikiPageIO(tmp_wiki_dir)


def make_wiki_page(wiki_dir, slug, page_type, name, body="## Overview\nTest content."):
    subdir = {"company": "companies", "product": "products", "person": "people", "trend": "trends"}[page_type]
    path = wiki_dir / subdir / f"{slug}.md"
    page = WikiPage(
        path=path,
        slug=slug,
        page_type=page_type,
        frontmatter={
            "name": name,
            "type": page_type,
            "last_updated": "2026-04-08",
            "sources": ["http://example.com"],
        },
        body=body,
        last_updated=datetime(2026, 4, 8),
    )
    io = WikiPageIO(wiki_dir)
    io.write(page)
    return page


def make_mock_llm(tool_sequence: list[dict] | None = None, final_text: str = "Test answer."):
    """Create a mock LLMClient that simulates a tool call sequence.

    tool_sequence: list of {"name": str, "input": dict} tool call specs
    """
    mock_llm = MagicMock()

    if not tool_sequence:
        # Simple end_turn response
        mock_llm.complete_with_tools.return_value = (final_text, 500)
    else:
        mock_llm.complete_with_tools.return_value = (final_text, 1000)

    return mock_llm
