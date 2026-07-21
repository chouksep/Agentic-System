"""Runner for the faithful T-Eval port.

Loads samples from test_data.json (keyed by evaluator: instruct / plan /
reason_retrieve_understand / review) and runs the matching evaluator on each.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))

from evaluators import (
    InstructEvaluator,
    PlanningEvaluator,
    ReasonRetrieveUnderstandEvaluator,
    ReviewEvaluator,
)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default=str(HERE / "test_data.json"))
    parser.add_argument(
        "--skip-bertscore",
        action="store_true",
        help="Skip evaluators that require the sentence-transformer model "
             "(planning, reason_retrieve_understand).",
    )
    parser.add_argument("--output", default=str(HERE / "results.json"))
    args = parser.parse_args()

    with open(args.data) as f:
        data = json.load(f)

    results: dict = {}

    print("=" * 70)
    print("T-EVAL FAITHFUL EVALUATION RESULTS")
    print("=" * 70)

    # InstructEvaluator does not require BERT; always run.
    print("\n[InstructEvaluator]")
    instruct_res = InstructEvaluator().evaluate(data["instruct"])
    results["instruct"] = instruct_res
    for k, v in instruct_res.items():
        print(f"  {k:<28} {v:.4f}")

    print("\n[ReviewEvaluator]")
    review_res = ReviewEvaluator().evaluate(data["review"])
    results["review"] = review_res
    for k, v in review_res.items():
        print(f"  {k:<28} {v:.4f}")

    if not args.skip_bertscore:
        print("\n[PlanningEvaluator]   (BERT-score matching, this loads "
              "all-mpnet-base-v2 ~420MB)")
        plan_res = PlanningEvaluator(match_strategy="bertscore").evaluate(data["plan"])
        results["planning_bertscore"] = plan_res
        for k, v in plan_res.items():
            print(f"  {k:<28} {v:.4f}")

        print("\n[ReasonRetrieveUnderstandEvaluator]")
        rru_res = ReasonRetrieveUnderstandEvaluator().evaluate(
            data["reason_retrieve_understand"]
        )
        results["reason_retrieve_understand"] = rru_res
        for k, v in rru_res.items():
            print(f"  {k:<28} {v:.4f}")
    else:
        # Permutation strategy is also part of upstream — it requires no model.
        print("\n[PlanningEvaluator]   (permutation strategy — no BERT model)")
        plan_res = PlanningEvaluator(match_strategy="permutation").evaluate(data["plan"])
        results["planning_permutation"] = plan_res
        for k, v in plan_res.items():
            print(f"  {k:<28} {v:.4f}")
        print("\n[ReasonRetrieveUnderstandEvaluator] — skipped "
              "(thought/args similarity needs BERT model)")

    with open(args.output, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nWrote detailed results to: {args.output}")


if __name__ == "__main__":
    main()
