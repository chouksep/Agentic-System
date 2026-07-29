"""Tests for benchmarks.runner.finqa_evaluator."""
from __future__ import annotations

from benchmarks.runner import finqa_evaluator as evaluator
from benchmarks.runner.datasets.finqa import FinqaCase


def _case(value=100.0, unit="millions") -> FinqaCase:
    return FinqaCase(
        id="JPM/2018/page_43.pdf-0",
        ticker="JPM",
        year=2018,
        question="q?",
        gold_answer_raw="$100 million",
        gold_answer_value=value,
        gold_answer_unit=unit,
    )


def test_score_correct_within_tolerance():
    result = evaluator.score(_case(), parsed_value=100.5, parsed_unit="millions", parse_error=None)
    assert result.correct is True
    assert result.reason == "correct"


def test_score_incorrect_just_outside_tolerance():
    # Gold 100, 1% tolerance is +/-1. 101.1 is outside.
    result = evaluator.score(_case(), parsed_value=101.1, parsed_unit="millions", parse_error=None)
    assert result.correct is False
    assert result.reason == "value_mismatch"


def test_score_unit_mismatch():
    result = evaluator.score(_case(unit="millions"), parsed_value=100.0, parsed_unit="%", parse_error=None)
    assert result.correct is False
    assert result.reason == "unit_mismatch"


def test_score_ratio_vs_scalar_mismatch():
    result = evaluator.score(_case(value=1.5, unit="ratio"), parsed_value=1.5, parsed_unit="raw", parse_error=None)
    assert result.correct is False
    assert result.reason == "unit_mismatch"


def test_score_unparseable_prediction():
    result = evaluator.score(_case(), parsed_value=None, parsed_unit=None, parse_error="regex_fail")
    assert result.correct is False
    assert result.reason == "unparseable_prediction"


def test_score_not_available():
    result = evaluator.score(_case(), parsed_value=None, parsed_unit=None, parse_error="not_available")
    assert result.correct is False
    assert result.reason == "not_available"


def test_score_raw_gold_matches_millions_prediction():
    """FinQA gold '750 raw' (table-implicit millions) should match agent's '750 millions'."""
    result = evaluator.score(_case(value=750.0, unit="raw"),
                             parsed_value=750.0, parsed_unit="millions", parse_error=None)
    assert result.correct is True
    assert result.reason == "correct"


def test_score_raw_gold_still_rejects_wrong_magnitude():
    """Adaptive raw promotion must not mask a real magnitude error."""
    result = evaluator.score(_case(value=750.0, unit="raw"),
                             parsed_value=100.0, parsed_unit="millions", parse_error=None)
    assert result.correct is False
    assert result.reason == "value_mismatch"


def test_percentage_absolute_tolerance_accepts_small_rounding():
    """Gold rounded to whole percent (12%) vs agent's precise 11.86% should match."""
    result = evaluator.score(_case(value=12.0, unit="%"),
                             parsed_value=11.86, parsed_unit="%", parse_error=None)
    assert result.correct is True
    assert result.reason == "correct"


def test_percentage_absolute_tolerance_still_rejects_wide_miss():
    """Absolute tolerance is a small floor, not a blanket pass for percentages."""
    result = evaluator.score(_case(value=12.0, unit="%"),
                             parsed_value=20.0, parsed_unit="%", parse_error=None)
    assert result.correct is False
    assert result.reason == "value_mismatch"
