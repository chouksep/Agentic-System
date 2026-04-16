"""Tests for IngestOp — uses mocked LLM client."""
from __future__ import annotations

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from ci_wiki.db import Database
from ci_wiki.models import Source
from ci_wiki.ops.ingest import IngestOp
from ci_wiki.wiki.index import WikiIndex
from ci_wiki.wiki.page import WikiPageIO
from tests.conftest import make_mock_llm, make_wiki_page


OPENAI_CONTENT = """---
name: OpenAI
type: company
founded: 2015
hq: "San Francisco, CA"
funding_stage: private
last_updated: 2026-04-08
sources: [http://example.com]
---
# OpenAI

## Overview
OpenAI is an AI research lab.

## Products & Services
- [[product:gpt-4o]]

## Pricing
GPT-4o costs $5 per 1M input tokens.
<!-- confidence: high | source_count: 1 -->

## Funding & Financials
Raised $10B from Microsoft.

## Leadership
CEO: [[person:sam-altman]]

## Competitive Position
Competes with Anthropic and Google.

## Recent Developments
- 2026-04-08: Released new pricing tier.

## Open Questions
None currently.

## Sources
http://example.com
"""


@pytest.fixture
def ingest_op(test_config, test_db, tmp_wiki_dir, tmp_schema_file):
    page_io = WikiPageIO(tmp_wiki_dir)
    index = WikiIndex(tmp_wiki_dir, page_io)
    mock_llm = MagicMock()

    # Simulate LLM writing a wiki page via the dispatcher
    def fake_complete_with_tools(system, initial_user_message, tools, dispatcher, **kwargs):
        # Simulate write_wiki_page tool call
        from ci_wiki.llm.tools import ToolCall
        dispatcher._write_wiki_page({"slug": "openai", "page_type": "company", "content": OPENAI_CONTENT})
        return "Ingested OpenAI company page.", 2341

    mock_llm.complete_with_tools.side_effect = fake_complete_with_tools

    return IngestOp(
        config=test_config,
        db=test_db,
        llm=mock_llm,
        page_io=page_io,
        index=index,
    )


@pytest.fixture
def pending_source():
    return Source(
        id="abc123",
        uri="http://techcrunch.com/openai-article",
        source_type="url",
        raw_text="OpenAI raised $10B from Microsoft. CEO Sam Altman. GPT-4o priced at $5/1M tokens.",
        status="pending",
    )


def test_ingest_creates_wiki_page(ingest_op, test_db, pending_source, tmp_wiki_dir):
    test_db.upsert_source(pending_source)
    result = ingest_op.run_source(pending_source)

    assert result.error is None or result.error == ""
    assert "openai" in result.pages_created
    assert (tmp_wiki_dir / "companies" / "openai.md").exists()


def test_ingest_marks_source_as_ingested(ingest_op, test_db, pending_source):
    test_db.upsert_source(pending_source)
    ingest_op.run_source(pending_source)
    assert test_db.is_ingested("abc123")


def test_ingest_records_in_db(ingest_op, test_db, pending_source):
    test_db.upsert_source(pending_source)
    result = ingest_op.run_source(pending_source)
    slugs = test_db.get_all_slugs()
    assert "openai" in slugs


def test_ingest_appends_to_log(ingest_op, test_db, pending_source, tmp_wiki_dir):
    test_db.upsert_source(pending_source)
    ingest_op.run_source(pending_source)
    log_path = tmp_wiki_dir / "log.md"
    assert log_path.exists()
    log_content = log_path.read_text()
    assert "Ingest" in log_content


def test_ingest_updates_index(ingest_op, test_db, pending_source, tmp_wiki_dir):
    test_db.upsert_source(pending_source)
    ingest_op.run_source(pending_source)
    index_path = tmp_wiki_dir / "index.md"
    assert index_path.exists()


def test_ingest_handles_llm_error(test_config, test_db, tmp_wiki_dir, tmp_schema_file):
    page_io = WikiPageIO(tmp_wiki_dir)
    index = WikiIndex(tmp_wiki_dir, page_io)
    mock_llm = MagicMock()
    mock_llm.complete_with_tools.side_effect = RuntimeError("API error")

    op = IngestOp(config=test_config, db=test_db, llm=mock_llm, page_io=page_io, index=index)
    source = Source(id="err1", uri="http://bad.com", source_type="url", raw_text="text", status="pending")
    test_db.upsert_source(source)

    result = op.run_source(source)
    assert result.error is not None
    assert "API error" in result.error
