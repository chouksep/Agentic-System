"""Tests for FINANCIALS_TOOLS wiring in ci_wiki.llm.tools."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from ci_wiki.llm.tools import (
    FINANCIALS_TOOLS,
    QUERY_TOOLS,
    INGEST_TOOLS,
    ToolCall,
    ToolDispatcher,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
WIKI_DIR = REPO_ROOT / "wiki"


def _dispatcher() -> ToolDispatcher:
    page_io = MagicMock()
    search = MagicMock()
    return ToolDispatcher(page_io, search, WIKI_DIR)


def test_dispatcher_requires_wiki_dir():
    page_io = MagicMock()
    search = MagicMock()
    with pytest.raises(TypeError):
        ToolDispatcher(page_io, search)  # missing wiki_dir


def test_financials_tools_registered_in_query_and_ingest():
    fin_names = {t["name"] for t in FINANCIALS_TOOLS}
    assert fin_names == {
        "list_companies_with_financials",
        "list_financial_metrics",
        "get_metric_series",
        "get_filing_table",
    }
    query_names = {t["name"] for t in QUERY_TOOLS}
    ingest_names = {t["name"] for t in INGEST_TOOLS}
    assert fin_names.issubset(query_names)
    assert fin_names.issubset(ingest_names)


def test_dispatch_list_companies_returns_parseable_json():
    d = _dispatcher()
    out = d.dispatch(ToolCall(id="1", name="list_companies_with_financials", input={}))
    payload = json.loads(out)
    assert isinstance(payload, list)
    assert any(e["slug"] == "jpmorgan-chase" for e in payload)


def test_dispatch_get_metric_series_returns_parseable_json():
    d = _dispatcher()
    out = d.dispatch(ToolCall(
        id="2",
        name="get_metric_series",
        input={"slug": "jpmorgan-chase", "metric": "revenue"},
    ))
    payload = json.loads(out)
    assert payload["ticker"] == "JPM"
    assert isinstance(payload["series"], list)


def test_dispatch_unknown_tool_still_returns_error_json():
    d = _dispatcher()
    out = d.dispatch(ToolCall(id="3", name="not_a_real_tool", input={}))
    payload = json.loads(out)
    assert "error" in payload
