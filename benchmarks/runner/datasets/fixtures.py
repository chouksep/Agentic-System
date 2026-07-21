"""Loader for benchmarks/bfcl-faithful/test_cases.json.

Surfaces the committed cases as BfclCase instances so the runner can mix them
with QA-corpus-sourced cases under one --datasets flag.
"""
from __future__ import annotations

import json
from pathlib import Path

from benchmarks.runner.datasets.base import BfclCase


def load_committed_fixtures(*, repo_root: Path) -> list[BfclCase]:
    path = repo_root / "benchmarks" / "bfcl-faithful" / "test_cases.json"
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    return [
        BfclCase(
            id=tc["id"],
            category=tc["category"],
            functions=tc["functions"],
            question=tc["question"],
            possible_answer=tc["possible_answer"],
        )
        for tc in data["test_cases"]
    ]
