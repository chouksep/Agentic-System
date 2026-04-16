"""All LLM prompt templates for ci-wiki operations."""
from __future__ import annotations

from pathlib import Path

_schema_cache: str | None = None


def load_schema(schema_file: Path) -> str:
    global _schema_cache
    if _schema_cache is None:
        _schema_cache = schema_file.read_text(encoding="utf-8")
    return _schema_cache


def build_ingest_system_prompt(schema: str) -> str:
    return schema + """

---

## Current Task: INGEST

You are processing a new source document for the competitive intelligence wiki.

**Your workflow:**
1. Read the source document carefully.
2. Identify all competitive intelligence entities: companies, products, people, and trends.
3. For each entity with at least 3 distinct facts, call `search_wiki` to find existing pages.
4. For each relevant entity, call `read_wiki_page` to get its current content (if it exists).
5. Call `write_wiki_page` to create or update pages. Integrate new information with existing content.
6. Follow the Update Protocol: never delete content, mark stale/conflicting claims with blockquotes.
7. Append this source's URI to the `sources:` frontmatter list of every page you update.

**Quality rules:**
- Extract only facts explicitly stated in the source. Do not infer or speculate.
- If you cannot determine a frontmatter field, use `unknown`.
- Prefer updating existing pages over creating new ones.
- Only create new pages for entities with 3+ distinct facts in the source.
"""


def build_ingest_user_prompt(source_text: str, source_uri: str, existing_slugs: list[str]) -> str:
    existing_summary = (
        f"The wiki currently has {len(existing_slugs)} pages. "
        f"Slugs: {', '.join(existing_slugs[:30])}"
        + (" (and more...)" if len(existing_slugs) > 30 else "")
        if existing_slugs
        else "The wiki is currently empty."
    )

    return f"""**Source URI:** {source_uri}

**Wiki status:** {existing_summary}

**Source document:**
---
{source_text}
---

Process this source document. Extract competitive intelligence and update the wiki accordingly.
"""


def build_query_system_prompt(schema: str) -> str:
    return schema + """

---

## Current Task: QUERY

You are answering a competitive intelligence question using the wiki.

**Your workflow:**
1. Call `search_wiki` with the question to find candidate pages.
2. Call `read_wiki_page` to read the 2-3 most relevant pages in full.
3. Synthesize a clear answer from the wiki content.

**Answer format:**
- **Direct Answer**: One or two sentences answering the question directly.
- **Supporting Evidence**: Key facts from the wiki with page citations [[type:slug]].
- **Confidence**: high / medium / low — based on source count and recency.
- **Gaps**: Any information the wiki lacks that would improve the answer.

**Rules:**
- Only use information found in the wiki. If the wiki doesn't have it, say so clearly.
- Always cite the wiki page(s) you used.
- Do not speculate beyond what the wiki contains.
"""


def build_query_user_prompt(question: str, page_summaries: str) -> str:
    return f"""**Question:** {question}

**Relevant wiki pages (summaries — call read_wiki_page for full content):**
{page_summaries}

Answer the question using information from the wiki. Use read_wiki_page to load full page content as needed.
"""


def build_lint_system_prompt(schema: str) -> str:
    return schema + """

---

## Current Task: LINT

You are auditing the competitive intelligence wiki for quality issues.

**Check for:**
1. **Contradictions**: Facts in one page that conflict with facts in another page.
2. **Missing required sections**: Company pages missing Pricing, Funding, or Competitive Position sections.
3. **Low-confidence claims needing verification**: Claims marked `confidence: low` with only 1 source that are 90+ days old.
4. **Stale unsourced claims**: Factual assertions with no source reference.

**For each issue found:**
- Use `flag_contradiction` for conflicts requiring human review.
- Use `write_wiki_page` to fix minor issues inline (e.g., add missing section headers, fix formatting).
- For stale claims, add a `> [STALE as of YYYY-MM-DD]:` marker.

**Be systematic**: read all pages in the provided batch before writing any fixes.
"""


def build_lint_user_prompt(page_contents: list[dict]) -> str:
    pages_text = ""
    for pc in page_contents:
        pages_text += f"\n### {pc['slug']} ({pc['page_type']})\n{pc['content'][:2000]}\n"
    return f"""Audit the following wiki pages for quality issues:

{pages_text}

For each issue found: use flag_contradiction or write_wiki_page to address it.
Report a summary of issues found and actions taken.
"""
