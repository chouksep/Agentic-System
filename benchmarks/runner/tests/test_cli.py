"""Tests for the CLI entry point.

Verifies argument parsing + dataset-loading bootstrap. Does NOT exercise the
real LLM or HF; uses --datasets fixtures only (committed cases) with a fake
agent client.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from benchmarks.runner import __main__ as cli


def test_parse_args_basic():
    args = cli.parse_args([
        "--benchmark", "bfcl",
        "--models", "claude-sonnet-4-5,claude-sonnet-4-6",
        "--datasets", "fixtures",
        "--n-samples", "5",
        "--seed", "7",
        "--max-cost", "1.0",
    ])
    assert args.benchmark == "bfcl"
    assert args.models == ["claude-sonnet-4-5", "claude-sonnet-4-6"]
    assert args.datasets == ["fixtures"]
    assert args.n_samples == 5
    assert args.seed == 7
    assert args.max_cost == 1.0


def test_assemble_cases_fixtures_only(repo_root):
    cases = cli.assemble_cases(
        repo_root=repo_root, datasets=["fixtures"], n_samples=12, seed=0,
    )
    assert 1 <= len(cases) <= 12
    assert all(c.id for c in cases)


def test_assemble_cases_deterministic_with_seed(repo_root):
    a = cli.assemble_cases(repo_root=repo_root, datasets=["fixtures"], n_samples=5, seed=0)
    b = cli.assemble_cases(repo_root=repo_root, datasets=["fixtures"], n_samples=5, seed=0)
    assert [c.id for c in a] == [c.id for c in b]


def test_assemble_cases_synthesized_grows_pool_with_multiple_and_irrelevance(repo_root):
    """`synthesized` derives extra cases from fixtures deterministically."""
    fixtures_only = cli.assemble_cases(
        repo_root=repo_root, datasets=["fixtures"], n_samples=100, seed=0,
    )
    with_synth = cli.assemble_cases(
        repo_root=repo_root, datasets=["fixtures", "synthesized"], n_samples=100, seed=0,
    )
    assert len(with_synth) > len(fixtures_only)
    categories = {c.category for c in with_synth}
    assert "multiple" in categories
    assert "irrelevance" in categories
    # Determinism across two identical calls
    with_synth_2 = cli.assemble_cases(
        repo_root=repo_root, datasets=["fixtures", "synthesized"], n_samples=100, seed=0,
    )
    assert [c.id for c in with_synth] == [c.id for c in with_synth_2]


def test_parse_args_accepts_synthesized_flag():
    args = cli.parse_args([
        "--benchmark", "bfcl",
        "--models", "claude-sonnet-4-5",
        "--datasets", "fixtures,synthesized",
    ])
    assert args.datasets == ["fixtures", "synthesized"]


def test_main_runs_smoke_with_stub_factory(tmp_path, repo_root, monkeypatch):
    """End-to-end CLI dry-run: fixtures dataset + stub agent factory."""
    # Inject a stub agent_factory to avoid any real LLM.
    from benchmarks.runner.types import AgentRecord
    from benchmarks.runner.datasets.base import BfclCase

    def stub_factory(model_id):
        class _R:
            def run_case(self, case: BfclCase):
                # Echo the first possible_answer as the model's prediction.
                if not case.possible_answer:
                    calls = []
                else:
                    pa = case.possible_answer
                    first = pa[0]
                    func_name = next(iter(first))
                    args = {k: (v[0] if isinstance(v, list) and v else v) for k, v in first[func_name].items()}
                    calls = [{func_name: args}]
                return AgentRecord(calls=calls, tokens_used=10, cost_usd=0.0001)
        return _R()

    monkeypatch.setattr(cli, "default_agent_factory", lambda: stub_factory)

    out_dir = tmp_path / "run_out"
    exit_code = cli.main([
        "--benchmark", "bfcl",
        "--models", "claude-sonnet-4-5",
        "--datasets", "fixtures",
        "--n-samples", "3",
        "--seed", "0",
        "--max-cost", "1.0",
        "--output-dir", str(out_dir),
        "--cache-dir", str(tmp_path / "cache"),
    ])
    assert exit_code == 0
    assert (out_dir / "summary.json").exists()
    assert (out_dir / "report.md").exists()
    data = json.loads((out_dir / "summary.json").read_text(encoding="utf-8"))
    assert data["cases_evaluated"] == 3
    assert data["models"][0]["model_id"] == "claude-sonnet-4-5"
