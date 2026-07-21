"""Adapter: Natural Questions Open (Kwiatkowski et al., TACL 2019) → BfclCase[].

Originally the plan targeted EntityQuestions (Sciavolino et al., EMNLP 2021),
but no publicly-accessible HuggingFace mirror of that dataset was verifiable
at implementation time. Natural Questions Open (`nq_open`) is a strong
functional substitute: real Google Search questions annotated with short
Wikipedia answers, many of them entity-centric ("who founded X", "where is Y
headquartered"). The wiki-entity filter (EntityIndex.match) keeps only rows
that mention entities present in our wiki, so the practical yield is the
same.

For each row whose question mentions a wiki-resolvable entity, emit one
`simple`-category BFCL case that expects `read_wiki_page(slug, page_type)`.
"""
from __future__ import annotations

import logging
from typing import Iterable, Iterator

from benchmarks.runner.datasets.base import BfclCase, EntityIndex
from benchmarks.runner.datasets.llm_verifier import VerifierFn, verify

log = logging.getLogger(__name__)

# HuggingFace dataset id — verified accessible without auth. Tests inject
# their own iter and never hit HF.
HF_DATASET_ID = "nq_open"


def _default_hf_iter() -> Iterator[dict]:
    """Stream the HF nq_open dataset row-by-row (Natural Questions Open)."""
    from datasets import load_dataset  # type: ignore[import-not-found]
    ds = load_dataset(HF_DATASET_ID, split="train", streaming=True)
    yield from ds  # type: ignore[misc]


def load_entity_questions(
    *,
    entity_index: EntityIndex,
    dataset_iter: Iterable[dict] | None = None,
    n_max: int | None = None,
    verifier_fn: VerifierFn | None = None,
) -> list[BfclCase]:
    """Filter dataset rows to wiki-resolvable entities, return BfclCase list.

    When `verifier_fn` is provided, each candidate is passed to the LLM
    verifier before being emitted; rows where the verifier returns False
    are dropped. This raises precision against broad-domain corpora where
    slug-name collisions ("Claude Francois" vs "Claude the AI product")
    would otherwise generate nonsensical ground truth.
    """
    if dataset_iter is None:
        dataset_iter = _default_hf_iter()
    out: list[BfclCase] = []
    dropped_by_verifier = 0
    for idx, row in enumerate(dataset_iter):
        question = (row.get("question") or "").strip()
        if not question:
            continue
        matches = entity_index.match(question)
        if not matches:
            continue
        # Take the first match — questions are typically single-entity.
        slug, page_type = matches[0]
        if verifier_fn is not None and not verify(
            question, slug, page_type, verifier_fn=verifier_fn,
        ):
            dropped_by_verifier += 1
            continue
        case = BfclCase(
            id=f"eq_{idx}_{slug}",
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
    log.info(
        "entity_questions: kept %d cases (verifier dropped %d)",
        len(out), dropped_by_verifier,
    )
    return out
