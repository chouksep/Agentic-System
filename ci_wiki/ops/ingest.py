"""Ingest operation: fetch source → parse → LLM tool loop → update wiki + DB."""
from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path

from ci_wiki.config import Config
from ci_wiki.db import Database
from ci_wiki.llm.client import LLMClient
from ci_wiki.llm.prompts import build_ingest_system_prompt, build_ingest_user_prompt, load_schema
from ci_wiki.llm.tools import INGEST_TOOLS, ToolDispatcher
from ci_wiki.models import IngestResult, LogEntry, Source
from ci_wiki.sources.fetcher import Fetcher
from ci_wiki.sources.parsers import Parser
from ci_wiki.sources.watcher import SourceWatcher
from ci_wiki.wiki.index import WikiIndex
from ci_wiki.wiki.page import WikiPageIO
from ci_wiki.wiki.search import WikiSearch


class IngestOp:
    def __init__(
        self,
        config: Config,
        db: Database,
        llm: LLMClient,
        page_io: WikiPageIO,
        index: WikiIndex,
    ) -> None:
        self._config = config
        self._db = db
        self._llm = llm
        self._page_io = page_io
        self._index = index
        self._fetcher = Fetcher()
        self._parser = Parser()

    def run_source(self, source: Source) -> IngestResult:
        """Ingest a single source. Returns IngestResult."""
        start = time.monotonic()
        result = IngestResult(source_id=source.id)

        try:
            source_text = self._prepare_text(source)
            final_text, tokens, pages_created, pages_updated = self._run_llm(
                source_text, source.uri
            )
            result.pages_created = pages_created
            result.pages_updated = pages_updated
            result.tokens_used = tokens

            self._db.mark_ingested(source, result)
            self._post_process(result, source.uri)

        except Exception as e:
            result.error = str(e)
            self._db.mark_failed(source, str(e))

        result.duration_s = time.monotonic() - start
        return result

    def run_url(self, url: str) -> IngestResult:
        """Fetch a URL and ingest it."""
        watcher = SourceWatcher(self._config.sources_dir, self._db)
        source = watcher.add_url(url)
        if source.status == "ingested":
            print(f"Already ingested: {url}")
            return IngestResult(source_id=source.id, error="already ingested")
        return self.run_source(source)

    def run_file(self, path: Path) -> IngestResult:
        """Ingest a local file."""
        watcher = SourceWatcher(self._config.sources_dir, self._db)
        source = watcher.add_file(path)
        if source.status == "ingested":
            print(f"Already ingested: {path}")
            return IngestResult(source_id=source.id, error="already ingested")
        return self.run_source(source)

    def run_all_pending(self) -> list[IngestResult]:
        """Ingest all pending sources from the DB + sources/ directory."""
        # Scan the sources/ directory for new files
        watcher = SourceWatcher(self._config.sources_dir, self._db)
        watcher.scan_directory()

        pending = self._db.get_pending_sources()
        results = []
        for source in pending:
            # Re-fetch raw text for file sources
            if source.source_type == "file":
                try:
                    source.raw_text = Path(source.uri).read_text(encoding="utf-8", errors="replace")
                except Exception:
                    pass
            print(f"  Ingesting: {source.uri[:80]}")
            result = self.run_source(source)
            results.append(result)
            self._print_result(result)
        return results

    def _prepare_text(self, source: Source) -> str:
        """Return plain text for the source, fetching if needed."""
        if source.raw_text:
            return source.raw_text

        # Re-fetch from URI
        if source.source_type == "url":
            raw = self._fetcher.fetch_url(source.uri)
            return self._parser.parse(raw)
        elif source.source_type == "file":
            path = Path(source.uri)
            if path.exists():
                return path.read_text(encoding="utf-8", errors="replace")
        return ""

    def _run_llm(
        self, source_text: str, source_uri: str
    ) -> tuple[str, int, list[str], list[str]]:
        """Run the LLM ingest loop. Returns (text, tokens, created_slugs, updated_slugs)."""
        schema = load_schema(self._config.schema_file)
        system = build_ingest_system_prompt(schema)
        existing_slugs = self._db.get_all_slugs()
        user_msg = build_ingest_user_prompt(source_text, source_uri, existing_slugs)

        pages = self._page_io.read_all()
        search = WikiSearch(pages)
        search.build_index()

        dispatcher = ToolDispatcher(self._page_io, search)
        final_text, tokens = self._llm.complete_with_tools(
            system=system,
            initial_user_message=user_msg,
            tools=INGEST_TOOLS,
            dispatcher=dispatcher,
        )

        # Register newly created pages in DB
        for slug in dispatcher.pages_created + dispatcher.pages_updated:
            try:
                # Find the page type by searching all type dirs
                for ptype in ("company", "product", "person", "trend"):
                    if self._page_io.exists(slug, ptype):
                        page = self._page_io.read_by_slug(slug, ptype)
                        self._db.upsert_page(page)
                        break
            except Exception:
                pass

        return final_text, tokens, dispatcher.pages_created, dispatcher.pages_updated

    def _post_process(self, result: IngestResult, source_uri: str) -> None:
        all_changed = result.pages_created + result.pages_updated
        if all_changed:
            self._index.update(result.pages_created, result.pages_updated)
        self._index.append_log(
            LogEntry(
                operation="Ingest",
                timestamp=datetime.utcnow(),
                source_uri=source_uri,
                pages_created=result.pages_created,
                pages_updated=result.pages_updated,
                tokens_used=result.tokens_used,
            )
        )

    @staticmethod
    def _print_result(result: IngestResult) -> None:
        if result.error and result.error != "already ingested":
            print(f"    ERROR: {result.error}")
        else:
            created = ", ".join(result.pages_created) or "none"
            updated = ", ".join(result.pages_updated) or "none"
            print(
                f"    Created: [{created}]  Updated: [{updated}]  "
                f"Tokens: {result.tokens_used:,}  Time: {result.duration_s:.1f}s"
            )
