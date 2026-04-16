"""BM25 Okapi search over wiki pages (no external dependencies)."""
from __future__ import annotations

import math
import re
from collections import Counter

from ci_wiki.models import WikiPage

_K1 = 1.5
_B = 0.75
_MD_STRIP = re.compile(r"[#*_\[\]`>|~]")
_WORD = re.compile(r"[a-z0-9]+(?:['-][a-z0-9]+)*")


def _tokenize(text: str) -> list[str]:
    text = _MD_STRIP.sub(" ", text.lower())
    return _WORD.findall(text)


class WikiSearch:
    def __init__(self, pages: list[WikiPage]) -> None:
        self._pages = pages
        self._corpus: list[list[str]] = []
        self._df: Counter = Counter()
        self._avgdl: float = 0.0
        self._built = False

    def build_index(self) -> None:
        self._corpus = []
        for page in self._pages:
            full_text = (
                page.frontmatter.get("name", page.slug)
                + " "
                + page.slug.replace("-", " ")
                + " "
                + page.body
            )
            tokens = _tokenize(full_text)
            self._corpus.append(tokens)

        # IDF: document frequency
        self._df = Counter()
        for tokens in self._corpus:
            for term in set(tokens):
                self._df[term] += 1

        total_len = sum(len(t) for t in self._corpus)
        self._avgdl = total_len / len(self._corpus) if self._corpus else 1.0
        self._built = True

    def search(
        self, query: str, top_k: int = 5
    ) -> list[tuple[WikiPage, float]]:
        if not self._pages:
            return []
        if not self._built:
            self.build_index()

        query_terms = _tokenize(query)
        if not query_terms:
            return []

        n = len(self._corpus)
        scores: list[float] = []
        for doc_id, tokens in enumerate(self._corpus):
            score = self._bm25_score(query_terms, tokens, n)
            scores.append(score)

        ranked = sorted(
            [(self._pages[i], scores[i]) for i in range(len(self._pages))],
            key=lambda x: x[1],
            reverse=True,
        )
        # Return only results with positive scores
        return [(p, s) for p, s in ranked[:top_k] if s > 0]

    def _bm25_score(self, query_terms: list[str], doc_tokens: list[str], n: int) -> float:
        tf = Counter(doc_tokens)
        dl = len(doc_tokens)
        score = 0.0
        for term in query_terms:
            if tf[term] == 0:
                continue
            df = self._df.get(term, 0)
            if df == 0:
                continue
            idf = math.log((n - df + 0.5) / (df + 0.5) + 1)
            numerator = tf[term] * (_K1 + 1)
            denominator = tf[term] + _K1 * (1 - _B + _B * dl / self._avgdl)
            score += idf * (numerator / denominator)
        return score

    def get_snippets(
        self, query: str, top_k: int = 5, snippet_chars: int = 300
    ) -> list[dict]:
        """Return top-k pages with a short body snippet."""
        results = self.search(query, top_k)
        out = []
        for page, score in results:
            snippet = page.body[:snippet_chars].replace("\n", " ").strip()
            out.append(
                {
                    "slug": page.slug,
                    "page_type": page.page_type,
                    "name": page.frontmatter.get("name", page.slug),
                    "score": round(score, 3),
                    "snippet": snippet,
                }
            )
        return out
