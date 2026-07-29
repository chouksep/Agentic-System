"""Pipeline orchestration: for each ticker → fetch → transform → validate → write."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

import yaml

from ci_wiki.ops import financials as _validator

from tools.seed_finance import sec_edgar
from tools.seed_finance.finqa_index import (
    enumerate_top_by_question_count,
    tables_for,
    years_by_ticker,
)
from tools.seed_finance.generate import build_sidecar, build_stub_markdown
from tools.seed_finance.ticker_slug_map import slug_for
from tools.seed_finance.xbrl_metric_map import METRIC_MAP, resolve_concept

log = logging.getLogger(__name__)

_USER_AGENT_DEFAULT = "Agentic-System ci-wiki-seeder pschoukse@gmail.com"

# What periods to attempt per ticker: FinQA year set ∪ last 3 fiscal years.
# Each year expands to 5 period keys: YYYY-FY, YYYY-Q1..Q4.
_QUARTER_FPS = ("Q1", "Q2", "Q3", "Q4")


@dataclass
class SeedResult:
    per_ticker: dict[str, dict] = field(default_factory=dict)
    succeeded: int = 0
    failed: int = 0
    skipped: int = 0


def seed(
    tickers: list[str],
    out_dir: Path,
    force: bool,
    dry_run: bool,
    edgar_client=None,
    finqa_rows: Iterable[dict] | None = None,
) -> SeedResult:
    """Seed sidecars for `tickers` under `out_dir/companies/`.

    Args:
      tickers: uppercase ticker symbols.
      out_dir: root directory; sidecars land at out_dir/companies/<slug>.financials.yaml.
      force: if True, overwrite existing sidecar (never overwrites .md).
      dry_run: if True, do not write to disk.
      edgar_client: injectable SecEdgarClient (defaults to a fresh one).
      finqa_rows: injectable iterable of FinQA rows (defaults to nothing — filings
        section will be empty for each seeded ticker).
    """
    out_dir = Path(out_dir)
    companies_dir = out_dir / "companies"
    companies_dir.mkdir(parents=True, exist_ok=True)

    if edgar_client is None:
        edgar_client = sec_edgar.SecEdgarClient(user_agent=_USER_AGENT_DEFAULT)

    # Cache ticker → cik map once
    try:
        ticker_map = edgar_client.load_ticker_map()
    except sec_edgar.SecEdgarError as exc:
        log.error("Failed to load ticker map; aborting run: %s", exc)
        raise

    # If FinQA rows were provided, materialize once (multiple iterations needed)
    # and pre-compute {ticker: years} up front so _seed_one is O(1) per lookup.
    finqa_rows_list = list(finqa_rows) if finqa_rows is not None else []
    finqa_years_index = years_by_ticker(finqa_rows_list) if finqa_rows_list else {}

    result = SeedResult()
    for ticker in tickers:
        try:
            slug = slug_for(ticker)
        except KeyError as exc:
            result.per_ticker[ticker] = {"seeded": False, "reason": str(exc)}
            result.failed += 1
            continue

        # Idempotence: skip if sidecar already exists and --force not set
        sidecar_path = companies_dir / f"{slug}.financials.yaml"
        markdown_path = companies_dir / f"{slug}.md"
        if sidecar_path.exists() and not force:
            result.per_ticker[ticker] = {
                "seeded": False,
                "reason": "sidecar_exists",
            }
            result.skipped += 1
            continue

        cik = ticker_map.get(ticker)
        if not cik:
            result.per_ticker[ticker] = {
                "seeded": False,
                "reason": "ticker_not_in_master_list",
            }
            result.failed += 1
            continue

        try:
            per_ticker_report = _seed_one(
                ticker=ticker,
                cik=cik,
                slug=slug,
                sidecar_path=sidecar_path,
                markdown_path=markdown_path,
                edgar_client=edgar_client,
                finqa_rows=finqa_rows_list,
                finqa_years=finqa_years_index.get(ticker, []),
                force=force,
                dry_run=dry_run,
            )
        except Exception as exc:
            log.exception("ticker %s: unexpected error", ticker)
            result.per_ticker[ticker] = {"seeded": False, "reason": f"exception: {exc}"}
            result.failed += 1
            continue

        result.per_ticker[ticker] = per_ticker_report
        if per_ticker_report.get("seeded"):
            result.succeeded += 1
        else:
            result.failed += 1

    return result


def _seed_one(
    ticker: str,
    cik: str,
    slug: str,
    sidecar_path: Path,
    markdown_path: Path,
    edgar_client,
    finqa_rows: list[dict],
    finqa_years: list[int],
    force: bool,
    dry_run: bool,
) -> dict:
    """Do the full pipeline for one ticker. Returns a per-ticker report dict.

    finqa_years is the sorted year list for this ticker (pre-computed by
    seed() from years_by_ticker(finqa_rows)); empty list is allowed and
    means the filings section will only cover the "last 3 fiscal years"
    slice — no FinQA-derived filings.
    """
    # Fetch Company Facts (needed for standardized metrics)
    try:
        facts_json = edgar_client.fetch_company_facts(cik)
    except (sec_edgar.NotFound, sec_edgar.SecEdgarError) as exc:
        return {"seeded": False, "reason": f"company_facts_failed: {exc}"}

    us_gaap = (facts_json.get("facts") or {}).get("us-gaap") or {}

    # Determine period target set: FinQA years ∪ last 3 fiscal years
    period_target_years = _period_target_years(finqa_years)

    # Transform metrics: for each metric × each period, walk priority list
    metrics_by_period: dict[str, dict[str, float]] = {}
    for year in period_target_years:
        for period_fp in ("FY",) + _QUARTER_FPS:
            period_key = f"{year}-{period_fp}"
            period_dict: dict[str, float] = {}
            for metric_name, concepts in METRIC_MAP.items():
                if not concepts:
                    continue  # derived metrics computed below
                raw = resolve_concept(concepts, us_gaap, period_key)
                if raw is None:
                    continue
                period_dict[metric_name] = _scale_to_units(raw, metric_name)
            # Derived: free_cash_flow = operating_cash_flow - capex
            ocf = period_dict.get("operating_cash_flow")
            capex = period_dict.get("capex")
            if ocf is not None and capex is not None:
                period_dict["free_cash_flow"] = ocf - capex
            if period_dict:
                metrics_by_period[period_key] = period_dict

    # Build metadata for only the metrics that resolved
    used_metric_names = {m for d in metrics_by_period.values() for m in d.keys()}
    metric_metadata = {
        name: {
            "xbrl_concept": f"us-gaap:{METRIC_MAP[name][0]}" if METRIC_MAP.get(name) else "",
            "description": name.replace("_", " ").capitalize(),
        }
        for name in sorted(used_metric_names)
    }
    # Clean up empty xbrl_concept fields (schema doesn't allow empty strings on optional fields
    # but our metadata schema allows omitting them entirely)
    for name, meta in metric_metadata.items():
        if not meta.get("xbrl_concept"):
            del meta["xbrl_concept"]

    # Fetch every 10-K (recent + paginated history) + build filings list
    filings: list[dict] = []
    try:
        all_10ks = edgar_client.fetch_all_10k_filings(cik)
    except (sec_edgar.NotFound, sec_edgar.SecEdgarError):
        all_10ks = []
    for year in period_target_years:
        filing_entry = _find_10k_for_year(all_10ks, year, cik)
        if not filing_entry:
            continue
        tables = tables_for(finqa_rows, ticker, year)
        for table_idx, table in enumerate(tables):
            table["id"] = f"{ticker.lower()}-{year}-table-{table_idx}"
        filings.append({
            "id": f"{ticker.lower()}-10k-{year}",
            "form": filing_entry["form"],
            "filed": filing_entry["filed"],
            "period_covered": f"{year}-FY",
            "source_url": filing_entry["source_url"],
            "tables": tables,
        })

    # Only include periods that have valid values referenced by filings, drop others
    # (this satisfies rule 3 on both sides — filings reference existing periods)
    valid_period_keys = set(metrics_by_period.keys())
    filings = [f for f in filings if f["period_covered"] in valid_period_keys]

    # Compose + validate
    sidecar = build_sidecar(
        ticker=ticker,
        cik=cik,
        metrics_by_period=metrics_by_period,
        metric_metadata=metric_metadata,
        filings=filings,
    )
    errors = _validator.validate(sidecar)
    if errors:
        return {"seeded": False, "reason": "validation_failed", "errors": errors}

    if dry_run:
        return {
            "seeded": True,
            "dry_run": True,
            "metrics_count": sum(len(d) for d in metrics_by_period.values()),
            "filings_count": len(filings),
        }

    # Write files
    sidecar_path.write_text(
        yaml.safe_dump(sidecar, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    if not markdown_path.exists():
        markdown_path.write_text(
            build_stub_markdown(slug=slug, name=_display_name_for(ticker)),
            encoding="utf-8",
        )
    return {
        "seeded": True,
        "metrics_count": sum(len(d) for d in metrics_by_period.values()),
        "filings_count": len(filings),
    }


def _period_target_years(finqa_years: list[int]) -> list[int]:
    """Target year set = FinQA years ∪ last 3 fiscal years (calendar-based)."""
    from datetime import date
    current = date.today().year
    return sorted(set(finqa_years) | set(range(current - 3, current + 1)))


# Metrics whose XBRL unit is NOT plain USD (e.g. USD/shares, pure counts) and
# therefore must never be divided into "millions of USD". Scaling these would
# silently corrupt them (e.g. a $5.30 diluted EPS becomes 0.0).
_PER_SHARE_OR_UNITLESS_METRICS = {"diluted_eps", "employees"}


def _scale_to_units(raw: float | int, metric_name: str) -> float:
    """Convert a raw XBRL value to the sidecar's storage units.

    Monetary metrics are stored in millions of USD, so we divide by 1e6 and
    round to 2 decimals. Per-share and unitless metrics (see
    `_PER_SHARE_OR_UNITLESS_METRICS`) are passed through unscaled — they are
    not USD amounts and dividing them by 1,000,000 would silently corrupt
    the value.
    """
    if metric_name in _PER_SHARE_OR_UNITLESS_METRICS:
        return round(float(raw), 2)
    return round(float(raw) / 1_000_000, 2)


def _find_10k_for_year(
    filings_10k: list[dict],
    year: int,
    cik: str,
) -> dict | None:
    """Find the 10-K covering fiscal year `year`.

    `filings_10k` is a flat list of 10-K filing dicts (as returned by
    `SecEdgarClient.fetch_all_10k_filings`), each with keys
    `accessionNumber`, `filingDate`, `reportDate`, `form`, `primaryDocument`.
    It spans both the recent-filings window and any older filings paginated
    into `filings.files[]` — a company with a long filing history (e.g. AMT,
    public since ~2005) has 10-Ks older than the ~1000-filing recent window,
    and those would otherwise be silently invisible to this lookup.

    Companies with a calendar fiscal year end typically file their FY N 10-K
    in early calendar year N+1 (e.g. JPM's FY2018 10-K filed 2019-02-26).
    Companies with a non-calendar fiscal year end (e.g. AAPL's Sep 30 FYE)
    file their FY N 10-K within calendar year N itself (e.g. AAPL's FY2018
    10-K filed 2018-11-05). A guard that only accepts `year + 1` silently
    drops the latter, leaving `filings` empty for roughly half of tickers.

    When the submissions API provides `reportDate` (the filing's fiscal
    period end, a YYYY-MM-DD string) we match on that directly — it is
    authoritative regardless of fiscal year end. When `reportDate` is
    unavailable for an entry we fall back to accepting a filing date in
    either `year` or `year + 1`.

    Returns {"form", "filed", "source_url"} or None.
    """
    for entry in filings_10k:
        if entry.get("form") != "10-K":
            continue
        filed = entry.get("filingDate") or ""
        report_date = entry.get("reportDate") or ""
        if report_date:
            if not report_date.startswith(str(year)):
                continue
        elif not (filed.startswith(str(year)) or filed.startswith(str(year + 1))):
            continue
        accn = entry.get("accessionNumber") or ""
        doc = entry.get("primaryDocument") or ""
        accn_no_dashes = accn.replace("-", "")
        source_url = (
            f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accn_no_dashes}/{doc}"
        )
        return {"form": "10-K", "filed": filed, "source_url": source_url}
    return None


def _display_name_for(ticker: str) -> str:
    """Best-effort human name for the markdown stub's `name:` field.

    For P2 we use the slug rewritten with title case as a fallback. If a
    curator later fills in the full legal name in the .md, we don't touch it.
    """
    from tools.seed_finance.ticker_slug_map import slug_for
    slug = slug_for(ticker)
    return " ".join(word.capitalize() for word in slug.split("-"))
