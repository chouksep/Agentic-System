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


def test_list_financial_metrics_returns_shape_for_jpm():
    result = financials_lookup.list_financial_metrics(WIKI_DIR, "jpmorgan-chase")
    assert result["ticker"] == "JPM"
    assert result["currency"] == "USD"
    metric_names = [m["name"] for m in result["metrics"]]
    assert metric_names == sorted(metric_names)
    assert {"revenue", "net_income", "diluted_eps"}.issubset(set(metric_names))
    assert isinstance(result["periods"], list)
    assert result["periods"] == sorted(result["periods"])
    assert any(p.endswith("-FY") for p in result["periods"])


def test_list_financial_metrics_no_sidecar():
    result = financials_lookup.list_financial_metrics(WIKI_DIR, "does-not-exist")
    assert result == {"error": "no_sidecar", "slug": "does-not-exist"}


def test_list_financial_metrics_metric_entry_has_metadata_fields():
    result = financials_lookup.list_financial_metrics(WIKI_DIR, "jpmorgan-chase")
    revenue = next(m for m in result["metrics"] if m["name"] == "revenue")
    assert "description" in revenue
    assert "xbrl_concept" in revenue


def test_get_metric_series_revenue_for_jpm():
    result = financials_lookup.get_metric_series(WIKI_DIR, "jpmorgan-chase", "revenue")
    assert result["ticker"] == "JPM"
    assert result["metric"] == "revenue"
    assert result["currency"] == "USD"
    assert result["units"] == "millions"
    periods = [pt["period"] for pt in result["series"]]
    assert periods == sorted(periods), "series must be sorted by period"
    assert len(result["series"]) > 0
    assert all(isinstance(pt["value"], (int, float)) for pt in result["series"])


def test_get_metric_series_diluted_eps_never_scaled_to_millions():
    """C1 regression: diluted_eps must be per-share, not /1_000_000."""
    result = financials_lookup.get_metric_series(WIKI_DIR, "jpmorgan-chase", "diluted_eps")
    assert result["series"], "expected at least one diluted_eps point"
    for pt in result["series"]:
        assert 0.0 < pt["value"] < 100.0, (
            f"diluted_eps must be per-share (0-100 USD range), got {pt}"
        )


def test_get_metric_series_unknown_metric_returns_available_list():
    result = financials_lookup.get_metric_series(WIKI_DIR, "jpmorgan-chase", "bogus_metric")
    assert result["error"] == "unknown_metric"
    assert result["metric"] == "bogus_metric"
    assert isinstance(result["available"], list) and len(result["available"]) > 0
    assert "revenue" in result["available"]


def test_get_metric_series_no_sidecar():
    result = financials_lookup.get_metric_series(WIKI_DIR, "does-not-exist", "revenue")
    assert result == {"error": "no_sidecar", "slug": "does-not-exist"}


# Discover the first LMT filing that actually has tables.
def _first_lmt_period_with_tables() -> str:
    import yaml
    data = yaml.safe_load(
        (WIKI_DIR / "companies" / "lockheed-martin.financials.yaml").read_text(encoding="utf-8")
    )
    for f in data.get("filings") or []:
        if f.get("tables"):
            return f["period_covered"]
    raise RuntimeError("no LMT filing has tables — fixture assumption broken")


def test_get_filing_table_returns_verbatim_fields_for_lmt():
    period = _first_lmt_period_with_tables()
    result = financials_lookup.get_filing_table(WIKI_DIR, "lockheed-martin", period)
    assert result["ticker"] == "LMT"
    assert result["period"] == period
    assert result["table_index"] == 0
    assert isinstance(result["pre_text"], str) and len(result["pre_text"]) > 0, (
        "coercion regression: pre_text must be a non-empty string"
    )
    assert isinstance(result["post_text"], str)
    assert isinstance(result["header"], list) and len(result["header"]) > 0
    assert isinstance(result["rows"], list)


def test_get_filing_table_includes_source_url_when_present():
    period = _first_lmt_period_with_tables()
    result = financials_lookup.get_filing_table(WIKI_DIR, "lockheed-martin", period)
    # source_url may be a string OR None per schema — but must be a key.
    assert "source_url" in result
    assert "filing_id" in result


def test_get_filing_table_unknown_period():
    result = financials_lookup.get_filing_table(WIKI_DIR, "lockheed-martin", "9999-FY")
    assert result["error"] == "unknown_period"
    assert isinstance(result["available"], list) and len(result["available"]) > 0


def test_get_filing_table_out_of_range_index():
    period = _first_lmt_period_with_tables()
    result = financials_lookup.get_filing_table(
        WIKI_DIR, "lockheed-martin", period, table_index=9999
    )
    assert result["error"] == "no_table"
    assert result["table_index"] == 9999
    assert isinstance(result["available_indices"], list) and len(result["available_indices"]) > 0


def test_get_filing_table_no_sidecar():
    result = financials_lookup.get_filing_table(WIKI_DIR, "does-not-exist", "2023-FY")
    assert result == {"error": "no_sidecar", "slug": "does-not-exist"}
