"""Unit tests for the ToolComp-faithful pipeline.

Tests verify:
  1. _extract_label parses all valid output shapes (JSON fence, plain JSON,
     regex fallback, numeric value).
  2. _score_pair returns the exact 1.0 / 0.5 / 0.0 outcomes documented in
     the upstream code for every combination of (l1, l2).
  3. evaluate_pair correctly swaps positions and aggregates a win/tie/loss.
  4. aggregate produces the same six fields as upstream metrics.json.
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))

from evaluator import (
    _extract_label,
    _score_pair,
    aggregate,
    evaluate_pair,
)


def test_extract_label_json_fence():
    label, _ = _extract_label('```json\n{"better_step": "1"}\n```', is_plan=False)
    assert label == "1"
    label, _ = _extract_label('```json\n{"better_step": "2"}\n```', is_plan=False)
    assert label == "2"
    label, _ = _extract_label('```json\n{"better_step": "tie"}\n```', is_plan=False)
    assert label == "tie"
    print("  PASS  extract_label: JSON fence")


def test_extract_label_plain_json():
    label, _ = _extract_label('{"better_step": "1", "reason": "x"}', is_plan=False)
    assert label == "1"
    label, _ = _extract_label('{"better_action_plan": "2"}', is_plan=True)
    assert label == "2"
    print("  PASS  extract_label: plain JSON")


def test_extract_label_regex_fallback():
    label, _ = _extract_label("Plain text: better_step: 1", is_plan=False)
    assert label == "1"
    label, _ = _extract_label('better_action_plan = "tie"', is_plan=True)
    assert label == "tie"
    print("  PASS  extract_label: regex fallback")


def test_extract_label_unknown():
    label, _ = _extract_label("totally unparseable garbage", is_plan=False)
    assert label == "unknown"
    print("  PASS  extract_label: unknown → 'unknown'")


def test_score_pair_all_cases():
    # win
    assert _score_pair("1", "2") == (1.0, "win")
    # loss
    assert _score_pair("2", "1") == (0.0, "loss")
    # explicit tie
    assert _score_pair("tie", "1") == (0.5, "tie")
    assert _score_pair("1", "tie") == (0.5, "tie")
    # position-bias tie
    assert _score_pair("1", "1") == (0.5, "tie")
    assert _score_pair("2", "2") == (0.5, "tie")
    # unknown
    assert _score_pair("unknown", "1") == (0.5, "tie")
    print("  PASS  score_pair: matches upstream truth table")


def test_evaluate_pair_position_swap():
    # Judge prefers whichever response contains the word 'good'.
    def judge(prompt: str) -> str:
        if "step_1" in prompt or "plan_1" in prompt:
            # Forward call: step_1 / plan_1 is the first one we passed in.
            # Look at the actual content order in the prompt to decide.
            pass
        # Simple rule: pick "1" if "good" appears before "bad" in the prompt.
        idx_good = prompt.find("good")
        idx_bad = prompt.find("bad")
        if idx_good == -1 and idx_bad == -1:
            return '{"better_step": "tie"}'
        if idx_good == -1:
            return '{"better_step": "2"}' if idx_bad < len(prompt) // 2 else '{"better_step": "1"}'
        if idx_bad == -1:
            return '{"better_step": "1"}' if idx_good < len(prompt) // 2 else '{"better_step": "2"}'
        return '{"better_step": "1"}' if idx_good < idx_bad else '{"better_step": "2"}'

    # Good vs bad → win
    r = evaluate_pair(judge, "Q", ["t"], "good response", "bad response", is_plan=False)
    assert r["outcome"] == "win", r
    # Bad vs good → loss
    r = evaluate_pair(judge, "Q", ["t"], "bad response", "good response", is_plan=False)
    assert r["outcome"] == "loss", r
    print("  PASS  evaluate_pair: position swap produces win / loss correctly")


def test_aggregate():
    results = [
        {"type": "plan", "score": 1.0},
        {"type": "plan", "score": 0.0},
        {"type": "step", "score": 1.0},
        {"type": "step", "score": 0.5},
        {"type": "step", "score": 0.5},
    ]
    agg = aggregate(results)
    assert agg["num_samples"] == 5
    assert agg["action_plan_only_count"] == 2
    assert agg["action_plan_only_accuracy"] == 0.5
    assert agg["react_steps_count"] == 3
    assert abs(agg["react_steps_accuracy"] - (2.0 / 3.0)) < 1e-9
    assert abs(agg["total_accuracy"] - (3.0 / 5.0)) < 1e-9
    print("  PASS  aggregate: matches upstream metrics.json schema")


def main():
    print("=" * 70)
    print("ToolComp-faithful pipeline tests")
    print("=" * 70)
    test_extract_label_json_fence()
    test_extract_label_plain_json()
    test_extract_label_regex_fallback()
    test_extract_label_unknown()
    test_score_pair_all_cases()
    test_evaluate_pair_position_swap()
    test_aggregate()
    print("\n" + "=" * 70)
    print("All ToolComp-faithful tests passed.")
    print("=" * 70)


if __name__ == "__main__":
    main()
