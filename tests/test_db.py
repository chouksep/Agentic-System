from __future__ import annotations

import pytest
from pathlib import Path
from datetime import datetime

from ci_wiki.db import Database
from ci_wiki.models import Source, WikiPage, IngestResult


@pytest.fixture
def db(tmp_path):
    d = Database(":memory:")
    d.connect()
    yield d
    d.close()


def make_source(id="abc123", uri="http://example.com", status="pending"):
    return Source(id=id, uri=uri, source_type="url", raw_text="hello world", status=status)


def make_page(slug="openai", page_type="company", path=None):
    return WikiPage(
        path=path or Path(f"/wiki/companies/{slug}.md"),
        slug=slug,
        page_type=page_type,
        frontmatter={"name": slug, "sources": ["http://a.com"]},
        body="## Overview\nSome text.",
        last_updated=datetime(2026, 4, 8),
    )


def test_is_ingested_false_for_new_hash(db):
    assert db.is_ingested("nonexistent") is False


def test_upsert_source_and_get(db):
    src = make_source()
    db.upsert_source(src)
    retrieved = db.get_source("abc123")
    assert retrieved is not None
    assert retrieved.uri == "http://example.com"
    assert retrieved.status == "pending"


def test_mark_ingested_records_source(db):
    src = make_source()
    db.upsert_source(src)
    result = IngestResult(source_id="abc123", pages_created=["openai"], tokens_used=100)
    db.mark_ingested(src, result)
    assert db.is_ingested("abc123") is True


def test_get_pending_sources_excludes_ingested(db):
    src1 = make_source(id="a1", uri="http://a.com")
    src2 = make_source(id="a2", uri="http://b.com")
    db.upsert_source(src1)
    db.upsert_source(src2)
    result = IngestResult(source_id="a1")
    db.mark_ingested(src1, result)

    pending = db.get_pending_sources()
    assert len(pending) == 1
    assert pending[0].id == "a2"


def test_upsert_page_creates_and_updates(db):
    page = make_page()
    db.upsert_page(page)
    slugs = db.get_all_slugs()
    assert "openai" in slugs

    meta = db.get_page_meta("openai")
    assert meta["page_type"] == "company"
    assert meta["source_count"] == 1

    # update
    page.frontmatter["sources"] = ["http://a.com", "http://b.com"]
    db.upsert_page(page)
    meta2 = db.get_page_meta("openai")
    assert meta2["source_count"] == 2


def test_get_stats(db):
    src = make_source()
    db.upsert_source(src)
    page = make_page()
    db.upsert_page(page)

    stats = db.get_stats()
    assert stats["sources_total"] == 1
    assert stats["sources_pending"] == 1
    assert stats["pages_total"] == 1
    assert stats["sources_ingested"] == 0


def test_mark_failed(db):
    src = make_source()
    db.upsert_source(src)
    db.mark_failed(src, "connection timeout")
    retrieved = db.get_source("abc123")
    assert retrieved.status == "failed"
    assert retrieved.error == "connection timeout"
