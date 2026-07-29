"""CLI entry point for benchmarks.runner.

Run:
    python -m benchmarks.runner --benchmark bfcl --models <csv> [...]
"""
from __future__ import annotations

import argparse
import json
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
from benchmarks.runner.datasets.llm_verifier import VerifierFn, verify as llm_verify
from benchmarks.runner.datasets.synthesizer import Synthesizer
from benchmarks.runner.datasets.triviaqa import load_triviaqa
from benchmarks.runner.report import render
from benchmarks.runner.types import MultiModelResults

log = logging.getLogger(__name__)

_VALID_DATASETS = ("fixtures", "entity_questions", "triviaqa", "synthesized")
_VALID_SINGLE_DATASETS = ("finqa",)

# Off-topic questions used by the synthesizer to build `irrelevance`-category
# cases. Each one is clearly outside the ci-wiki domain (AI companies /
# products / people); the agent is expected to abstain (emit zero tool calls).
_OFF_TOPIC_QUESTIONS: list[str] = [
    "What's the capital of France?",
    "How many planets are in the solar system?",
    "Who painted the Mona Lisa?",
    "When did World War II end?",
    "What's the boiling point of water in Celsius?",
    "What language is spoken in Brazil?",
    "How many continents are there?",
]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="python -m benchmarks.runner")
    p.add_argument("--benchmark", choices=["bfcl"], default=None,
                   help="BFCL harness mode. Mutually exclusive with --dataset.")
    p.add_argument(
        "--models",
        default=None,
        type=lambda s: [m.strip() for m in s.split(",") if m.strip()],
        help="Comma-separated model IDs (e.g. claude-sonnet-4-5,claude-sonnet-4-6). "
             "Required with --benchmark bfcl.",
    )
    p.add_argument(
        "--datasets",
        default="fixtures,synthesized",
        type=lambda s: [d.strip() for d in s.split(",") if d.strip()],
        help=(
            f"Comma-separated subset of {_VALID_DATASETS}. "
            "'fixtures' + 'synthesized' is the recommended trustworthy default; "
            "'entity_questions' + 'triviaqa' produce over-matched ground truth "
            "against broad QA corpora and should only be used once "
            "EntityIndex.match() is disambiguated."
        ),
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
    p.add_argument(
        "--dataset",
        choices=_VALID_SINGLE_DATASETS,
        default=None,
        help="Single-dataset mode (e.g. 'finqa'). Mutually exclusive with --benchmark.",
    )
    p.add_argument(
        "--n",
        type=int,
        default=None,
        help="(finqa) cap the number of cases; default = all seeded",
    )
    p.add_argument(
        "--tickers",
        type=str,
        default=None,
        help="(finqa) comma-separated ticker override (e.g. 'JPM,AAPL'); default = SEEDED_TICKERS",
    )
    args = p.parse_args(argv)
    if args.dataset is None and args.benchmark is None:
        p.error("one of --benchmark or --dataset is required")
    if args.dataset is not None and args.benchmark is not None:
        p.error("--benchmark and --dataset are mutually exclusive")
    if args.benchmark == "bfcl" and not args.models:
        p.error("--models is required with --benchmark bfcl")
    return args


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


def _build_default_verifier() -> VerifierFn:
    """Build the LLM verifier callable used for entity_questions / triviaqa.

    Shares one Anthropic client across all verifier calls in a run. Fails
    fast if ANTHROPIC_API_KEY isn't loaded.
    """
    import anthropic  # type: ignore[import-not-found]
    from ci_wiki.config import Config
    cfg = Config.from_env()
    if not cfg.anthropic_api_key:
        raise RuntimeError(
            "QA-corpus loaders require ANTHROPIC_API_KEY for the LLM verifier."
        )
    client = anthropic.Anthropic(api_key=cfg.anthropic_api_key, max_retries=3)

    def verifier(question: str, entity_key: tuple[str, str]) -> bool:
        slug, page_type = entity_key
        return llm_verify(
            question, slug, page_type, anthropic_client=client,
        )

    return verifier


def assemble_cases(
    *,
    repo_root: Path,
    datasets: list[str],
    n_samples: int,
    seed: int,
    verifier_fn: VerifierFn | None = None,
) -> list[BfclCase]:
    """Assemble the case pool from every requested dataset.

    `verifier_fn` is passed through to QA-corpus loaders when set. When None
    AND the datasets list includes 'entity_questions' or 'triviaqa', a real
    Anthropic-backed verifier is built (defensive default). Tests explicitly
    pass a stub verifier_fn to keep the network out of the loop.
    """
    for d in datasets:
        if d not in _VALID_DATASETS:
            raise ValueError(f"Unknown dataset: {d!r}. Valid: {_VALID_DATASETS}")
    needs_verifier = "entity_questions" in datasets or "triviaqa" in datasets
    if needs_verifier and verifier_fn is None:
        verifier_fn = _build_default_verifier()
    entity_index = EntityIndex.from_wiki(repo_root / "wiki")
    pool: list[BfclCase] = []
    if "fixtures" in datasets:
        pool.extend(load_committed_fixtures(repo_root=repo_root))
    if "entity_questions" in datasets:
        pool.extend(load_entity_questions(
            entity_index=entity_index, n_max=n_samples * 2,
            verifier_fn=verifier_fn,
        ))
    if "triviaqa" in datasets:
        pool.extend(load_triviaqa(
            entity_index=entity_index, n_max=n_samples * 2,
            verifier_fn=verifier_fn,
        ))
    if "synthesized" in datasets:
        # Grow the trustworthy pool by deriving `multiple` + `irrelevance`
        # variants from the hand-curated fixtures. Ground truth stays valid
        # because the source cases are hand-authored, unlike QA-corpus mining.
        base = load_committed_fixtures(repo_root=repo_root)
        simple_bases = [c for c in base if c.category == "simple"]
        synth = Synthesizer(seed=seed)
        pool.extend(synth.to_multiple(simple_bases, n_distractors=3))
        pool.extend(synth.to_irrelevance(
            _OFF_TOPIC_QUESTIONS,
            tools_subset=["read_wiki_page", "search_wiki", "list_wiki_pages"],
        ))
    # Dedupe by (question, category, sorted-functions). Question alone would
    # collapse synthesizer variants (a `multiple` case built from a `simple`
    # fixture reuses the question but tests a different capability).
    seen: set[tuple] = set()
    deduped: list[BfclCase] = []
    for c in pool:
        k = (c.question.strip().lower(), c.category, tuple(sorted(c.functions)))
        if k in seen:
            continue
        seen.add(k)
        deduped.append(c)
    rng = random.Random(seed)
    rng.shuffle(deduped)
    return deduped[:n_samples]


def _run_finqa(args: argparse.Namespace, repo_root: Path) -> int:
    """Single-dataset FinQA mode: load, run the agent, score, write results."""
    from benchmarks.runner import finqa_evaluator as evaluator
    from benchmarks.runner.datasets import finqa as _finqa
    from benchmarks.runner.finqa_agent import FinqaAgent
    from ci_wiki.config import Config
    from ci_wiki.llm.client import LLMClient

    tickers = (
        frozenset(t.strip().upper() for t in args.tickers.split(",") if t.strip())
        if args.tickers else _finqa.SEEDED_TICKERS
    )
    cases = _finqa.load(n=args.n, tickers=tickers)
    log.info("finqa: loaded %d case(s) across %d ticker(s)", len(cases), len(tickers))

    config = Config.from_env(repo_root=repo_root)
    llm = LLMClient(config)
    wiki_dir = repo_root / "wiki"
    agent = FinqaAgent(llm_client=llm, wiki_dir=wiki_dir)

    per_case = []
    n_correct = 0
    total_tool_calls = 0
    for case in cases:
        record = agent.answer(case)
        result = evaluator.score(case, record.parsed_value, record.parsed_unit, record.parse_error)
        per_case.append({
            "id": case.id,
            "ticker": case.ticker,
            "question": case.question,
            "gold_raw": case.gold_answer_raw,
            "gold_value": case.gold_answer_value,
            "gold_unit": case.gold_answer_unit,
            "pred_text": record.final_text,
            "pred_value": record.parsed_value,
            "pred_unit": record.parsed_unit,
            "parse_error": record.parse_error,
            "correct": result.correct,
            "reason": result.reason,
            "tool_call_count": record.tool_call_count,
            "latency_s": record.latency_s,
        })
        n_correct += int(result.correct)
        total_tool_calls += record.tool_call_count

    summary = {
        "n": len(cases),
        "accuracy": (n_correct / len(cases)) if cases else 0.0,
        "mean_tool_calls": (total_tool_calls / len(cases)) if cases else 0.0,
        "per_case": per_case,
    }
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = repo_root / "benchmarks" / "runner" / "results" / f"finqa-{ts}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    print(f"finqa: {n_correct}/{len(cases)} correct ({summary['accuracy']:.1%})  ->  {out}")
    return 0


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    args = parse_args(argv)
    repo_root = _repo_root()

    if args.dataset == "finqa":
        return _run_finqa(args, repo_root)

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
