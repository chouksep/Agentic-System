"""Comparator — orchestrates models x cases through the agent + cache.

Two phases:
  1. run_agent_phase: for each (model, case), get an AgentRecord from cache or
     by invoking the agent_factory. Track cumulative cost; abort with
     CostCeilingExceeded before exceeding max_cost.
  2. run_evaluation_phase: for each model, write predictions + test-cases
     slice JSON and shell out to bfcl-faithful/evaluate.py, then aggregate
     per-model results into MultiModelResults.

Splitting the phases keeps agent-phase failures (network) recoverable
without re-paying — the cache preserves progress.
"""
from __future__ import annotations

import json
import logging
import statistics
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Protocol

from benchmarks.runner.cache import Cache, build_key
from benchmarks.runner.datasets.base import BfclCase
from benchmarks.runner.types import AgentRecord, ModelResult, MultiModelResults
from benchmarks.runner.version import RUNNER_VERSION

log = logging.getLogger(__name__)


class CostCeilingExceeded(RuntimeError):
    """Raised when cumulative cost would exceed --max-cost before the next call."""


class _AgentLike(Protocol):
    def run_case(self, case: BfclCase) -> AgentRecord: ...


_BFCL_EVAL_SCRIPT = "benchmarks/bfcl-faithful/evaluate.py"
_SLICE_META = {
    "benchmark": "BFCL (Berkeley Function Calling Leaderboard)",
    "source_repo": "https://github.com/ShishirPatil/gorilla",
    "generated_by": f"benchmarks.runner v{RUNNER_VERSION}",
    "notes": "Sampled subset emitted by benchmarks.runner — see summary.json for provenance.",
}


def _tools_schema_hash(case: BfclCase) -> str:
    return json.dumps(sorted(case.functions), separators=(",", ":"))


@dataclass
class Comparator:
    cache: Cache

    def run_agent_phase(
        self,
        *,
        models: list[str],
        cases: list[BfclCase],
        agent_factory: Callable[[str], _AgentLike],
        max_cost: float,
    ) -> dict[str, dict[str, AgentRecord]]:
        """Returns {model_id: {case_id: AgentRecord}} populated for every (model, case).

        Raises CostCeilingExceeded the first time the next predicted call would
        push cumulative cost past `max_cost`. Already-completed records remain
        in the cache.
        """
        records: dict[str, dict[str, AgentRecord]] = {m: {} for m in models}
        total_cost = 0.0
        for model_id in models:
            runner = agent_factory(model_id)
            for case in cases:
                key = build_key(
                    model_id=model_id,
                    case_id=case.id,
                    tools_schema=_tools_schema_hash(case),
                )
                # Check cache first: a hit costs $0 and never trips the ceiling.
                cell_path = self.cache._path_for_key(key)
                if not cell_path.exists() and total_cost >= max_cost:
                    raise CostCeilingExceeded(
                        f"cumulative cost ${total_cost:.4f} reached max_cost "
                        f"${max_cost:.4f} before model={model_id} case={case.id}"
                    )
                record = self.cache.get_or_compute(key, lambda c=case: runner.run_case(c))
                records[model_id][case.id] = record
                total_cost += record.cost_usd
        return records

    @staticmethod
    def emit_predictions(case_records: dict[str, AgentRecord], path: Path) -> None:
        data = {case_id: rec.calls for case_id, rec in case_records.items()}
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")

    @staticmethod
    def emit_test_cases_slice(cases: list[BfclCase], path: Path) -> None:
        data = {
            "_meta": _SLICE_META,
            "test_cases": [c.to_dict() for c in cases],
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")

    def run_evaluation_phase(
        self,
        *,
        repo_root: Path,
        records: dict[str, dict[str, AgentRecord]],
        cases: list[BfclCase],
        run_dir: Path,
    ) -> MultiModelResults:
        """For each model: write preds + slice, invoke evaluate.py, aggregate."""
        run_id = run_dir.name
        out_models: list[ModelResult] = []
        slice_path = run_dir / "test_cases_slice.json"
        self.emit_test_cases_slice(cases, slice_path)

        for model_id, case_records in records.items():
            pred_path = run_dir / "predictions" / f"{model_id}.json"
            self.emit_predictions(case_records, pred_path)
            results_path = run_dir / "evaluator_out" / f"{model_id}.json"
            results_path.parent.mkdir(parents=True, exist_ok=True)
            cmd = [
                sys.executable,
                str(repo_root / _BFCL_EVAL_SCRIPT),
                "--test-cases", str(slice_path),
                "--predictions", str(pred_path),
                "--output", str(results_path),
            ]
            log.info("evaluator: %s", " ".join(cmd))
            subprocess.run(cmd, check=True)
            results = json.loads(results_path.read_text(encoding="utf-8"))
            out_models.append(self._build_model_result(model_id, case_records, results))

        return MultiModelResults(
            run_id=run_id,
            models=out_models,
            cases_evaluated=len(cases),
        )

    @staticmethod
    def _build_model_result(
        model_id: str,
        case_records: dict[str, AgentRecord],
        eval_out: dict,
    ) -> ModelResult:
        latencies = [r.latency_seconds for r in case_records.values()]
        latencies_sorted = sorted(latencies)
        p50 = statistics.median(latencies_sorted) if latencies_sorted else 0.0
        p95 = _percentile(latencies_sorted, 0.95)
        return ModelResult(
            model_id=model_id,
            per_case=eval_out.get("per_case", []),
            accuracy=eval_out.get("overall", {}).get("accuracy", 0.0),
            total_cost_usd=sum(r.cost_usd for r in case_records.values()),
            total_tokens=sum(r.tokens_used for r in case_records.values()),
            p50_latency=p50,
            p95_latency=p95,
            agent_errors=sum(1 for r in case_records.values() if r.error),
        )


def _percentile(sorted_values: list[float], q: float) -> float:
    if not sorted_values:
        return 0.0
    if len(sorted_values) == 1:
        return sorted_values[0]
    idx = min(len(sorted_values) - 1, int(q * len(sorted_values)))
    return sorted_values[idx]
