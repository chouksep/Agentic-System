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
