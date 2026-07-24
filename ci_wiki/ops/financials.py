"""Financial data sidecar loader + validator.

Two-layer validation for wiki/companies/<slug>.financials.yaml files:
- Layer 1: JSON Schema Draft 2020-12 structural checks
- Layer 2: Python-level cross-consistency rules

Public API (implemented across subsequent tasks):
- load_sidecar(path) -> dict
- validate(data) -> list[str]
- find_and_validate_all(wiki_root) -> dict[Path, list[str]]

See docs/superpowers/specs/2026-07-24-finance-wiki-data-model-design.md
for the schema and validation rules.
"""
from __future__ import annotations
