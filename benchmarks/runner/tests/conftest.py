"""Shared pytest fixtures for the runner test suite.

These fixtures ensure tests never hit a real LLM, real HuggingFace dataset, or
the user's real cache directory.
"""
from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _isolate_env(monkeypatch):
    """Strip credentials so any accidental network call fails loudly."""
    for var in ("ANTHROPIC_API_KEY", "DATABRICKS_TOKEN", "HF_TOKEN"):
        monkeypatch.delenv(var, raising=False)


@pytest.fixture
def tmp_cache(tmp_path) -> Path:
    """Throwaway cache root unique to each test."""
    root = tmp_path / "cache"
    root.mkdir()
    return root


@pytest.fixture
def repo_root() -> Path:
    """Resolve the repo root from this conftest's location."""
    return Path(__file__).resolve().parents[3]


@pytest.fixture
def wiki_root(repo_root) -> Path:
    """Resolve the wiki/ directory at the repo root."""
    return repo_root / "wiki"
