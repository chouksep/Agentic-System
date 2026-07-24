"""One-shot tooling for seeding real financial data into wiki/companies/*.financials.yaml.

See docs/superpowers/specs/2026-07-24-finance-wiki-seed-data-p2-design.md.

Not part of ci_wiki runtime — this is ops tooling. `python -m tools.seed_finance`
fetches SEC EDGAR data and writes schema-valid sidecars.
"""
from __future__ import annotations
