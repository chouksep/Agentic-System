"""Transform simple BFCL cases into multiple/irrelevance category variants.

`Synthesizer` is deterministic given a seed. Multiple-category cases pad the
function list with distractors drawn from the wiki tool set; irrelevance
cases pair an off-topic question with random wiki tools and expect zero
calls. Parallel-category synthesis is deferred — QA-corpus questions don't
naturally yield parallel-call patterns.
"""
from __future__ import annotations

import random
from dataclasses import replace

from benchmarks.runner.datasets.base import BfclCase

# Canonical wiki tool names — must match ci_wiki/llm/tools.py and
# benchmarks/bfcl-faithful/wiki_functions.py exactly.
ALL_WIKI_FUNCTIONS: list[str] = [
    "read_wiki_page",
    "write_wiki_page",
    "search_wiki",
    "list_wiki_pages",
    "flag_contradiction",
]


class Synthesizer:
    def __init__(self, seed: int) -> None:
        self._rng = random.Random(seed)

    def to_multiple(self, cases: list[BfclCase], n_distractors: int) -> list[BfclCase]:
        """Pad each case's function list with up to `n_distractors` distractors.

        Distractors are drawn from `ALL_WIKI_FUNCTIONS` minus already-present
        functions; if fewer than `n_distractors` candidates remain, the whole
        remaining pool is used (best-effort). Each returned case gets the
        suffix `__multi` on its id and `category="multiple"`. `question` and
        `possible_answer` are preserved.
        """
        out: list[BfclCase] = []
        for case in cases:
            present = set(case.functions)
            pool = [f for f in ALL_WIKI_FUNCTIONS if f not in present]
            self._rng.shuffle(pool)
            distractors = pool[:n_distractors]
            new_functions = list(case.functions) + distractors
            self._rng.shuffle(new_functions)
            out.append(
                replace(
                    case,
                    id=f"{case.id}__multi",
                    category="multiple",
                    functions=new_functions,
                )
            )
        return out

    def to_irrelevance(
        self,
        off_topic_questions: list[str],
        tools_subset: list[str],
    ) -> list[BfclCase]:
        """Pair each off-topic question with a random non-empty subset of tools.

        `tools_subset` should be a subset of `ALL_WIKI_FUNCTIONS` (not
        enforced — caller's responsibility); empty `tools_subset` raises
        ValueError. Each returned case has `possible_answer=[]` and
        `category="irrelevance"`; the model is expected to abstain.
        """
        if not tools_subset:
            raise ValueError("tools_subset must be non-empty")
        out: list[BfclCase] = []
        for idx, question in enumerate(off_topic_questions):
            k = self._rng.randint(1, len(tools_subset))
            funcs = self._rng.sample(tools_subset, k)
            out.append(
                BfclCase(
                    id=f"irrelevance_{idx}",
                    category="irrelevance",
                    functions=funcs,
                    question=question,
                    possible_answer=[],
                )
            )
        return out
