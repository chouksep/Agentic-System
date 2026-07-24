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
