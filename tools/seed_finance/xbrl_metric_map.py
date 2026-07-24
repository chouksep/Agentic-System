"""Short-name metric ↔ us-gaap XBRL concept mapping.

METRIC_MAP maps our sidecar's short-name metrics (see P1 schema §5) to
priority lists of us-gaap concept names. Companies tag revenue differently
depending on when they filed (ASC 606 caused a taxonomy transition circa
2018), so most metrics have 2-3 fallback concepts.

resolve_concept walks the priority list and returns the first hit's value
for the requested period, or None if no concept has data for that period.
Callers must NOT interpolate or fabricate; None means the metric is genuinely
absent from the source and should be omitted from the sidecar.
"""
from __future__ import annotations

METRIC_MAP: dict[str, list[str]] = {
    "revenue": [
        "Revenues",
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "SalesRevenueNet",
    ],
    "cost_of_revenue": [
        "CostOfRevenue",
        "CostOfGoodsSold",
        "CostOfGoodsAndServicesSold",
    ],
    "gross_profit": ["GrossProfit"],
    "operating_income": ["OperatingIncomeLoss"],
    "net_income": ["NetIncomeLoss"],
    "diluted_eps": ["EarningsPerShareDiluted"],
    "total_assets": ["Assets"],
    "total_liabilities": ["Liabilities"],
    "total_equity": ["StockholdersEquity"],
    "cash_and_equivalents": [
        "CashAndCashEquivalentsAtCarryingValue",
        "Cash",
    ],
    "total_debt": ["LongTermDebt", "LongTermDebtNoncurrent"],
    "operating_cash_flow": [
        "NetCashProvidedByUsedInOperatingActivities",
    ],
    "capex": ["PaymentsToAcquirePropertyPlantAndEquipment"],
    # free_cash_flow is DERIVED downstream (operating_cash_flow − capex).
    "free_cash_flow": [],
    # employees is not in Company Facts JSON; best-effort from other sources.
    "employees": [],
}


def resolve_concept(
    concepts: list[str],
    facts: dict,
    period_key: str,
) -> float | None:
    """Walk `concepts` in priority order; return the first hit's value.

    Args:
      concepts: priority list of us-gaap concept names (e.g. ["Revenues", ...]).
      facts: the .facts["us-gaap"] sub-tree of a SEC Company Facts JSON.
      period_key: our sidecar convention: "YYYY-FY" or "YYYY-QN".

    Returns:
      The numeric value (float or int) from the first concept that has data
      for `period_key`, or None if no concept has data for that period.
    """
    for concept in concepts:
        block = facts.get(concept)
        if not block:
            continue
        # Company Facts stores values under units.USD (or USD/shares, etc.).
        # We iterate all unit buckets to find the requested period.
        for _unit, entries in (block.get("units") or {}).items():
            for entry in entries:
                if _entry_matches_period(entry, period_key):
                    return entry.get("val")
    return None


def _entry_matches_period(entry: dict, period_key: str) -> bool:
    """Return True if a Company Facts entry corresponds to our sidecar period_key."""
    fy = entry.get("fy")
    fp = entry.get("fp")
    if fy is None or fp is None:
        return False
    # Sidecar uses YYYY-FY for annual, YYYY-QN for quarterly.
    if fp == "FY" and period_key == f"{fy}-FY":
        return True
    if fp in ("Q1", "Q2", "Q3", "Q4") and period_key == f"{fy}-{fp}":
        return True
    return False
