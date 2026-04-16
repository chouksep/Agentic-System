"""Query operation: BM25 pre-fetch → LLM reads wiki → synthesizes answer."""
from __future__ import annotations

import re
import unicodedata
from datetime import datetime, UTC
from pathlib import Path

from ci_wiki.config import Config
from ci_wiki.db import Database
from ci_wiki.llm.client import LLMClient
from ci_wiki.llm.prompts import build_query_system_prompt, build_query_user_prompt, load_schema
from ci_wiki.llm.tools import QUERY_TOOLS, ToolDispatcher
from ci_wiki.models import LogEntry, QueryResult
from ci_wiki.wiki.index import WikiIndex
from ci_wiki.wiki.page import WikiPageIO
from ci_wiki.wiki.search import WikiSearch


def _slugify(text: str) -> str:
    text = unicodedata.normalize("NFD", text.lower())
    text = re.sub(r"[^a-z0-9\s-]", "", text)
    text = re.sub(r"[\s]+", "-", text.strip())
    return text[:60]


class QueryOp:
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

    def run(self, question: str, save: bool = False, stream: bool = True) -> QueryResult:
        """Answer a competitive intelligence question from the wiki."""
        schema = load_schema(self._config.schema_file)
        system = build_query_system_prompt(schema)

        # BM25 pre-fetch for context hints
        pages = self._page_io.read_all()
        search = WikiSearch(pages)
        search.build_index()

        top_k = self._config.max_context_pages
        snippets = search.get_snippets(question, top_k=top_k, snippet_chars=400)
        page_summaries = self._format_summaries(snippets)

        user_msg = build_query_user_prompt(question, page_summaries)

        dispatcher = ToolDispatcher(self._page_io, search)
        final_text, tokens = self._llm.complete_with_tools(
            system=system,
            initial_user_message=user_msg,
            tools=QUERY_TOOLS,
            dispatcher=dispatcher,
        )

        pages_consulted = list(
            {tc for tc in (dispatcher.pages_created + dispatcher.pages_updated)}
        )
        # Also capture what was read (pages_created/updated not set for reads — use dispatch log)
        # We infer from search results for now
        if not pages_consulted:
            pages_consulted = [s["slug"] for s in snippets[:3]]

        result = QueryResult(
            question=question,
            answer=final_text,
            pages_consulted=pages_consulted,
            tokens_used=tokens,
        )

        if save:
            result.filed_to = self._save_to_wiki(result)

        self._index.append_log(
            LogEntry(
                operation="Query",
                timestamp=datetime.now(UTC).replace(tzinfo=None),
                notes=f"Q: {question[:80]}",
                tokens_used=tokens,
            )
        )

        return result

    def _format_summaries(self, snippets: list[dict]) -> str:
        if not snippets:
            return "_No relevant pages found in the wiki yet._"
        lines = []
        for s in snippets:
            lines.append(
                f"**[{s['page_type']}:{s['slug']}]** {s['name']}\n"
                f"  Score: {s['score']} | {s['snippet'][:200]}...\n"
            )
        return "\n".join(lines)

    def _save_to_wiki(self, result: QueryResult) -> str:
        """File the query result as a wiki page under wiki/queries/."""
        queries_dir = self._config.wiki_dir / "queries"
        queries_dir.mkdir(exist_ok=True)

        slug = _slugify(result.question)
        path = queries_dir / f"{slug}.md"
        now = datetime.now(UTC).replace(tzinfo=None).strftime("%Y-%m-%d")

        content = f"""---
question: "{result.question}"
type: query
answered: {now}
pages_consulted: [{', '.join(result.pages_consulted)}]
tokens_used: {result.tokens_used}
---
# Q: {result.question}

{result.answer}
"""
        path.write_text(content, encoding="utf-8")
        return str(path)
