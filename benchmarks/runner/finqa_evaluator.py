"""Score a FinQA agent prediction against a gold FinqaCase.

Tolerance-based numeric matching, unit-aware. Reasons:
  correct | unparseable_prediction | not_available | unit_mismatch | value_mismatch
"""
from __future__ import annotations

from dataclasses import dataclass

from benchmarks.runner.datasets.finqa import FinqaCase


_TOLERANCE = 0.01  # 1% relative


@dataclass
class ScoreResult:
    correct: bool
    reason: str


def _canonical_unit(unit: str) -> str:
    """Fold millions/billions to the same 'scalar' family; keep %/ratio separate."""
    if unit in {"raw", "millions", "billions"}:
        return "scalar"
    return unit  # '%' or 'ratio'


def score(
    case: FinqaCase,
    parsed_value: float | None,
    parsed_unit: str | None,
    parse_error: str | None,
) -> ScoreResult:
    if parse_error == "not_available":
        return ScoreResult(False, "not_available")
    if parsed_value is None or parsed_unit is None:
        return ScoreResult(False, "unparseable_prediction")

    if _canonical_unit(parsed_unit) != _canonical_unit(case.gold_answer_unit):
        return ScoreResult(False, "unit_mismatch")

    # FinQA gold answers with unit='raw' typically inherit the table's implicit
    # unit (usually 'millions'). When one side is 'raw' and the other has an
    # explicit scale, adopt the explicit scale for the raw side so
    # `750 raw` compares equal to `750 millions`.
    pred_unit = parsed_unit
    gold_unit = case.gold_answer_unit
    if pred_unit == "raw" and gold_unit in {"millions", "billions"}:
        pred_unit = gold_unit
    elif gold_unit == "raw" and pred_unit in {"millions", "billions"}:
        gold_unit = pred_unit

    scale = {"raw": 1.0, "millions": 1e6, "billions": 1e9, "%": 1.0, "ratio": 1.0}
    pred = parsed_value * scale.get(pred_unit, 1.0)
    gold = case.gold_answer_value * scale.get(gold_unit, 1.0)

    denom = max(abs(gold), 1e-9)
    if abs(pred - gold) / denom < _TOLERANCE:
        return ScoreResult(True, "correct")
    return ScoreResult(False, "value_mismatch")
