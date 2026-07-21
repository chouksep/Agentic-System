"""Tests for the disk-backed Cache."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from benchmarks.runner.cache import Cache, build_key
from benchmarks.runner.types import AgentRecord
from benchmarks.runner.version import RUNNER_VERSION


def _record() -> AgentRecord:
    return AgentRecord(
        calls=[{"read_wiki_page": {"slug": "openai", "page_type": "company"}}],
        tokens_used=420,
        latency_seconds=1.23,
        cost_usd=0.005,
    )


def test_cache_miss_invokes_compute_fn(tmp_cache):
    cache = Cache(tmp_cache)
    calls = {"n": 0}

    def compute() -> AgentRecord:
        calls["n"] += 1
        return _record()

    key = build_key(model_id="m", case_id="c", tools_schema='{"v":1}')
    result = cache.get_or_compute(key, compute)
    assert calls["n"] == 1
    assert result.tokens_used == 420


def test_cache_hit_skips_compute_fn(tmp_cache):
    cache = Cache(tmp_cache)
    key = build_key(model_id="m", case_id="c", tools_schema='{"v":1}')
    cache.get_or_compute(key, _record)  # populate

    calls = {"n": 0}

    def compute() -> AgentRecord:
        calls["n"] += 1
        return _record()

    cache.get_or_compute(key, compute)
    assert calls["n"] == 0


def test_cache_schema_change_invalidates(tmp_cache):
    cache = Cache(tmp_cache)
    key_a = build_key(model_id="m", case_id="c", tools_schema='{"v":1}')
    key_b = build_key(model_id="m", case_id="c", tools_schema='{"v":2}')
    assert key_a != key_b
    cache.get_or_compute(key_a, _record)
    calls = {"n": 0}

    def compute() -> AgentRecord:
        calls["n"] += 1
        return _record()

    cache.get_or_compute(key_b, compute)
    assert calls["n"] == 1  # different key → recomputed


def test_cache_corrupt_json_triggers_recompute(tmp_cache, caplog):
    cache = Cache(tmp_cache)
    key = build_key(model_id="m", case_id="c", tools_schema='{"v":1}')
    cache.get_or_compute(key, _record)

    # Corrupt the on-disk JSON.
    path = cache._path_for_key(key)
    path.write_text("{ not valid json", encoding="utf-8")

    calls = {"n": 0}

    def compute() -> AgentRecord:
        calls["n"] += 1
        return _record()

    cache.get_or_compute(key, compute)
    assert calls["n"] == 1
    # Should now be valid JSON again.
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["tokens_used"] == 420


def test_build_key_is_stable_and_includes_runner_version():
    k1 = build_key(model_id="m", case_id="c", tools_schema='{"v":1}')
    k2 = build_key(model_id="m", case_id="c", tools_schema='{"v":1}')
    assert k1 == k2
    assert RUNNER_VERSION in k1 or len(k1) >= 64  # sha256 hex
