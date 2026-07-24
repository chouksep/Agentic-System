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
