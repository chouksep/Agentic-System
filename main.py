#!/usr/bin/env python3
"""ci-wiki — Competitive Intelligence Wiki CLI

Usage:
  python main.py ingest --source <url-or-path>   # ingest one source
  python main.py ingest --all                    # ingest all pending sources
  python main.py query "<question>" [--save]     # ask a question
  python main.py lint [--dry-run] [--no-llm]    # check wiki quality
  python main.py status                          # show DB stats
  python main.py index                           # rebuild wiki/index.md
"""
from __future__ import annotations

import argparse
import io
import sys
from pathlib import Path

# Ensure UTF-8 output on Windows (console may default to cp1252)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def _get_components():
    """Lazy import: only load heavy deps when actually running a command."""
    from ci_wiki.config import Config
    from ci_wiki.db import Database
    from ci_wiki.llm.client import LLMClient
    from ci_wiki.wiki.page import WikiPageIO
    from ci_wiki.wiki.index import WikiIndex

    config = Config.from_env()
    db = Database(config.db_path)
    db.connect()
    llm = LLMClient(config)
    page_io = WikiPageIO(config.wiki_dir)
    index = WikiIndex(config.wiki_dir, page_io)
    return config, db, llm, page_io, index


def cmd_ingest(args: argparse.Namespace) -> int:
    config, db, llm, page_io, index = _get_components()
    from ci_wiki.ops.ingest import IngestOp
    op = IngestOp(config=config, db=db, llm=llm, page_io=page_io, index=index)

    try:
        if args.all:
            print("Ingesting all pending sources...")
            results = op.run_all_pending()
            total_tokens = sum(r.tokens_used for r in results)
            errors = [r for r in results if r.error and r.error != "already ingested"]
            print(f"\nDone. {len(results)} source(s) processed. "
                  f"Total tokens: {total_tokens:,}. Errors: {len(errors)}.")
        elif args.source:
            src = args.source
            print(f"Ingesting: {src}")
            if src.startswith("http://") or src.startswith("https://"):
                result = op.run_url(src)
            else:
                result = op.run_file(Path(src))
            op._print_result(result)
            if result.error and result.error != "already ingested":
                return 1
        else:
            print("ERROR: Specify --source <url-or-path> or --all", file=sys.stderr)
            return 1
    finally:
        db.close()
    return 0


def cmd_query(args: argparse.Namespace) -> int:
    config, db, llm, page_io, index = _get_components()
    from ci_wiki.ops.query import QueryOp
    op = QueryOp(config=config, db=db, llm=llm, page_io=page_io, index=index)

    question = args.question
    save = getattr(args, "save", False)

    print(f"Query: {question}\n")
    print("=" * 60)
    try:
        result = op.run(question, save=save)
        print(result.answer)
        print("=" * 60)
        print(f"Pages consulted: {', '.join(result.pages_consulted) or 'none'}")
        print(f"Tokens used: {result.tokens_used:,}")
        if result.filed_to:
            print(f"Saved to: {result.filed_to}")
    finally:
        db.close()
    return 0


def cmd_lint(args: argparse.Namespace) -> int:
    config, db, llm, page_io, index = _get_components()
    from ci_wiki.ops.lint import LintOp
    op = LintOp(config=config, db=db, llm=llm, page_io=page_io, index=index)

    dry_run = getattr(args, "dry_run", False)
    no_llm = getattr(args, "no_llm", False)

    if dry_run:
        print("Lint (dry run — no changes will be made)...")
    else:
        print("Linting wiki...")

    try:
        issues = op.run(dry_run=dry_run, llm_check=not no_llm)
    finally:
        db.close()

    errors = [i for i in issues if i.severity == "error"]
    return 1 if errors else 0


def cmd_status(args: argparse.Namespace) -> int:
    config, db, llm, page_io, index = _get_components()
    try:
        stats = db.get_stats()
    finally:
        db.close()

    print("ci-wiki Status")
    print("=" * 40)
    print(f"Sources total:    {stats['sources_total']}")
    print(f"Sources ingested: {stats['sources_ingested']}")
    print(f"Sources pending:  {stats['sources_pending']}")
    print(f"Wiki pages:       {stats['pages_total']}")
    print(f"Last ingest:      {stats['last_ingest'] or 'never'}")
    return 0


def cmd_index(args: argparse.Namespace) -> int:
    config, db, llm, page_io, index = _get_components()
    try:
        print("Rebuilding wiki/index.md...")
        index.rebuild()
        print("Done.")
    finally:
        db.close()
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ci-wiki",
        description="Competitive Intelligence Wiki — LLM-powered knowledge compilation",
    )
    parser.add_argument(
        "--model",
        help="Override Claude model (e.g. claude-opus-4-6)",
        default=None,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # ingest
    p_ingest = subparsers.add_parser("ingest", help="Ingest source documents into the wiki")
    p_ingest.add_argument("--source", metavar="URL_OR_PATH", help="URL or file path to ingest")
    p_ingest.add_argument("--all", action="store_true", help="Ingest all pending sources")

    # query
    p_query = subparsers.add_parser("query", help="Ask a competitive intelligence question")
    p_query.add_argument("question", help="Natural language question")
    p_query.add_argument("--save", action="store_true", help="Save answer to wiki/queries/")

    # lint
    p_lint = subparsers.add_parser("lint", help="Check wiki for quality issues")
    p_lint.add_argument("--dry-run", action="store_true", help="Report issues without fixing them")
    p_lint.add_argument("--no-llm", action="store_true", help="Skip LLM semantic checks (faster)")

    # status
    subparsers.add_parser("status", help="Show wiki and source statistics")

    # index
    subparsers.add_parser("index", help="Rebuild wiki/index.md from all pages")

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    # Model override
    if args.model:
        import os
        os.environ["CI_WIKI_MODEL"] = args.model

    dispatch = {
        "ingest": cmd_ingest,
        "query": cmd_query,
        "lint": cmd_lint,
        "status": cmd_status,
        "index": cmd_index,
    }

    handler = dispatch.get(args.command)
    if handler is None:
        print(f"Unknown command: {args.command}", file=sys.stderr)
        return 1

    try:
        return handler(args)
    except RuntimeError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
