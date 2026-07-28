"""Tests for ci_wiki.ops.financials_lookup — pure helpers over sidecars."""
from __future__ import annotations

from pathlib import Path

import pytest

from ci_wiki.ops import financials_lookup

REPO_ROOT = Path(__file__).resolve().parents[2]
WIKI_DIR = REPO_ROOT / "wiki"


def test_list_companies_returns_five_seeded_entries_sorted_by_slug():
    result = financials_lookup.list_companies_with_financials(WIKI_DIR)
    slugs = [entry["slug"] for entry in result]
    assert slugs == sorted(slugs), "entries must be sorted by slug"
    assert set(slugs) >= {
        "american-tower",
        "entergy",
        "jpmorgan-chase",
        "lockheed-martin",
        "union-pacific",
    }


def test_list_companies_entry_has_expected_shape():
    result = financials_lookup.list_companies_with_financials(WIKI_DIR)
    jpm = next(e for e in result if e["slug"] == "jpmorgan-chase")
    assert jpm["ticker"] == "JPM"
    assert jpm["cik"] == "0000019617"
    assert jpm["currency"] == "USD"
    assert jpm["units"] in {"millions", "billions", "thousands", "raw"}
    assert isinstance(jpm["period_count"], int) and jpm["period_count"] > 0
    assert isinstance(jpm["has_filings"], bool)


def test_list_companies_returns_empty_when_dir_missing(tmp_path):
    result = financials_lookup.list_companies_with_financials(tmp_path / "does-not-exist")
    assert result == []


def test_list_companies_returns_empty_when_no_sidecars(tmp_path):
    (tmp_path / "companies").mkdir()
    result = financials_lookup.list_companies_with_financials(tmp_path)
    assert result == []
