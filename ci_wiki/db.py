from __future__ import annotations

import json
import sqlite3
from datetime import datetime, UTC
from pathlib import Path

from ci_wiki.models import IngestResult, Source, WikiPage


_SCHEMA = """
CREATE TABLE IF NOT EXISTS sources (
    id TEXT PRIMARY KEY,
    uri TEXT NOT NULL,
    source_type TEXT NOT NULL,
    ingested_at TEXT,
    status TEXT DEFAULT 'pending',
    error TEXT,
    raw_text_path TEXT
);

CREATE TABLE IF NOT EXISTS wiki_pages (
    slug TEXT PRIMARY KEY,
    page_type TEXT NOT NULL,
    file_path TEXT NOT NULL,
    created_at TEXT,
    last_updated TEXT,
    source_count INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS ingest_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id TEXT NOT NULL,
    run_at TEXT NOT NULL,
    pages_created TEXT,
    pages_updated TEXT,
    tokens_used INTEGER,
    duration_s REAL,
    error TEXT
);
"""


class Database:
    def __init__(self, db_path: Path | str) -> None:
        self._path = str(db_path)
        self._conn: sqlite3.Connection | None = None

    def connect(self) -> None:
        self._conn = sqlite3.connect(self._path)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    def __enter__(self) -> "Database":
        self.connect()
        return self

    def __exit__(self, *_) -> None:
        self.close()

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            raise RuntimeError("Database not connected. Use as context manager or call connect().")
        return self._conn

    # --- sources ---

    def is_ingested(self, content_hash: str) -> bool:
        row = self.conn.execute(
            "SELECT status FROM sources WHERE id = ?", (content_hash,)
        ).fetchone()
        return row is not None and row["status"] == "ingested"

    def get_source(self, content_hash: str) -> Source | None:
        row = self.conn.execute(
            "SELECT * FROM sources WHERE id = ?", (content_hash,)
        ).fetchone()
        if row is None:
            return None
        return self._row_to_source(row)

    def upsert_source(self, source: Source) -> None:
        self.conn.execute(
            """INSERT INTO sources (id, uri, source_type, ingested_at, status, error)
               VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(id) DO UPDATE SET
                   status=excluded.status,
                   ingested_at=excluded.ingested_at,
                   error=excluded.error""",
            (
                source.id,
                source.uri,
                source.source_type,
                source.ingested_at.isoformat() if source.ingested_at else None,
                source.status,
                source.error,
            ),
        )
        self.conn.commit()

    def mark_ingested(self, source: Source, result: IngestResult) -> None:
        now = datetime.now(UTC).replace(tzinfo=None).isoformat()
        self.conn.execute(
            """UPDATE sources SET status='ingested', ingested_at=?, error=NULL WHERE id=?""",
            (now, source.id),
        )
        self.conn.execute(
            """INSERT INTO ingest_log (source_id, run_at, pages_created, pages_updated, tokens_used, duration_s, error)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                source.id,
                now,
                json.dumps(result.pages_created),
                json.dumps(result.pages_updated),
                result.tokens_used,
                result.duration_s,
                result.error,
            ),
        )
        self.conn.commit()

    def mark_failed(self, source: Source, error: str) -> None:
        self.conn.execute(
            """UPDATE sources SET status='failed', error=? WHERE id=?""",
            (error, source.id),
        )
        self.conn.commit()

    def get_pending_sources(self) -> list[Source]:
        rows = self.conn.execute(
            "SELECT * FROM sources WHERE status IN ('pending', 'failed') ORDER BY rowid"
        ).fetchall()
        return [self._row_to_source(r) for r in rows]

    def _row_to_source(self, row: sqlite3.Row) -> Source:
        return Source(
            id=row["id"],
            uri=row["uri"],
            source_type=row["source_type"],
            raw_text="",  # not stored in DB; re-fetched if needed
            ingested_at=datetime.fromisoformat(row["ingested_at"]) if row["ingested_at"] else None,
            status=row["status"],
            error=row["error"],
        )

    # --- wiki_pages ---

    def upsert_page(self, page: WikiPage) -> None:
        now = datetime.now(UTC).replace(tzinfo=None).isoformat()
        existing = self.conn.execute(
            "SELECT created_at FROM wiki_pages WHERE slug = ?", (page.slug,)
        ).fetchone()
        created_at = existing["created_at"] if existing else now

        sources_list = page.frontmatter.get("sources", []) or []
        self.conn.execute(
            """INSERT INTO wiki_pages (slug, page_type, file_path, created_at, last_updated, source_count)
               VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(slug) DO UPDATE SET
                   page_type=excluded.page_type,
                   file_path=excluded.file_path,
                   last_updated=excluded.last_updated,
                   source_count=excluded.source_count""",
            (
                page.slug,
                page.page_type,
                str(page.path),
                created_at,
                page.last_updated.isoformat() if page.last_updated else now,
                len(sources_list),
            ),
        )
        self.conn.commit()

    def get_all_slugs(self) -> list[str]:
        rows = self.conn.execute("SELECT slug FROM wiki_pages ORDER BY slug").fetchall()
        return [r["slug"] for r in rows]

    def get_page_meta(self, slug: str) -> dict | None:
        row = self.conn.execute(
            "SELECT * FROM wiki_pages WHERE slug = ?", (slug,)
        ).fetchone()
        return dict(row) if row else None

    def get_stats(self) -> dict:
        sources_total = self.conn.execute("SELECT COUNT(*) FROM sources").fetchone()[0]
        sources_ingested = self.conn.execute(
            "SELECT COUNT(*) FROM sources WHERE status='ingested'"
        ).fetchone()[0]
        sources_pending = self.conn.execute(
            "SELECT COUNT(*) FROM sources WHERE status='pending'"
        ).fetchone()[0]
        pages_total = self.conn.execute("SELECT COUNT(*) FROM wiki_pages").fetchone()[0]
        last_ingest = self.conn.execute(
            "SELECT MAX(run_at) FROM ingest_log"
        ).fetchone()[0]
        return {
            "sources_total": sources_total,
            "sources_ingested": sources_ingested,
            "sources_pending": sources_pending,
            "pages_total": pages_total,
            "last_ingest": last_ingest,
        }
