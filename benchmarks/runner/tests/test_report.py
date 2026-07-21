"""Tests for report.render — JSON summary + markdown table."""
from __future__ import annotations

import json
from pathlib import Path

from benchmarks.runner.report import render
from benchmarks.runner.types import ModelResult, MultiModelResults


def _fixed_results() -> MultiModelResults:
    a = ModelResult(
        model_id="claude-sonnet-4-5",
        per_case=[
            {"id": "c1", "category": "simple", "valid": True, "error_type": "", "error": []},
            {"id": "c2", "category": "simple", "valid": False, "error_type": "type_error", "error": ["..."]},
        ],
        accuracy=0.5,
        total_cost_usd=0.123,
        total_tokens=4200,
        p50_latency=1.0,
        p95_latency=2.5,
        agent_errors=0,
    )
    b = ModelResult(
        model_id="claude-sonnet-4-6",
        per_case=[
            {"id": "c1", "category": "simple", "valid": True, "error_type": "", "error": []},
            {"id": "c2", "category": "simple", "valid": True, "error_type": "", "error": []},
        ],
        accuracy=1.0,
        total_cost_usd=0.155,
        total_tokens=4800,
        p50_latency=1.2,
        p95_latency=2.6,
        agent_errors=0,
    )
    return MultiModelResults(run_id="20260522T103000Z", models=[a, b], cases_evaluated=2)


def test_render_writes_summary_json_and_report_md(tmp_path):
    out_dir = tmp_path / "run"
    render(_fixed_results(), out_dir)
    summary_path = out_dir / "summary.json"
    md_path = out_dir / "report.md"
    assert summary_path.exists()
    assert md_path.exists()
    data = json.loads(summary_path.read_text(encoding="utf-8"))
    assert data["run_id"] == "20260522T103000Z"
    assert len(data["models"]) == 2


def test_report_md_contains_per_model_accuracy(tmp_path):
    out_dir = tmp_path / "run"
    render(_fixed_results(), out_dir)
    md = (out_dir / "report.md").read_text(encoding="utf-8")
    assert "claude-sonnet-4-5" in md
    assert "claude-sonnet-4-6" in md
    assert "50.0%" in md or "0.500" in md
    assert "100.0%" in md or "1.000" in md


def test_report_md_includes_diff_table_when_models_disagree(tmp_path):
    out_dir = tmp_path / "run"
    render(_fixed_results(), out_dir)
    md = (out_dir / "report.md").read_text(encoding="utf-8")
    # Models disagreed on c2 — should appear in the diff section.
    assert "Disagreements" in md
    assert "c2" in md
