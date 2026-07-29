"""FinQA dataset adapter for the benchmarks runner.

Loads the HuggingFace `dreamerdeo/finqa` train split, filters to tickers that
have a seeded sidecar under wiki/companies/, parses gold answers into
(value, unit), and yields FinqaCase records.

Row IDs follow `TICKER/YYYY/page_N.pdf-idx`.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path

import yaml

log = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parents[3]
_WIKI_COMPANIES = _REPO_ROOT / "wiki" / "companies"


def _load_seeded_tickers() -> frozenset[str]:
    """Enumerate every wiki/companies/*.financials.yaml and collect their tickers."""
    if not _WIKI_COMPANIES.is_dir():
        return frozenset()
    tickers: set[str] = set()
    for path in _WIKI_COMPANIES.glob("*.financials.yaml"):
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError:
            continue
        t = (data or {}).get("ticker")
        if isinstance(t, str) and t:
            tickers.add(t)
    return frozenset(tickers)


SEEDED_TICKERS: frozenset[str] = _load_seeded_tickers()


@dataclass
class FinqaCase:
    id: str
    ticker: str
    year: int
    question: str
    gold_answer_raw: str
    gold_answer_value: float
    gold_answer_unit: str


_ID_PATTERN = re.compile(r"^([A-Z][A-Z\-]+)/(\d{4})/page_(\d+)\.pdf")

_NUMBER_RE = re.compile(r"-?\d+(?:,\d{3})*(?:\.\d+)?")


def _parse_answer(raw: str) -> tuple[float, str]:
    """Parse a FinQA gold-answer string into (value, unit).

    Units: 'raw' | 'millions' | 'billions' | '%' | 'ratio'.
    Raises ValueError on unparseable input.
    """
    if raw is None:
        raise ValueError("answer is None")
    s = str(raw).strip()
    if not s:
        raise ValueError("empty answer")
    low = s.lower()

    if low in {"n/a", "na", "none", "null"}:
        raise ValueError(f"non-numeric answer: {raw!r}")

    # Ratio: 1.5:1 or 1.5x
    m = re.match(r"^\s*(-?\d+(?:\.\d+)?)\s*(?::\s*1|x)\s*$", low)
    if m:
        return float(m.group(1)), "ratio"

    unit = "raw"
    body = s

    # Trailing unit words / symbols
    if body.strip().endswith("%"):
        unit = "%"
        body = body.rstrip().rstrip("%").rstrip()
    elif re.search(r"\bbillion(s)?\b|\bbn\b", low):
        unit = "billions"
        body = re.sub(r"\b(?:billions?|bn)\b", "", body, flags=re.IGNORECASE)
    elif re.search(r"\bmillion(s)?\b|\bmn\b|\bmm?\b", low):
        unit = "millions"
        body = re.sub(r"\b(?:millions?|mm?|mn)\b", "", body, flags=re.IGNORECASE)

    # Strip currency symbols and commas from the remaining number body.
    body = body.replace("$", "").replace(",", "").strip()

    m = re.search(r"-?\d+(?:\.\d+)?", body)
    if m is None:
        raise ValueError(f"no numeric value found in {raw!r}")
    return float(m.group(0)), unit


def load(
    n: int | None = None,
    tickers: frozenset[str] = SEEDED_TICKERS,
    rows: list[dict] | None = None,
    min_year: int | None = None,
) -> list[FinqaCase]:
    """Load FinQA rows, filter, parse, return sorted+truncated case list.

    When `rows` is None, downloads the HF train split. Tests pass `rows`
    directly to avoid network. `min_year` drops rows whose FinQA year is
    older than the argument (used to align with the seed's period coverage,
    e.g. min_year=2010 for the current AAPL sidecar).
    """
    if rows is None:
        from datasets import load_dataset  # local import to keep test paths cheap
        ds = load_dataset("dreamerdeo/finqa", split="train")
        rows = list(ds)

    cases: list[FinqaCase] = []
    for row in rows:
        m = _ID_PATTERN.match(row.get("id", ""))
        if m is None:
            continue
        ticker, year_s, _page = m.group(1), m.group(2), m.group(3)
        if ticker not in tickers:
            continue
        year = int(year_s)
        if min_year is not None and year < min_year:
            continue
        raw_ans = row.get("answer", "")
        try:
            value, unit = _parse_answer(raw_ans)
        except ValueError as exc:
            log.warning("dropping row %s: %s", row.get("id"), exc)
            continue
        cases.append(FinqaCase(
            id=row["id"],
            ticker=ticker,
            year=year,
            question=row.get("question", ""),
            gold_answer_raw=str(raw_ans),
            gold_answer_value=value,
            gold_answer_unit=unit,
        ))
    cases.sort(key=lambda c: c.id)
    if n is not None:
        cases = cases[:n]
    return cases
