from __future__ import annotations

import hashlib
from pathlib import Path

from ci_wiki.db import Database
from ci_wiki.models import Source
from ci_wiki.sources.fetcher import Fetcher
from ci_wiki.sources.parsers import Parser


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class SourceWatcher:
    def __init__(self, sources_dir: Path, db: Database) -> None:
        self._sources_dir = sources_dir
        self._db = db
        self._fetcher = Fetcher()
        self._parser = Parser()

    def scan_directory(self) -> list[Source]:
        """Walk sources/ dir, hash content, return new (not-yet-ingested) Sources.

        Deduplicates by content hash: if two files have identical content, only
        the first (alphabetically) is returned and registered.
        """
        new_sources: list[Source] = []
        seen_hashes: set[str] = set()

        for path in sorted(self._sources_dir.rglob("*")):
            if not path.is_file():
                continue
            if path.name.startswith("."):
                continue
            try:
                raw_text = path.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue

            content_id = _hash(raw_text)

            # Skip if already processed in this scan pass or fully ingested
            if content_id in seen_hashes or self._db.is_ingested(content_id):
                continue
            seen_hashes.add(content_id)

            source = Source(
                id=content_id,
                uri=str(path),
                source_type="file",
                raw_text=raw_text,
                status="pending",
            )
            existing = self._db.get_source(content_id)
            if existing is None:
                self._db.upsert_source(source)
            new_sources.append(source)

        return new_sources

    def add_url(self, url: str) -> Source:
        """Fetch a URL, hash content, register as a pending Source."""
        raw = self._fetcher.fetch_url(url)
        parsed_text = self._parser.parse(raw)
        content_id = _hash(parsed_text)

        source = Source(
            id=content_id,
            uri=url,
            source_type="url",
            raw_text=parsed_text,
            status="pending",
        )
        existing = self._db.get_source(content_id)
        if existing is not None and existing.status == "ingested":
            source.status = "ingested"
            return source

        self._db.upsert_source(source)
        return source

    def add_file(self, path: Path) -> Source:
        """Read a local file and register it as a pending Source."""
        raw_text = path.read_text(encoding="utf-8", errors="replace")
        content_id = _hash(raw_text)

        source = Source(
            id=content_id,
            uri=str(path),
            source_type="file",
            raw_text=raw_text,
            status="pending",
        )
        existing = self._db.get_source(content_id)
        if existing is not None and existing.status == "ingested":
            source.status = "ingested"
            return source

        self._db.upsert_source(source)
        return source
