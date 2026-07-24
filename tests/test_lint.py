"""Tests for LintOp static checks — no API calls required."""
from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pytest
from unittest.mock import MagicMock

from ci_wiki.models import WikiPage
from ci_wiki.ops.lint import LintOp
from ci_wiki.wiki.index import WikiIndex
from ci_wiki.wiki.page import WikiPageIO
from tests.conftest import make_wiki_page


@pytest.fixture
def lint_wiki(tmp_wiki_dir, test_db):
    """Wiki with known issues for testing."""
    # Good company page
    openai = make_wiki_page(
        tmp_wiki_dir, "openai", "company", "OpenAI",
        (
            "## Overview\nOpenAI builds GPT.\n\n"
            "## Pricing\nGPT-4o $5/1M tokens.\n<!-- confidence: high | source_count: 2 -->\n\n"
            "## Funding & Financials\nRaised $10B.\n\n"
            "## Competitive Position\nLeads LLM market.\n\n"
            "## Recent Developments\n- 2026-04-08: New pricing.\n\n"
            "## Sources\nhttp://example.com\n"
            "Cross-references: [[product:gpt-5]]"  # broken xref!
        )
    )
    test_db.upsert_page(openai)

    # Stale company page
    stale_page = WikiPage(
        path=tmp_wiki_dir / "companies" / "anthropic.md",
        slug="anthropic",
        page_type="company",
        frontmatter={
            "name": "Anthropic",
            "type": "company",
            "last_updated": "2025-01-01",
            "sources": ["http://anthropic.com"],
        },
        body=(
            "## Overview\nAI safety company.\n\n"
            "## Pricing\nClaude API pricing.\n\n"
            "## Funding & Financials\nRaised $4B.\n\n"
            "## Competitive Position\nCompetes with OpenAI.\n"
        ),
        last_updated=datetime(2025, 1, 1),
    )
    WikiPageIO(tmp_wiki_dir).write(stale_page)
    test_db.upsert_page(stale_page)

    # Orphan page (not in DB)
    orphan = WikiPage(
        path=tmp_wiki_dir / "companies" / "mystery-co.md",
        slug="mystery-co",
        page_type="company",
        frontmatter={"name": "Mystery Co", "type": "company", "last_updated": "2026-04-08", "sources": []},
        body="## Overview\nUnknown company.\n",
        last_updated=datetime(2026, 4, 8),
    )
    WikiPageIO(tmp_wiki_dir).write(orphan)
    # Note: NOT added to test_db — this is the orphan

    return tmp_wiki_dir


@pytest.fixture
def lint_op(test_config, test_db, lint_wiki):
    page_io = WikiPageIO(lint_wiki)
    index = WikiIndex(lint_wiki, page_io)
    mock_llm = MagicMock()
    mock_llm.complete_with_tools.return_value = ("No issues found in batch.", 500)
    return LintOp(
        config=test_config,
        db=test_db,
        llm=mock_llm,
        page_io=page_io,
        index=index,
    )


def test_find_broken_xrefs(lint_op):
    issues = lint_op._find_broken_xrefs()
    issue_types = [i.issue_type for i in issues]
    assert "missing_xref" in issue_types
    broken_descs = [i.description for i in issues if i.issue_type == "missing_xref"]
    assert any("gpt-5" in d for d in broken_descs)


def test_find_stale_pages(lint_op):
    issues = lint_op._find_stale_pages()
    stale_slugs = [i.page_slug for i in issues]
    assert "anthropic" in stale_slugs


def test_find_orphaned_pages(lint_op):
    issues = lint_op._find_orphaned_pages()
    orphan_slugs = [i.page_slug for i in issues]
    assert "mystery-co" in orphan_slugs


def test_find_missing_sections(tmp_wiki_dir, test_db, test_config):
    """Company page missing Pricing section should be flagged."""
    incomplete = make_wiki_page(
        tmp_wiki_dir, "incomplete-co", "company", "Incomplete Co",
        "## Overview\nMissing pricing section.\n\n## Funding & Financials\nUnknown.\n"
    )
    test_db.upsert_page(incomplete)
    page_io = WikiPageIO(tmp_wiki_dir)
    index = WikiIndex(tmp_wiki_dir, page_io)
    mock_llm = MagicMock()
    mock_llm.complete_with_tools.return_value = ("", 100)
    op = LintOp(config=test_config, db=test_db, llm=mock_llm, page_io=page_io, index=index)
    issues = op._find_missing_sections()
    missing = [i for i in issues if i.page_slug == "incomplete-co"]
    assert any("Pricing" in i.description for i in missing)


def test_lint_dry_run_does_not_modify_index(lint_op, lint_wiki):
    original_index = (lint_wiki / "index.md").read_text()
    lint_op.run(dry_run=True, llm_check=False)
    current_index = (lint_wiki / "index.md").read_text()
    assert current_index == original_index


def test_lint_full_run_returns_issues(lint_op):
    issues = lint_op.run(llm_check=False)
    assert len(issues) > 0


def test_lint_surfaces_invalid_financials_sidecar(lint_op, lint_wiki):
    """A broken *.financials.yaml sidecar surfaces as an 'invalid_financials_sidecar' LintIssue."""
    bad_sidecar = lint_wiki / "companies" / "bogus.financials.yaml"
    bad_sidecar.write_text(
        "schema_version: 1\nticker: BOGUS\ncik: 42\n"  # cik: int, not 10-digit string
        "metrics: {currency: USD, units: millions, by_period: {}, metadata: {}}\n",
        encoding="utf-8",
    )
    issues = lint_op._find_invalid_financials_sidecars()
    sidecar_issues = [i for i in issues if i.issue_type == "invalid_financials_sidecar"]
    assert sidecar_issues, f"expected an invalid_financials_sidecar issue; got: {issues}"
    assert sidecar_issues[0].page_slug == "bogus"
    assert "cik" in sidecar_issues[0].description.lower()
