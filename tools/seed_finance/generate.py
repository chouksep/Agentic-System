"""Compose sidecar YAML + minimal markdown stub for a seeded company.

build_sidecar returns a plain dict that MUST pass ci_wiki.ops.financials.validate.
build_stub_markdown returns a string with schema-compliant frontmatter +
placeholder section headers (bodies empty — LintOp will flag missing sections
as warnings for future human fill-in).
"""
from __future__ import annotations

from datetime import date


def build_sidecar(
    ticker: str,
    cik: str,
    metrics_by_period: dict[str, dict[str, float]],
    metric_metadata: dict[str, dict],
    filings: list[dict],
) -> dict:
    """Return the sidecar dict for a company, ready for yaml.safe_dump + validate."""
    sidecar: dict = {
        "schema_version": 1,
        "ticker": ticker,
        "cik": cik,
        "metrics": {
            "currency": "USD",
            "units": "millions",
            "by_period": metrics_by_period,
            "metadata": metric_metadata,
        },
    }
    if filings:
        sidecar["filings"] = filings
    return sidecar


_STUB_TEMPLATE = """\
---
name: "{name}"
type: company
last_updated: "{today}"
sources: []
---
# {name}

## Overview
<!-- 2-3 sentence summary — seeded by tools/seed_finance; requires human fill-in. -->

## Products & Services
<!-- Bullet list of key products / services / business lines. -->

## Pricing
<!-- Public pricing information if available. -->
<!-- confidence: low | source_count: 0 -->

## Funding & Financials
See structured data in `{slug}.financials.yaml`.

## Leadership
<!-- CEO, CTO, key executives: [[person:slug]] -->

## Competitive Position
<!-- Key competitors, strengths, weaknesses. -->

## Recent Developments
<!-- Reverse chronological, dated entries: - YYYY-MM-DD: ... -->

## Sources
<!-- Auto-maintained: list of source URIs that contributed to this page. -->
"""


def build_stub_markdown(slug: str, name: str) -> str:
    """Return a minimal wiki/companies/<slug>.md page.

    Bodies are placeholders — LintOp will flag missing_section warnings which
    signal to human curators that these need filling in. The `## Funding &
    Financials` section points at the sidecar file so readers know the
    structured data lives there.
    """
    return _STUB_TEMPLATE.format(
        name=name,
        today=date.today().isoformat(),
        slug=slug,
    )
