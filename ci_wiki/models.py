from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


@dataclass
class Source:
    id: str                        # SHA-256 of normalized content
    uri: str                       # file path or URL
    source_type: str               # "url", "file", "rss"
    raw_text: str
    ingested_at: datetime | None = None
    status: str = "pending"        # pending | ingested | failed | skipped
    error: str | None = None


@dataclass
class WikiPage:
    path: Path
    slug: str
    page_type: str                 # company | product | person | trend
    frontmatter: dict
    body: str                      # everything after frontmatter
    last_updated: datetime | None = None


@dataclass
class IngestResult:
    source_id: str
    pages_created: list[str] = field(default_factory=list)
    pages_updated: list[str] = field(default_factory=list)
    tokens_used: int = 0
    duration_s: float = 0.0
    error: str | None = None


@dataclass
class QueryResult:
    question: str
    answer: str
    pages_consulted: list[str] = field(default_factory=list)
    tokens_used: int = 0
    filed_to: str | None = None    # wiki path if --save used


@dataclass
class LintIssue:
    severity: str                  # error | warning | info
    page_slug: str
    issue_type: str                # contradiction | stale | orphan | missing_xref | missing_section
    description: str
    auto_fixed: bool = False


@dataclass
class LogEntry:
    operation: str                 # Ingest | Query | Lint
    timestamp: datetime
    source_uri: str | None = None
    pages_created: list[str] = field(default_factory=list)
    pages_updated: list[str] = field(default_factory=list)
    tokens_used: int = 0
    notes: str | None = None
