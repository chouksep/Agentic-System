"""Adapter: TriviaQA (Joshi et al., ACL 2017) → BfclCase[].

TriviaQA is broad-domain trivia. To keep download volume small and filter
yield high, we apply a tech-keyword allowlist before checking the wiki
entity index. Both filters are case-insensitive.
"""
from __future__ import annotations

import logging
from typing import Iterable, Iterator

from benchmarks.runner.datasets.base import BfclCase, EntityIndex

log = logging.getLogger(__name__)

HF_DATASET_ID = "trivia_qa"
HF_DATASET_CONFIG = "rc.nocontext"

# Terms that strongly imply the question is about an entity in our wiki domain.
# A row must contain one of these (case-insensitive) before we run the full
# EntityIndex match.
TECH_KEYWORDS: set[str] = {
    "openai", "anthropic", "deepmind", "google", "claude",
    "chatgpt", "gpt", "gemini", "altman", "amodei",
    "brockman", "sutskever", "hassabis", "suleyman", "musk",
    "ai", "artificial intelligence", "llm",
}


def _row_has_tech_keyword(question: str) -> bool:
    lower = question.lower()
    return any(kw in lower for kw in TECH_KEYWORDS)


def _default_hf_iter() -> Iterator[dict]:
    """Stream TriviaQA row-by-row."""
    from datasets import load_dataset  # type: ignore[import-not-found]
    ds = load_dataset(HF_DATASET_ID, HF_DATASET_CONFIG, split="train", streaming=True)
    yield from ds  # type: ignore[misc]


def load_triviaqa(
    *,
    entity_index: EntityIndex,
    dataset_iter: Iterable[dict] | None = None,
    n_max: int | None = None,
) -> list[BfclCase]:
    if dataset_iter is None:
        dataset_iter = _default_hf_iter()
    out: list[BfclCase] = []
    examined = 0
    for row in dataset_iter:
        examined += 1
        question = (row.get("question") or "").strip()
        if not question or not _row_has_tech_keyword(question):
            continue
        matches = entity_index.match(question)
        if not matches:
            continue
        slug, page_type = matches[0]
        case = BfclCase(
            id=f"tqa_{examined}_{slug}",
            category="simple",
            functions=["read_wiki_page"],
            question=question,
            possible_answer=[
                {"read_wiki_page": {"slug": [slug], "page_type": [page_type]}}
            ],
        )
        out.append(case)
        if n_max is not None and len(out) >= n_max:
            break
    log.info("triviaqa: examined %d rows, kept %d", examined, len(out))
    return out
