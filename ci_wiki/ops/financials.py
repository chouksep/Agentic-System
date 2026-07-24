"""Financial data sidecar loader + validator.

Two-layer validation for wiki/companies/<slug>.financials.yaml files:
- Layer 1: JSON Schema Draft 2020-12 structural checks
- Layer 2: Python-level cross-consistency rules (added in Task 3)

Public API:
- load_sidecar(path) -> dict
- validate(data) -> list[str]                  (composed in Task 4)
- find_and_validate_all(wiki_root) -> dict     (added in Task 4)

See docs/superpowers/specs/2026-07-24-finance-wiki-data-model-design.md.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

_SCHEMA_PATH = (
    Path(__file__).resolve().parents[2] / "schema" / "financials_sidecar.schema.json"
)


@lru_cache(maxsize=1)
def _load_schema() -> dict:
    """Load and cache the JSON Schema document from disk."""
    return json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))


def load_sidecar(path: Path) -> dict:
    """Load a sidecar YAML file into a plain dict."""
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


def _check_json_schema(data: dict) -> list[str]:
    """Return a list of JSON Schema violation messages (empty when valid)."""
    validator = Draft202012Validator(_load_schema())
    return [
        # Include the JSON pointer path so callers can locate errors.
        f"{'/'.join(str(p) for p in e.absolute_path) or '<root>'}: {e.message}"
        for e in validator.iter_errors(data)
    ]


def _check_cross_consistency(data: dict) -> list[str]:
    """Return a list of cross-consistency violation messages (empty when valid).

    Rules (spec section 6):
      1. Every metric in metadata appears in at least one by_period.
      2. Every metric in any by_period has a metadata entry.
      3. filings[].period_covered references a key in by_period.
      4. Every row in filings[].tables[].rows has len == len(header).
      5. filings[].id values are unique.

    Assumes Layer-1 (JSON Schema) has already passed. If input is malformed
    (e.g., metrics missing), returns a single error string rather than raising.
    """
    errors: list[str] = []

    metrics = data.get("metrics")
    if not isinstance(metrics, dict):
        return ["metrics: missing or not an object (Layer 1 should have caught this)"]

    by_period = metrics.get("by_period") or {}
    metadata = metrics.get("metadata") or {}

    used_metric_names: set[str] = set()
    for _period, period_metrics in by_period.items():
        if isinstance(period_metrics, dict):
            used_metric_names.update(period_metrics.keys())
    documented_metric_names: set[str] = set(metadata.keys())

    # Rule 1: metadata -> by_period
    for name in sorted(documented_metric_names - used_metric_names):
        errors.append(
            f"metrics.metadata.{name}: documented but never used in any by_period (rule 1)"
        )
    # Rule 2: by_period -> metadata
    for name in sorted(used_metric_names - documented_metric_names):
        errors.append(
            f"metrics.by_period: metric {name!r} appears in a period but has no metadata entry (rule 2)"
        )

    filings = data.get("filings") or []

    # Rule 3: period_covered orphan check
    period_keys = set(by_period.keys())
    for i, f in enumerate(filings):
        pc = (f or {}).get("period_covered")
        if pc and pc not in period_keys:
            errors.append(
                f"filings[{i}].period_covered: {pc!r} does not exist in metrics.by_period (rule 3)"
            )

    # Rule 4: table row shape
    for i, f in enumerate(filings):
        for j, table in enumerate((f or {}).get("tables") or []):
            header = table.get("header") or []
            width = len(header)
            for r, row in enumerate(table.get("rows") or []):
                if len(row) != width:
                    errors.append(
                        f"filings[{i}].tables[{j}].rows[{r}]: {len(row)} column(s) "
                        f"but header has {width} (rule 4)"
                    )

    # Rule 5: unique filing ids
    seen_ids: dict[str, int] = {}
    for i, f in enumerate(filings):
        fid = (f or {}).get("id")
        if not fid:
            continue
        if fid in seen_ids:
            errors.append(
                f"filings[{i}].id: duplicate id {fid!r} (also at filings[{seen_ids[fid]}]) (rule 5)"
            )
        else:
            seen_ids[fid] = i

    return errors
