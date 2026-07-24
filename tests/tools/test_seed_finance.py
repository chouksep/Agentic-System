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
