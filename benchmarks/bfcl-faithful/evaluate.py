"""BFCL-faithful evaluator runner for the ci-wiki agent.

Following BFCL's two-phase protocol:
    1. Generation: ask a model the `question` field with the listed functions
       available; record the produced function calls.
    2. Evaluation: feed those calls into `ast_checker` along with the
       `possible_answer` and `category`; compute accuracy per category and
       overall.

Because this repo does not ship a live LLM, the runner accepts a
`predictions.json` file produced separately (e.g., by `ci_wiki.llm.client`)
and scores it. It can also run in `--self-test` mode against handcrafted
predictions to verify the AST checker is wired up correctly.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))

from ast_checker import ast_checker
from wiki_functions import ALL_WIKI_FUNCTIONS


def load_test_cases(path: Path) -> dict:
    with path.open() as f:
        return json.load(f)


def get_function_descriptions(function_names: list) -> list:
    by_name = {f["name"]: f for f in ALL_WIKI_FUNCTIONS}
    return [by_name[n] for n in function_names]


def evaluate_one(test_case: dict, prediction: list) -> dict:
    """Run BFCL's ast_checker on one test case + model prediction."""
    func_descriptions = get_function_descriptions(test_case["functions"])
    possible_answer = test_case["possible_answer"]
    category = test_case["category"]

    if category == "irrelevance":
        # BFCL convention: pass iff model abstains (0 calls).
        if len(prediction) == 0:
            return {"valid": True, "error": []}
        return {
            "valid": False,
            "error": ["Expected abstention but got function calls."],
            "error_type": "irrelevance:should_abstain",
        }

    return ast_checker(
        func_descriptions if category != "simple" else func_descriptions[0],
        prediction,
        possible_answer,
        category,
    )


def evaluate_all(test_cases: list, predictions: dict) -> dict:
    """Evaluate every test case and aggregate accuracy per BFCL category."""
    per_category: dict[str, list[bool]] = defaultdict(list)
    per_case: list[dict] = []

    for tc in test_cases:
        tc_id = tc["id"]
        pred = predictions.get(tc_id, [])
        result = evaluate_one(tc, pred)
        per_category[tc["category"]].append(result["valid"])
        per_case.append(
            {
                "id": tc_id,
                "category": tc["category"],
                "valid": result["valid"],
                "error_type": result.get("error_type", ""),
                "error": result.get("error", []),
            }
        )

    summary: dict[str, Any] = {"per_category": {}, "overall": {}}
    total_valid = 0
    total_count = 0
    for cat, values in per_category.items():
        valid = sum(values)
        total = len(values)
        summary["per_category"][cat] = {
            "accuracy": valid / total if total else 0.0,
            "valid": valid,
            "total": total,
        }
        total_valid += valid
        total_count += total
    summary["overall"] = {
        "accuracy": total_valid / total_count if total_count else 0.0,
        "valid": total_valid,
        "total": total_count,
    }
    summary["per_case"] = per_case
    return summary


def self_test_predictions(test_cases: list) -> dict:
    """Build a deliberately-correct prediction set so we can verify the checker.

    Each prediction is taken straight from `possible_answer[0]` — i.e., the
    canonical golden answer. For parallel cases we include all expected calls.
    """
    predictions: dict[str, list] = {}
    for tc in test_cases:
        pa = tc["possible_answer"]
        calls = []
        for call in pa:
            for func_name, params in call.items():
                concrete_params = {}
                for p_name, p_values in params.items():
                    # Pick a non-empty value; "" indicates optional-absent.
                    chosen = next((v for v in p_values if v != "" and v != []), None)
                    if chosen is None:
                        continue
                    concrete_params[p_name] = chosen
                calls.append({func_name: concrete_params})
        predictions[tc["id"]] = calls
    return predictions


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--test-cases", default=str(HERE / "test_cases.json"))
    parser.add_argument(
        "--predictions",
        help="JSON file mapping test_case_id -> list of {func_name: {param: value}}",
    )
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="Generate predictions from golden answers and verify checker.",
    )
    parser.add_argument("--output", default=str(HERE / "results.json"))
    args = parser.parse_args()

    data = load_test_cases(Path(args.test_cases))
    test_cases = data["test_cases"]

    if args.self_test:
        predictions = self_test_predictions(test_cases)
    else:
        if not args.predictions:
            parser.error("--predictions required unless --self-test is set")
        with open(args.predictions) as f:
            predictions = json.load(f)

    summary = evaluate_all(test_cases, predictions)

    print("=" * 70)
    print("BFCL-FAITHFUL EVALUATION RESULTS")
    print("=" * 70)
    print(f"Overall accuracy: {summary['overall']['accuracy']:.1%} "
          f"({summary['overall']['valid']}/{summary['overall']['total']})")
    print()
    print("Per category:")
    for cat, m in summary["per_category"].items():
        print(f"  {cat:<15}  {m['accuracy']:.1%}  ({m['valid']}/{m['total']})")
    print()
    failed = [c for c in summary["per_case"] if not c["valid"]]
    if failed:
        print(f"Failed cases ({len(failed)}):")
        for c in failed:
            print(f"  - {c['id']} [{c['category']}] {c['error_type']}: {c['error']}")

    with open(args.output, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\nWrote detailed results to: {args.output}")


if __name__ == "__main__":
    main()
