"""Enumerate FinQA companies from row IDs and extract per-company year sets.

FinQA row IDs follow the pattern `TICKER/YYYY/page_N.pdf-idx`. We parse the
ticker + year from the ID, count questions per ticker, and deduplicate tables
so downstream code sees one unique table per (ticker, year, page).
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict
from typing import Iterable

_ID_PATTERN = re.compile(r"^([A-Z][A-Z\-]+)/(\d{4})/page_(\d+)\.pdf")


def _parse_id(row_id: str) -> tuple[str, int, int] | None:
    """Return (ticker, year, page) or None if the id doesn't match."""
    m = _ID_PATTERN.match(row_id)
    if not m:
        return None
    return m.group(1), int(m.group(2)), int(m.group(3))


def enumerate_top_by_question_count(
    rows: Iterable[dict],
    n: int,
) -> list[tuple[str, list[int]]]:
    """Return top-N tickers by question count, each paired with its year set.

    Result is sorted by count descending; ties are broken by ticker
    alphabetically for determinism. Year lists are sorted ascending.
    """
    count = Counter()
    years_by_ticker: dict[str, set[int]] = defaultdict(set)
    for row in rows:
        parsed = _parse_id(row.get("id", ""))
        if parsed is None:
            continue
        ticker, year, _page = parsed
        count[ticker] += 1
        years_by_ticker[ticker].add(year)

    # Sort by (-count, ticker) for a total order.
    ranked = sorted(count.items(), key=lambda kv: (-kv[1], kv[0]))
    return [
        (ticker, sorted(years_by_ticker[ticker]))
        for ticker, _n in ranked[:n]
    ]


def years_by_ticker(rows: Iterable[dict]) -> dict[str, list[int]]:
    """Return {ticker: sorted_years} for EVERY ticker in `rows`.

    Unlike enumerate_top_by_question_count, this returns all tickers
    unranked — used by the seeder pipeline to look up a specific ticker's
    year set without iterating the full row set per ticker.
    """
    out: dict[str, set[int]] = defaultdict(set)
    for row in rows:
        parsed = _parse_id(row.get("id", ""))
        if parsed is None:
            continue
        ticker, year, _page = parsed
        out[ticker].add(year)
    return {ticker: sorted(ys) for ticker, ys in out.items()}


def tables_for(
    rows: Iterable[dict],
    ticker: str,
    year: int,
) -> list[dict]:
    """Return unique tables for (ticker, year), deduped by pdf_page.

    Each returned dict has the sidecar-ready shape:
        {"pre_text": str, "header": list[str], "rows": list[list[str]], "post_text": str}
    """
    seen_pages: set[int] = set()
    out: list[dict] = []
    for row in rows:
        parsed = _parse_id(row.get("id", ""))
        if parsed is None:
            continue
        row_ticker, row_year, row_page = parsed
        if row_ticker != ticker or row_year != year:
            continue
        if row_page in seen_pages:
            continue
        seen_pages.add(row_page)
        raw_table = row.get("table") or []
        if not raw_table:
            continue
        header = [str(c) for c in raw_table[0]]
        body = [[str(c) for c in r] for r in raw_table[1:]]
        out.append({
            "pre_text": row.get("pre_text", "") or "",
            "header": header,
            "rows": body,
            "post_text": row.get("post_text", "") or "",
        })
    return out
