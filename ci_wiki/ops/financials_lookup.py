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


def _sidecar_path(wiki_dir: Path, slug: str) -> Path:
    return _companies_dir(wiki_dir) / f"{slug}.financials.yaml"


def list_financial_metrics(wiki_dir: Path, slug: str) -> dict:
    """Return the metric catalogue and period keys for one company.

    {ticker, currency, units, metrics, periods} where
        metrics = [{name, description, xbrl_concept}] sorted by name,
        periods = sorted list of period keys ('2023-FY', '2023-Q3', ...).
    Returns {"error": "no_sidecar", "slug": slug} when the file is missing.
    """
    path = _sidecar_path(wiki_dir, slug)
    if not path.is_file():
        return {"error": "no_sidecar", "slug": slug}
    data = load_sidecar(path)
    metrics = data.get("metrics") or {}
    metadata = metrics.get("metadata") or {}
    by_period = metrics.get("by_period") or {}
    metric_entries = [
        {
            "name": name,
            "description": (meta or {}).get("description"),
            "xbrl_concept": (meta or {}).get("xbrl_concept"),
        }
        for name, meta in sorted(metadata.items())
    ]
    return {
        "ticker": data.get("ticker"),
        "currency": metrics.get("currency"),
        "units": metrics.get("units"),
        "metrics": metric_entries,
        "periods": sorted(by_period.keys()),
    }


def get_metric_series(wiki_dir: Path, slug: str, metric: str) -> dict:
    """Time series for one metric across all periods.

    {ticker, metric, currency, units, series: [{period, value}]}
    sorted by period ascending. Periods where the metric is missing are
    omitted (not returned as null).

    Errors:
      {"error": "no_sidecar", "slug": slug}
      {"error": "unknown_metric", "metric": metric, "available": [names]}
    """
    path = _sidecar_path(wiki_dir, slug)
    if not path.is_file():
        return {"error": "no_sidecar", "slug": slug}
    data = load_sidecar(path)
    metrics = data.get("metrics") or {}
    by_period = metrics.get("by_period") or {}
    metadata = metrics.get("metadata") or {}

    if metric not in metadata:
        return {
            "error": "unknown_metric",
            "metric": metric,
            "available": sorted(metadata.keys()),
        }

    series = [
        {"period": period, "value": values[metric]}
        for period, values in sorted(by_period.items())
        if isinstance(values, dict) and metric in values
    ]
    return {
        "ticker": data.get("ticker"),
        "metric": metric,
        "currency": metrics.get("currency"),
        "units": metrics.get("units"),
        "series": series,
    }


def get_filing_table(
    wiki_dir: Path,
    slug: str,
    period: str,
    table_index: int = 0,
) -> dict:
    """Return one filing table verbatim from the sidecar.

    {ticker, period, source_url, filing_id, table_index,
     pre_text, header, rows, post_text}.

    Errors:
      {"error": "no_sidecar", "slug"}
      {"error": "no_filings", "slug"}
      {"error": "unknown_period", "period", "available": [periods]}
      {"error": "no_table", "table_index", "available_indices": [...]}
    """
    path = _sidecar_path(wiki_dir, slug)
    if not path.is_file():
        return {"error": "no_sidecar", "slug": slug}
    data = load_sidecar(path)
    filings = data.get("filings") or []
    if not filings:
        return {"error": "no_filings", "slug": slug}

    available_periods = sorted({f.get("period_covered") for f in filings if f.get("period_covered")})
    filing = next((f for f in filings if f.get("period_covered") == period), None)
    if filing is None:
        return {"error": "unknown_period", "period": period, "available": available_periods}

    tables = filing.get("tables") or []
    if not tables or table_index >= len(tables) or table_index < 0:
        return {
            "error": "no_table",
            "table_index": table_index,
            "available_indices": list(range(len(tables))),
        }
    table = tables[table_index]
    return {
        "ticker": data.get("ticker"),
        "period": period,
        "source_url": filing.get("source_url"),
        "filing_id": filing.get("id"),
        "table_index": table_index,
        "pre_text": table.get("pre_text", ""),
        "header": table.get("header") or [],
        "rows": table.get("rows") or [],
        "post_text": table.get("post_text", ""),
    }
