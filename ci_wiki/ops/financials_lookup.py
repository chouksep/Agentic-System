"""Read-only helpers over wiki/companies/*.financials.yaml sidecars.

Consumed by the agent's tool dispatcher (ci_wiki.llm.tools) so an LLM
can look up structured financial values instead of guessing. All
functions are pure — they read files but do not mutate anything.

Expected misses (unknown slug/metric/period/table) return an
`{"error": ...}` dict so the LLM can recover cheaply. Data-integrity
failures (malformed YAML, schema violations) still raise.
"""
from __future__ import annotations

from pathlib import Path

from ci_wiki.ops.financials import load_sidecar


def _companies_dir(wiki_dir: Path) -> Path:
    return Path(wiki_dir) / "companies"


def list_companies_with_financials(wiki_dir: Path) -> list[dict]:
    """Enumerate every *.financials.yaml under wiki/companies/.

    Each entry: {slug, ticker, cik, currency, units, period_count, has_filings}.
    Sorted by slug. Empty list if the directory does not exist or holds
    no sidecars.
    """
    companies = _companies_dir(wiki_dir)
    if not companies.is_dir():
        return []
    out: list[dict] = []
    for path in sorted(companies.glob("*.financials.yaml")):
        data = load_sidecar(path)
        metrics = data.get("metrics") or {}
        by_period = metrics.get("by_period") or {}
        out.append({
            "slug": path.name.removesuffix(".financials.yaml"),
            "ticker": data.get("ticker"),
            "cik": data.get("cik"),
            "currency": metrics.get("currency"),
            "units": metrics.get("units"),
            "period_count": len(by_period),
            "has_filings": bool(data.get("filings")),
        })
    return out
