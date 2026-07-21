"""Tests for the per-model pricing table."""
from __future__ import annotations

import pytest

from benchmarks.runner.pricing import (
    PRICES_USD_PER_M_TOKENS,
    compute_cost_usd,
    get_price,
)


def test_known_models_have_prices():
    for model in ("claude-sonnet-4-5", "claude-sonnet-4-6", "claude-opus-4-7"):
        in_p, out_p = get_price(model)
        assert in_p > 0
        assert out_p > 0


def test_compute_cost_simple_proportional():
    # 1M input tokens at $3/M = $3.
    cost = compute_cost_usd(model_id="claude-sonnet-4-5", input_tokens=1_000_000, output_tokens=0)
    in_p, _ = get_price("claude-sonnet-4-5")
    assert cost == pytest.approx(in_p, rel=1e-9)


def test_compute_cost_combines_in_and_out():
    in_p, out_p = get_price("claude-sonnet-4-5")
    cost = compute_cost_usd(
        model_id="claude-sonnet-4-5",
        input_tokens=2_000_000,
        output_tokens=500_000,
    )
    expected = 2 * in_p + 0.5 * out_p
    assert cost == pytest.approx(expected, rel=1e-9)


def test_unknown_model_raises():
    with pytest.raises(KeyError):
        get_price("not-a-real-model")
