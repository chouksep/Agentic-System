"""ci-wiki tool definitions converted to BFCL function-description format.

BFCL's function-description schema is essentially the OpenAI/JSON-Schema format
that the ci-wiki tools already use. We re-export them here so the AST checker
can be invoked on them directly.

Source (ci-wiki tools): ci_wiki/llm/tools.py
"""
from __future__ import annotations

PAGE_TYPES = ["company", "product", "person", "trend"]

# These match ci_wiki/llm/tools.py exactly, but are wrapped in BFCL's expected
# {name, description, parameters} shape with `parameters.properties` and
# `parameters.required` keys.
READ_WIKI_PAGE = {
    "name": "read_wiki_page",
    "description": (
        "Read the current content of a wiki page by slug and type. "
        "Always call this before writing to see the current state."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "slug": {
                "type": "string",
                "description": "Page slug (lowercase, hyphens, e.g. 'openai').",
            },
            "page_type": {
                "type": "string",
                "description": "Entity type",
                "enum": PAGE_TYPES,
            },
        },
        "required": ["slug", "page_type"],
    },
}

WRITE_WIKI_PAGE = {
    "name": "write_wiki_page",
    "description": (
        "Write or update a wiki page. Provide the COMPLETE new content including "
        "YAML frontmatter (between --- fences) and markdown body."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "slug": {"type": "string", "description": "Page slug"},
            "page_type": {"type": "string", "enum": PAGE_TYPES},
            "content": {
                "type": "string",
                "description": "Full markdown content with YAML frontmatter.",
            },
        },
        "required": ["slug", "page_type", "content"],
    },
}

SEARCH_WIKI = {
    "name": "search_wiki",
    "description": (
        "Search the wiki using a text query. Returns top matching page slugs "
        "and snippets."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search query"},
            "top_k": {
                "type": "integer",
                "description": "Number of results to return (default 5)",
            },
        },
        "required": ["query"],
    },
}

LIST_WIKI_PAGES = {
    "name": "list_wiki_pages",
    "description": "List all pages of a given type in the wiki.",
    "parameters": {
        "type": "object",
        "properties": {
            "page_type": {
                "type": "string",
                "enum": PAGE_TYPES + ["all"],
                "description": "Entity type, or 'all' for every page.",
            }
        },
        "required": ["page_type"],
    },
}

FLAG_CONTRADICTION = {
    "name": "flag_contradiction",
    "description": (
        "Flag a factual contradiction between two wiki pages for human review."
    ),
    "parameters": {
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

ALL_WIKI_FUNCTIONS = [
    READ_WIKI_PAGE,
    WRITE_WIKI_PAGE,
    SEARCH_WIKI,
    LIST_WIKI_PAGES,
    FLAG_CONTRADICTION,
]
