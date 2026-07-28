"""Ticker → wiki slug mapping.

Hand-authored for the 20 companies with the highest FinQA question count
in the training split. Slugs follow the wiki convention: lowercase letters,
digits, and hyphens only. Slug is the shortest recognizable form of the
company's common name (not the legal name).

If you add a new ticker, add both the entry here AND the corresponding
wiki/companies/<slug>.md skeleton page (the seeder will complain otherwise).
"""
from __future__ import annotations

TICKER_SLUG: dict[str, str] = {
    "AAL": "american-airlines",
    "AAPL": "apple",
    "ADBE": "adobe",
    "AES": "aes",
    "AMT": "american-tower",
    "AON": "aon",
    "AWK": "american-water-works",
    "BLK": "blackrock",
    "CME": "cme-group",
    "ETR": "entergy",
    "GPN": "global-payments",
    "GS": "goldman-sachs",
    "IP": "international-paper",
    "IPG": "interpublic-group",
    "JPM": "jpmorgan-chase",
    "LMT": "lockheed-martin",
    "MRO": "marathon-oil",
    "PNC": "pnc-financial-services",
    "PPG": "ppg-industries",
    "RE": "everest-re",
    "RSG": "republic-services",
    "STT": "state-street",
    "UNP": "union-pacific",
    "ZBH": "zimmer-biomet",
}


def slug_for(ticker: str) -> str:
    """Return the wiki slug for `ticker`, or raise KeyError if unknown."""
    try:
        return TICKER_SLUG[ticker]
    except KeyError:
        raise KeyError(
            f"No wiki slug registered for ticker {ticker!r}. "
            f"Add an entry to tools/seed_finance/ticker_slug_map.TICKER_SLUG."
        ) from None
