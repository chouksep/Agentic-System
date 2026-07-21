"""CLI entry point for benchmarks.runner.

Run:
    python -m benchmarks.runner --benchmark bfcl --models <csv> [...]
"""
from __future__ import annotations

import argparse
import logging
import random
import sys
from datetime import datetime, timezone
from pathlib import Path

from benchmarks.runner.agent import AgentRunner
from benchmarks.runner.cache import Cache
from benchmarks.runner.comparator import Comparator, CostCeilingExceeded
from benchmarks.runner.datasets.base import BfclCase, EntityIndex
from benchmarks.runner.datasets.entity_questions import load_entity_questions
from benchmarks.runner.datasets.fixtures import load_committed_fixtures
from benchmarks.runner.datasets.triviaqa import load_triviaqa
from benchmarks.runner.report import render
from benchmarks.runner.types import MultiModelResults

_VALID_DATASETS = ("fixtures", "entity_questions", "triviaqa")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="python -m benchmarks.runner")
    p.add_argument("--benchmark", choices=["bfcl"], required=True)
    p.add_argument(
        "--models",
        required=True,
        type=lambda s: [m.strip() for m in s.split(",") if m.strip()],
        help="Comma-separated model IDs (e.g. claude-sonnet-4-5,claude-sonnet-4-6).",
    )
    p.add_argument(
        "--datasets",
        default="fixtures,entity_questions",
        type=lambda s: [d.strip() for d in s.split(",") if d.strip()],
        help=f"Comma-separated subset of {_VALID_DATASETS}.",
    )
    p.add_argument("--n-samples", type=int, default=200)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--max-cost", type=float, default=15.0,
                   help="Hard ceiling in USD; abort before the next LLM call exceeds it.")
    p.add_argument("--no-cache", action="store_true",
                   help="Bypass cache reads (still writes for future runs).")
    p.add_argument("--cache-dir", default=None, help="Override cache root.")
    p.add_argument("--output-dir", default=None,
                   help="Override output dir (default benchmarks/runner/results/<timestamp>).")
    return p.parse_args(argv)


def default_agent_factory():
    """Build a factory that creates an AgentRunner per model, sharing one client."""
    import anthropic  # type: ignore[import-not-found]
    from ci_wiki.config import Config

    cfg = Config.from_env()
    if not cfg.anthropic_api_key:
        raise RuntimeError(
            "default_agent_factory needs ANTHROPIC_API_KEY (loaded by ci_wiki.config)."
        )
    # max_retries=3 matches spec section 7 — exponential backoff via SDK.
    client = anthropic.Anthropic(api_key=cfg.anthropic_api_key, max_retries=3)

    def factory(model_id: str) -> AgentRunner:
        return AgentRunner(model_id=model_id, anthropic_client=client)

    return factory


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def assemble_cases(
    *,
    repo_root: Path,
    datasets: list[str],
    n_samples: int,
    seed: int,
) -> list[BfclCase]:
    for d in datasets:
        if d not in _VALID_DATASETS:
            raise ValueError(f"Unknown dataset: {d!r}. Valid: {_VALID_DATASETS}")
    entity_index = EntityIndex.from_wiki(repo_root / "wiki")
    pool: list[BfclCase] = []
    if "fixtures" in datasets:
        pool.extend(load_committed_fixtures(repo_root=repo_root))
    if "entity_questions" in datasets:
        pool.extend(load_entity_questions(entity_index=entity_index, n_max=n_samples * 2))
    if "triviaqa" in datasets:
        pool.extend(load_triviaqa(entity_index=entity_index, n_max=n_samples * 2))
    # Dedupe by question text (case-insensitive).
    seen: set[str] = set()
    deduped: list[BfclCase] = []
    for c in pool:
        k = c.question.strip().lower()
        if k in seen:
            continue
        seen.add(k)
        deduped.append(c)
    rng = random.Random(seed)
    rng.shuffle(deduped)
    return deduped[:n_samples]


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    args = parse_args(argv)
    repo_root = _repo_root()
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = Path(args.output_dir) if args.output_dir else (
        repo_root / "benchmarks" / "runner" / "results" / run_id
    )
    cache_root = Path(args.cache_dir) if args.cache_dir else (
        repo_root / "benchmarks" / "runner" / "cache"
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    cases = assemble_cases(
        repo_root=repo_root,
        datasets=args.datasets,
        n_samples=args.n_samples,
        seed=args.seed,
    )
    cache = Cache(cache_root)
    cmp = Comparator(cache=cache)
    agent_factory_builder = default_agent_factory
    factory = agent_factory_builder()
    partial = False
    reason = None
    try:
        records = cmp.run_agent_phase(
            models=args.models,
            cases=cases,
            agent_factory=factory,
            max_cost=args.max_cost,
        )
    except CostCeilingExceeded as exc:
        partial = True
        reason = str(exc)
        # Still emit reports for whatever we managed to cache.
        records = _records_from_cache(cmp.cache, args.models, cases)

    results: MultiModelResults
    if records and any(records[m] for m in args.models):
        results = cmp.run_evaluation_phase(
            repo_root=repo_root, records=records, cases=cases, run_dir=out_dir,
        )
    else:
        results = MultiModelResults(run_id=run_id, models=[], cases_evaluated=0)
    results.partial = partial
    results.reason = reason
    render(results, out_dir)
    if partial:
        logging.warning("Run is PARTIAL: %s", reason)
    print(f"Wrote: {out_dir / 'report.md'}")
    print(f"Wrote: {out_dir / 'summary.json'}")
    return 0 if not partial else 2


def _records_from_cache(cache, models, cases):
    """Recover whatever cells are already on disk; missing cells become empty records."""
    from benchmarks.runner.cache import build_key
    from benchmarks.runner.types import AgentRecord
    out: dict[str, dict[str, AgentRecord]] = {m: {} for m in models}
    for m in models:
        for c in cases:
            key = build_key(
                model_id=m, case_id=c.id,
                tools_schema=__import__("json").dumps(sorted(c.functions), separators=(",", ":")),
            )
            path = cache._path_for_key(key)
            if path.exists():
                import json as _j
                out[m][c.id] = AgentRecord.from_dict(_j.loads(path.read_text(encoding="utf-8")))
    return out


if __name__ == "__main__":
    sys.exit(main())
