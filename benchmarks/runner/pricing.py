"""Per-model price table for cost accounting.

Prices are in USD per 1 million tokens (input, output). Values match the
publicly listed list price at time of writing -- update as needed; the
constants module makes it grep-able and easy to override.

If a model isn't in the table, get_price raises KeyError so cost accounting
fails loudly rather than silently undercounting.
"""
from __future__ import annotations

# (input USD/M tokens, output USD/M tokens)
PRICES_USD_PER_M_TOKENS: dict[str, tuple[float, float]] = {
    # Anthropic native names.
    "claude-sonnet-4-5": (3.0, 15.0),
    "claude-sonnet-4-6": (3.0, 15.0),
    "claude-opus-4-7": (15.0, 75.0),
    # Databricks-prefixed names route to the same underlying models.
    "databricks-claude-sonnet-4-5": (3.0, 15.0),
    "databricks-claude-sonnet-4-6": (3.0, 15.0),
}


def get_price(model_id: str) -> tuple[float, float]:
    """Return (input_usd_per_M, output_usd_per_M) for `model_id`.

    Raises:
        KeyError: if the model isn't in PRICES_USD_PER_M_TOKENS. Caller should
            either add the entry or wrap in a try/except that records zero
            cost with an explicit `pricing_missing` flag.
    """
    return PRICES_USD_PER_M_TOKENS[model_id]


def compute_cost_usd(
    *,
    model_id: str,
    input_tokens: int,
    output_tokens: int,
) -> float:
    """Compute USD cost for one request from token counts."""
    in_p, out_p = get_price(model_id)
    return (input_tokens / 1_000_000) * in_p + (output_tokens / 1_000_000) * out_p
