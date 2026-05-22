"""Faithful port of ToolComp's process-supervision evaluation pipeline.

Source: https://github.com/vaskar-open-source-research/toolcomp
Paper: Nath et al., 'ToolComp: A Multi-Tool Reasoning & Process Supervision
       Benchmark', arXiv:2501.01290 (2025).

The official pipeline:

    1. Generate a model trajectory for each of the 485 prompts (native or ReAct
       inference strategy). A trajectory consists of an *action plan* and a
       sequence of *ReAct steps* (thought / action / observation triples).
    2. For each (golden vs. model) pair, query an LLM judge twice — once with
       response A first, once with response B first — to neutralise position
       bias.
    3. Combine the two labels with `_score_pair` (see below) → win (1.0) /
       tie (0.5) / loss (0.0).
    4. Aggregate into `total_accuracy`, `action_plan_only_accuracy`, and
       `react_steps_accuracy`.

Faithfully reproduced here (identical algorithm; pluggable judge):
    _extract_label   — parses better_step / better_action_plan from output
    _score_pair      — pairwise scoring with position-bias correction
    aggregate        — same three accuracy metrics as upstream `metrics.json`

The actual LLM call is abstracted behind a `Judge` callable so this evaluator
can be wired to any model (the upstream repo uses LiteLLM with any of GPT-4o,
Claude 4 Sonnet, o3, Gemini 2.5 Pro, etc.).
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Callable

# The exact pairwise judge prompt template names referenced by the upstream
# code. They are imported from `prompts.llm_as_judge.get_pairwise_judge_react_prompt`
# and `get_pairwise_judge_plan_prompt`. We reproduce them here in spirit; the
# only requirement of the algorithm is that the judge ultimately returns JSON
# containing either `better_step` or `better_action_plan` ∈ {"1", "2", "tie"}.
PAIRWISE_REACT_PROMPT_TEMPLATE = """\
You are evaluating two tool-use trajectories produced by different agents
answering the same question.

Question: {question}
Tools available: {tools}

Response 1 ReAct step:
{step_1}

Response 2 ReAct step:
{step_2}

Which step is better? Reply with a JSON object:
{{"better_step": "1" | "2" | "tie", "reason": "<short explanation>"}}
"""

PAIRWISE_PLAN_PROMPT_TEMPLATE = """\
You are evaluating two action plans for the same question.

Question: {question}
Tools available: {tools}

Action plan 1:
{plan_1}

Action plan 2:
{plan_2}

Which plan is better? Reply with a JSON object:
{{"better_action_plan": "1" | "2" | "tie", "reason": "<short explanation>"}}
"""


# --------------------------------------------------------------------------- #
# Faithful copy of _extract_label and _score_pair from the upstream repo.
# --------------------------------------------------------------------------- #
def _extract_label(text: str, is_plan: bool) -> tuple[str, dict]:
    """Extract better_step / better_action_plan from a judge response.

    Identical to upstream:
    https://github.com/vaskar-open-source-research/toolcomp/blob/main/inference/llm_as_judge_inference.py
    """
    debug: dict[str, Any] = {"raw": text}
    fence_match = re.search(
        r"```json\s*\{[^`]*\}\s*```", text, flags=re.IGNORECASE | re.DOTALL
    )
    json_str = None
    if fence_match:
        json_str = fence_match.group(0)
        json_str = re.sub(r"^```json", "", json_str, flags=re.IGNORECASE).strip()
        json_str = re.sub(r"```$", "", json_str).strip()
    else:
        curly = re.search(r"\{[^\}]*\}", text, flags=re.DOTALL)
        if curly:
            json_str = curly.group(0)

    if json_str:
        try:
            data = json.loads(json_str)
            debug["parsed"] = data
            val = data.get("better_action_plan" if is_plan else "better_step")
            if isinstance(val, str) and val.lower() in {"tie", "1", "2"}:
                return val.lower(), debug
            if val in (1, 2):
                return str(val), debug
        except Exception as e:
            debug["json_error"] = str(e)

    pattern = (
        r"better_action_plan\s*[:=]\s*\"?(tie|1|2)\"?"
        if is_plan
        else r"better_step\s*[:=]\s*\"?(tie|1|2)\"?"
    )
    m = re.search(pattern, text, flags=re.IGNORECASE)
    if m:
        return m.group(1).lower(), debug
    return "unknown", debug


def _score_pair(l1: str, l2: str) -> tuple[float, str]:
    """Score a sample based on two predictions with positions swapped.

    Identical to upstream `_score_pair`.

    - Either is tie/unknown → 0.5 (tie)
    - (1, 2) → 1.0 (win)
    - (2, 1) → 0.0 (loss)
    - (1, 1) or (2, 2) → 0.5 (tie, attributable to position bias)
    """
    if l1 in ("tie", "unknown") or l2 in ("tie", "unknown"):
        return 0.5, "tie"
    if l1 == "1" and l2 == "2":
        return 1.0, "win"
    if l1 == "2" and l2 == "1":
        return 0.0, "loss"
    if l1 == l2:
        return 0.5, "tie"
    return 0.5, "tie"


# --------------------------------------------------------------------------- #
# Trajectory data structures
# --------------------------------------------------------------------------- #
@dataclass
class ReActStep:
    """One ReAct step: thought, action, observation."""

    thought: str
    action: str
    observation: str = ""


@dataclass
class Trajectory:
    """A complete model trajectory.

    Mirrors the upstream layout: an `action_plan` (list of intended high-level
    steps) and a sequence of `react_steps` (the actual thought/action loop).
    """

    action_plan: list[str] = field(default_factory=list)
    react_steps: list[ReActStep] = field(default_factory=list)
    final_answer: str = ""


# --------------------------------------------------------------------------- #
# Pluggable judge interface
# --------------------------------------------------------------------------- #
Judge = Callable[[str], str]
"""A judge is any function that takes the rendered prompt and returns text."""


def evaluate_pair(
    judge: Judge,
    question: str,
    tools: list[str],
    response_a: Any,
    response_b: Any,
    *,
    is_plan: bool,
) -> dict:
    """Evaluate one pair (a vs. b) with position swap.

    Returns a dict with keys: score, outcome, label_forward, label_reverse.
    """
    template = (
        PAIRWISE_PLAN_PROMPT_TEMPLATE if is_plan else PAIRWISE_REACT_PROMPT_TEMPLATE
    )
    key_a, key_b = ("plan_1", "plan_2") if is_plan else ("step_1", "step_2")

    fwd_prompt = template.format(
        question=question, tools=tools, **{key_a: str(response_a), key_b: str(response_b)}
    )
    rev_prompt = template.format(
        question=question, tools=tools, **{key_a: str(response_b), key_b: str(response_a)}
    )

    fwd_label, _ = _extract_label(judge(fwd_prompt), is_plan)
    rev_label, _ = _extract_label(judge(rev_prompt), is_plan)
    score, outcome = _score_pair(fwd_label, rev_label)
    return {
        "score": score,
        "outcome": outcome,
        "label_forward": fwd_label,
        "label_reverse": rev_label,
    }


def aggregate(per_sample_results: list[dict]) -> dict:
    """Identical aggregation to upstream metrics.json.

    Reports `total_accuracy`, `num_samples`, `action_plan_only_accuracy`,
    `action_plan_only_count`, `react_steps_accuracy`, `react_steps_count`.
    """
    plan = [r for r in per_sample_results if r["type"] == "plan"]
    step = [r for r in per_sample_results if r["type"] == "step"]
    all_ = plan + step

    def _mean(xs: list[dict]) -> float:
        return sum(x["score"] for x in xs) / len(xs) if xs else 0.0

    return {
        "total_accuracy": _mean(all_),
        "num_samples": len(all_),
        "action_plan_only_accuracy": _mean(plan),
        "action_plan_only_count": len(plan),
        "react_steps_accuracy": _mean(step),
        "react_steps_count": len(step),
    }
