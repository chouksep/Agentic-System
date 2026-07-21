"""Render a MultiModelResults into summary.json + report.md."""
from __future__ import annotations

import dataclasses
import json
from pathlib import Path

from benchmarks.runner.types import ModelResult, MultiModelResults


def render(results: MultiModelResults, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    _write_summary_json(results, out_dir / "summary.json")
    _write_report_md(results, out_dir / "report.md")


def _write_summary_json(results: MultiModelResults, path: Path) -> None:
    data = {
        "run_id": results.run_id,
        "cases_evaluated": results.cases_evaluated,
        "partial": results.partial,
        "reason": results.reason,
        "models": [dataclasses.asdict(m) for m in results.models],
    }
    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")


def _write_report_md(results: MultiModelResults, path: Path) -> None:
    lines: list[str] = []
    lines.append(f"# Benchmark run `{results.run_id}`")
    lines.append("")
    if results.partial:
        lines.append(f"> **PARTIAL** — {results.reason or 'aborted before completion'}")
        lines.append("")
    lines.append(f"Cases evaluated: **{results.cases_evaluated}**")
    lines.append("")
    lines.append("## Per-model summary")
    lines.append("")
    lines.append("| model | accuracy | cost (USD) | tokens | p50 lat (s) | p95 lat (s) | agent_errors |")
    lines.append("|---|---|---|---|---|---|---|")
    for m in results.models:
        lines.append(
            f"| `{m.model_id}` | {m.accuracy:.1%} ({m.accuracy:.3f}) | "
            f"${m.total_cost_usd:.4f} | {m.total_tokens} | "
            f"{m.p50_latency:.2f} | {m.p95_latency:.2f} | {m.agent_errors} |"
        )
    lines.append("")
    diff_rows = _disagreements(results.models)
    if diff_rows:
        lines.append("## Disagreements")
        lines.append("")
        lines.append("Cases where any model pair produced different `valid` outcomes.")
        lines.append("")
        header = "| case_id | category | " + " | ".join(m.model_id for m in results.models) + " |"
        sep = "|---|---|" + "---|" * len(results.models)
        lines.append(header)
        lines.append(sep)
        for row in diff_rows:
            cells = " | ".join(_short(row["per_model"][m.model_id]) for m in results.models)
            lines.append(f"| `{row['id']}` | {row['category']} | {cells} |")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _short(case_result: dict | None) -> str:
    if case_result is None:
        return "—"
    if case_result.get("valid"):
        return "✓"
    return f"✗ {case_result.get('error_type', '?')}"


def _disagreements(models: list[ModelResult]) -> list[dict]:
    """Return rows for cases where any pair of models disagreed on `valid`."""
    if len(models) < 2:
        return []
    by_case: dict[str, dict] = {}
    for m in models:
        for c in m.per_case:
            entry = by_case.setdefault(c["id"], {"id": c["id"], "category": c["category"], "per_model": {}})
            entry["per_model"][m.model_id] = c
    out: list[dict] = []
    for entry in by_case.values():
        valids = {entry["per_model"].get(m.model_id, {}).get("valid") for m in models}
        if len(valids) > 1:
            out.append(entry)
    out.sort(key=lambda e: e["id"])
    return out
