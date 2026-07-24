"""Tests for tools/seed_finance/ (P2 seeder package).

All tests are self-contained: they use hand-authored fixtures under
tests/tools/fixtures/. No live network calls (SEC EDGAR or HuggingFace).
"""
from __future__ import annotations

from pathlib import Path

import pytest

from tools import seed_finance  # noqa: F401 — import smoke test


FIXTURES = Path(__file__).parent / "fixtures"


def test_module_imports():
    """Sanity: the seed_finance package can be imported."""
    assert seed_finance is not None


def test_fixture_files_exist():
    """Sanity: all committed fixtures are present on disk."""
    for name in (
        "company_facts_JPM.json",
        "submissions_JPM.json",
        "company_tickers.json",
        "finqa_rows.json",
    ):
        assert (FIXTURES / name).exists(), f"missing fixture: {name}"


import json

from tools.seed_finance import xbrl_metric_map


def _company_facts_us_gaap() -> dict:
    """Load the fixture's .facts["us-gaap"] sub-tree."""
    return json.loads((FIXTURES / "company_facts_JPM.json").read_text())["facts"]["us-gaap"]


def test_metric_map_covers_expected_metric_names():
    """METRIC_MAP must contain the standardized short-names used by the sidecar schema."""
    expected = {
        "revenue", "cost_of_revenue", "gross_profit", "operating_income",
        "net_income", "diluted_eps", "total_assets", "total_liabilities",
        "total_equity", "cash_and_equivalents", "total_debt",
        "operating_cash_flow", "capex", "free_cash_flow", "employees",
    }
    missing = expected - set(xbrl_metric_map.METRIC_MAP.keys())
    assert not missing, f"missing metric names: {missing}"


def test_resolve_concept_happy_path():
    facts = _company_facts_us_gaap()
    v = xbrl_metric_map.resolve_concept(
        ["Revenues", "SalesRevenueNet"], facts, "2018-FY",
    )
    assert v == 108783000000  # raw USD from the fixture


def test_resolve_concept_priority_order():
    """First concept in list should win when both are present.

    Fixture has 'Revenues' but not 'RevenueFromContractWithCustomerExcludingAssessedTax'.
    Priority ['Revenues', 'RevenueFromContractWithCustomerExcludingAssessedTax'] should
    return the Revenues value (108783000000). Reversed order should also return
    108783000000 because the ASC 606 concept is absent, so the fallback wins.
    """
    facts = _company_facts_us_gaap()
    v_priority_order = xbrl_metric_map.resolve_concept(
        ["Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax"],
        facts, "2018-FY",
    )
    v_reversed = xbrl_metric_map.resolve_concept(
        ["RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues"],
        facts, "2018-FY",
    )
    assert v_priority_order == 108783000000
    assert v_reversed == 108783000000


def test_resolve_concept_missing_period():
    facts = _company_facts_us_gaap()
    v = xbrl_metric_map.resolve_concept(["Revenues"], facts, "2010-FY")
    assert v is None


def test_resolve_concept_empty_priority_list():
    facts = _company_facts_us_gaap()
    v = xbrl_metric_map.resolve_concept([], facts, "2018-FY")
    assert v is None


from tools.seed_finance import ticker_slug_map


def test_ticker_slug_map_covers_top20_finqa_tickers():
    """The 20 hand-authored entries must include the tickers we plan to seed."""
    # Top-20 tickers by FinQA question count (from prior FinQA sample).
    expected = {
        "ETR", "LMT", "JPM", "AMT", "GS", "AAPL", "PNC", "MRO",
        "UNP", "AWK", "IPG", "AON", "STT", "AES", "RSG", "GPN",
        "AAL", "RE", "ZBH", "CME",
    }
    missing = expected - set(ticker_slug_map.TICKER_SLUG.keys())
    assert not missing, f"missing ticker→slug entries: {missing}"


def test_slug_for_known_ticker():
    assert ticker_slug_map.slug_for("JPM") == "jpmorgan-chase"


def test_slug_for_unknown_ticker_raises():
    with pytest.raises(KeyError, match="ZZZ"):
        ticker_slug_map.slug_for("ZZZ")


def test_all_slugs_are_lowercase_hyphenated():
    """Slug rules: lowercase letters, digits, hyphens only."""
    import re
    slug_pattern = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    for ticker, slug in ticker_slug_map.TICKER_SLUG.items():
        assert slug_pattern.match(slug), f"invalid slug for {ticker}: {slug!r}"


from tools.seed_finance import finqa_index


def _finqa_rows() -> list[dict]:
    return json.loads((FIXTURES / "finqa_rows.json").read_text())


def test_enumerate_top_by_question_count():
    """JPM has 3 rows (2 in 2018, 1 in 2017); GS has 1 (2018); AAPL has 1 (2018)."""
    rows = _finqa_rows()
    top = finqa_index.enumerate_top_by_question_count(rows, n=3)
    tickers = [t for t, _years in top]
    assert tickers[0] == "JPM"  # highest count
    assert set(tickers) == {"JPM", "GS", "AAPL"}
    # JPM's year set should include both 2017 and 2018
    jpm_years = dict(top)["JPM"]
    assert set(jpm_years) == {2017, 2018}


def test_enumerate_top_caps_at_n():
    rows = _finqa_rows()
    top = finqa_index.enumerate_top_by_question_count(rows, n=1)
    assert len(top) == 1


def test_tables_for_dedupes_by_page():
    """The two JPM/2018/page_43 rows share the same table — should return 1 unique table."""
    rows = _finqa_rows()
    tables = finqa_index.tables_for(rows, ticker="JPM", year=2018)
    assert len(tables) == 1
    tbl = tables[0]
    assert "pre_text" in tbl
    assert "header" in tbl
    assert "rows" in tbl
    assert "post_text" in tbl
    assert tbl["header"] == ["", "2018", "2017"]
    # Numeric rows come through as strings, verbatim
    assert any("Net income" in row[0] for row in tbl["rows"])


def test_tables_for_returns_empty_when_no_match():
    rows = _finqa_rows()
    assert finqa_index.tables_for(rows, ticker="ZZZ", year=2018) == []
    assert finqa_index.tables_for(rows, ticker="JPM", year=1999) == []


def test_years_by_ticker_covers_every_ticker():
    """years_by_ticker returns EVERY ticker (not top-N) with sorted year lists."""
    rows = _finqa_rows()
    m = finqa_index.years_by_ticker(rows)
    assert set(m.keys()) == {"JPM", "GS", "AAPL"}
    assert m["JPM"] == [2017, 2018]      # sorted ascending
    assert m["GS"] == [2018]
    assert m["AAPL"] == [2018]
