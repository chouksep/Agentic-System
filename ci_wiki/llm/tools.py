"""Claude tool definitions and dispatcher for wiki operations."""
from __future__ import annotations

import json
from typing import Any, Callable

from ci_wiki.wiki.page import WikiPageIO
from ci_wiki.wiki.search import WikiSearch
from ci_wiki.models import WikiPage

PAGE_TYPES = ["company", "product", "person", "trend"]

# --- Tool schemas (passed to Anthropic API) ---

READ_WIKI_PAGE = {
    "name": "read_wiki_page",
    "description": (
        "Read the current content of a wiki page by slug and type. "
        "Always call this before writing to see the current state."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "slug": {
                "type": "string",
                "description": "Page slug (lowercase, hyphens, e.g. 'openai', 'gpt-4o')",
            },
            "page_type": {
                "type": "string",
                "enum": PAGE_TYPES,
                "description": "Entity type",
            },
        },
        "required": ["slug", "page_type"],
    },
}

WRITE_WIKI_PAGE = {
    "name": "write_wiki_page",
    "description": (
        "Write or update a wiki page. Provide the COMPLETE new content including "
        "YAML frontmatter (between --- fences) and markdown body. "
        "This overwrites the existing file atomically."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "slug": {
                "type": "string",
                "description": "Page slug (lowercase, hyphens)",
            },
            "page_type": {
                "type": "string",
                "enum": PAGE_TYPES,
            },
            "content": {
                "type": "string",
                "description": (
                    "Full markdown content with YAML frontmatter. "
                    "Must start with ---\\nfrontmatter\\n---\\n"
                ),
            },
        },
        "required": ["slug", "page_type", "content"],
    },
}

SEARCH_WIKI = {
    "name": "search_wiki",
    "description": (
        "Search the wiki using a text query. Returns top matching page slugs and snippets. "
        "Use this to discover existing pages before reading or writing."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query (entity names, keywords)",
            },
            "top_k": {
                "type": "integer",
                "description": "Number of results to return (default: 5)",
                "default": 5,
            },
        },
        "required": ["query"],
    },
}

LIST_WIKI_PAGES = {
    "name": "list_wiki_pages",
    "description": "List all pages of a given type in the wiki.",
    "input_schema": {
        "type": "object",
        "properties": {
            "page_type": {
                "type": "string",
                "enum": PAGE_TYPES + ["all"],
                "description": "Entity type, or 'all' for every page",
            }
        },
        "required": ["page_type"],
    },
}

FLAG_CONTRADICTION = {
    "name": "flag_contradiction",
    "description": (
        "Flag a factual contradiction between two wiki pages for human review. "
        "Use during lint operations when you detect conflicting information."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "page_a": {"type": "string", "description": "First page slug"},
            "page_b": {"type": "string", "description": "Second page slug"},
            "description": {
                "type": "string",
                "description": "Description of the contradiction",
            },
            "suggested_resolution": {
                "type": "string",
                "description": "Optional suggested resolution",
            },
        },
        "required": ["page_a", "page_b", "description"],
    },
}

# Standard toolsets per operation
INGEST_TOOLS = [READ_WIKI_PAGE, WRITE_WIKI_PAGE, SEARCH_WIKI, LIST_WIKI_PAGES]
QUERY_TOOLS = [READ_WIKI_PAGE, SEARCH_WIKI, LIST_WIKI_PAGES]
LINT_TOOLS = [READ_WIKI_PAGE, WRITE_WIKI_PAGE, SEARCH_WIKI, LIST_WIKI_PAGES, FLAG_CONTRADICTION]


class ToolCall:
    def __init__(self, tool_use_block: Any) -> None:
        self.id = tool_use_block.id
        self.name = tool_use_block.name
        self.input = tool_use_block.input


class ToolDispatcher:
    """Routes tool calls to Python implementations."""

    def __init__(self, page_io: WikiPageIO, search: WikiSearch) -> None:
        self._page_io = page_io
        self._search = search
        self.pages_created: list[str] = []
        self.pages_updated: list[str] = []
        self.contradictions: list[dict] = []

    def dispatch(self, tool_call: ToolCall) -> str:
        handlers: dict[str, Callable] = {
            "read_wiki_page": self._read_wiki_page,
            "write_wiki_page": self._write_wiki_page,
            "search_wiki": self._search_wiki,
            "list_wiki_pages": self._list_wiki_pages,
            "flag_contradiction": self._flag_contradiction,
        }
        handler = handlers.get(tool_call.name)
        if handler is None:
            return json.dumps({"error": f"Unknown tool: {tool_call.name}"})
        try:
            return handler(tool_call.input)
        except Exception as e:
            return json.dumps({"error": str(e)})

    def _read_wiki_page(self, inp: dict) -> str:
        slug = inp["slug"]
        page_type = inp["page_type"]
        if not self._page_io.exists(slug, page_type):
            return json.dumps({"exists": False, "message": f"Page '{slug}' ({page_type}) does not exist yet."})
        page = self._page_io.read_by_slug(slug, page_type)
        content = f"---\n"
        from ci_wiki.utils.markdown import _dump_yaml_subset
        content += _dump_yaml_subset(page.frontmatter)
        content += f"---\n{page.body}"
        return json.dumps({"exists": True, "slug": slug, "page_type": page_type, "content": content})

    def _write_wiki_page(self, inp: dict) -> str:
        slug = inp["slug"]
        page_type = inp["page_type"]
        content = inp["content"]

        existed = self._page_io.exists(slug, page_type)
        page = self._page_io.write_content(slug, page_type, content)

        if existed:
            if slug not in self.pages_updated:
                self.pages_updated.append(slug)
        else:
            if slug not in self.pages_created:
                self.pages_created.append(slug)

        # Invalidate search index
        self._search._built = False

        return json.dumps({
            "success": True,
            "slug": slug,
            "page_type": page_type,
            "action": "updated" if existed else "created",
        })

    def _search_wiki(self, inp: dict) -> str:
        query = inp["query"]
        top_k = inp.get("top_k", 5)

        # Rebuild index if stale
        if not self._search._built:
            pages = self._page_io.read_all()
            self._search._pages = pages
            self._search.build_index()

        snippets = self._search.get_snippets(query, top_k=top_k)
        return json.dumps({"results": snippets, "total": len(snippets)})

    def _list_wiki_pages(self, inp: dict) -> str:
        page_type = inp["page_type"]
        if page_type == "all":
            pages = self._page_io.read_all()
        else:
            pages = self._page_io.read_all(page_type)
        result = [
            {
                "slug": p.slug,
                "page_type": p.page_type,
                "name": p.frontmatter.get("name", p.slug),
            }
            for p in pages
        ]
        return json.dumps({"pages": result, "total": len(result)})

    def _flag_contradiction(self, inp: dict) -> str:
        entry = {
            "page_a": inp["page_a"],
            "page_b": inp["page_b"],
            "description": inp["description"],
            "suggested_resolution": inp.get("suggested_resolution", ""),
        }
        self.contradictions.append(entry)
        return json.dumps({"flagged": True, "contradiction": entry})
