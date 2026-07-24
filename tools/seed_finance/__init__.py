"""One-shot tooling for seeding real financial data into wiki/companies/*.financials.yaml.

See docs/superpowers/specs/2026-07-24-finance-wiki-seed-data-p2-design.md.
"""
from __future__ import annotations

from tools.seed_finance.run import SeedResult, seed

__all__ = ["seed", "SeedResult"]
