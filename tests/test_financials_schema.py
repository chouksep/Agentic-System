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
