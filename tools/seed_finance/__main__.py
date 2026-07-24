"""CLI entry point for tools.seed_finance."""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from tools.seed_finance.finqa_index import enumerate_top_by_question_count
from tools.seed_finance.run import seed


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="python -m tools.seed_finance",
        description="Seed real financial data into wiki/companies/*.financials.yaml.",
    )
    p.add_argument(
        "--n-companies",
        type=int,
        default=5,
        help="Seed top-N tickers by FinQA question count (default: 5)",
    )
    p.add_argument(
        "--ticker",
        action="append",
        default=[],
        help="Seed a specific ticker (repeatable). Overrides --n-companies.",
    )
    p.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing sidecar (never overwrites .md).",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch + compose + validate, but don't write to disk.",
    )
    p.add_argument(
        "--out-dir",
        default="wiki",
        help="Output directory (default: 'wiki'; sidecars land under out-dir/companies/).",
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    args = parse_args(argv)

    # Materialize FinQA once — needed for both ticker selection AND the
    # per-ticker filings section (`tables_for`). Streaming iterators can't
    # be reused, so we always load into a list. ~5000 rows × ~10KB each
    # ≈ 50-100 MB in memory; acceptable for a one-shot ops script.
    from datasets import load_dataset  # type: ignore[import-not-found]
    logging.info("Loading FinQA training split...")
    finqa_rows_list: list[dict] = list(
        load_dataset("dreamerdeo/finqa", split="train", streaming=True)
    )
    logging.info("Loaded %d FinQA rows", len(finqa_rows_list))

    if args.ticker:
        tickers = args.ticker
    else:
        top = enumerate_top_by_question_count(finqa_rows_list, n=args.n_companies)
        tickers = [t for t, _years in top]

    logging.info("Seeding %d ticker(s): %s", len(tickers), tickers)

    result = seed(
        tickers=tickers,
        out_dir=Path(args.out_dir),
        force=args.force,
        dry_run=args.dry_run,
        finqa_rows=finqa_rows_list,
    )

    print("\n=== Seed report ===")
    for ticker, info in result.per_ticker.items():
        print(f"  {ticker}: {info}")
    print(f"\nsucceeded={result.succeeded}  failed={result.failed}  skipped={result.skipped}")

    return 0 if result.failed == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
