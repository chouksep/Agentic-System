"""Tests for the financial-sidecar validator (ci_wiki.ops.financials).

All tests are self-contained: they build minimal dict inputs in memory
or read tests/fixtures/financials_valid.yaml. No network, no live LLM.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from ci_wiki.ops import financials  # noqa: F401 — import smoke test


def test_module_imports():
    """Sanity: the module can be imported without side effects."""
    assert financials is not None


import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
VALID_FIXTURE = REPO_ROOT / "tests" / "fixtures" / "financials_valid.yaml"


def _load_valid_fixture() -> dict:
    return yaml.safe_load(VALID_FIXTURE.read_text(encoding="utf-8"))


def test_valid_sample_passes():
    data = _load_valid_fixture()
    errors = financials._check_json_schema(data)
    assert errors == [], f"unexpected errors on the valid fixture: {errors}"


def test_missing_required_top_key_fails():
    data = _load_valid_fixture()
    data.pop("ticker")
    errors = financials._check_json_schema(data)
    assert any("ticker" in e for e in errors), errors


def test_bad_period_key_format_fails():
    data = _load_valid_fixture()
    # Insert a period whose key doesn't match ^\d{4}-(FY|Q[1-4])$
    data["metrics"]["by_period"]["2024Q4"] = {"revenue": 100}
    data["metrics"]["metadata"]["revenue"] = {"description": "revenue"}
    errors = financials._check_json_schema(data)
    assert any("2024Q4" in e or "pattern" in e.lower() for e in errors), errors


def test_cik_must_be_10digit_string():
    data = _load_valid_fixture()
    data["cik"] = 789019  # int rather than 10-char string
    errors = financials._check_json_schema(data)
    assert any("cik" in e.lower() for e in errors), errors


import copy


def test_metric_used_but_undocumented_fails():
    data = _load_valid_fixture()
    # Add a value to a period without a matching metadata entry
    data["metrics"]["by_period"]["2024-FY"]["mystery_metric"] = 42
    errors = financials._check_cross_consistency(data)
    assert any("mystery_metric" in e and "metadata" in e for e in errors), errors


def test_metric_documented_but_unused_fails():
    data = _load_valid_fixture()
    data["metrics"]["metadata"]["ghost_metric"] = {"description": "not used anywhere"}
    errors = financials._check_cross_consistency(data)
    assert any("ghost_metric" in e and "by_period" in e for e in errors), errors


def test_orphan_filing_period_fails():
    data = _load_valid_fixture()
    # period_covered pointing at a period not in by_period
    data["filings"][0]["period_covered"] = "2020-FY"
    errors = financials._check_cross_consistency(data)
    assert any("2020-FY" in e and "period_covered" in e for e in errors), errors


def test_table_row_column_mismatch_fails():
    data = _load_valid_fixture()
    # Add a row with one fewer column than header
    data["filings"][0]["tables"][0]["rows"].append(["Only two", "cols"])
    errors = financials._check_cross_consistency(data)
    assert any("row" in e.lower() and "column" in e.lower() for e in errors), errors


def test_duplicate_filing_id_fails():
    data = _load_valid_fixture()
    dup = copy.deepcopy(data["filings"][0])
    data["filings"].append(dup)  # same id
    errors = financials._check_cross_consistency(data)
    assert any("duplicate" in e.lower() and dup["id"] in e for e in errors), errors


def test_valid_fixture_has_no_cross_consistency_errors():
    """Sanity: the happy-path fixture also passes cross-consistency."""
    data = _load_valid_fixture()
    errors = financials._check_cross_consistency(data)
    assert errors == [], errors
