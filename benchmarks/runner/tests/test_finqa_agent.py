"""Tests for benchmarks.runner.finqa_agent — uses MockLLMClient."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from benchmarks.runner.datasets.finqa import FinqaCase
from benchmarks.runner.finqa_agent import FinqaAgent, _CountingDispatcher, _MAX_TOOL_CALLS


REPO_ROOT = Path(__file__).resolve().parents[3]
WIKI_DIR = REPO_ROOT / "wiki"


def _case() -> FinqaCase:
    return FinqaCase(
        id="JPM/2018/page_43.pdf-0",
        ticker="JPM",
        year=2018,
        question="What was JPM 2018 revenue?",
        gold_answer_raw="$100 million",
        gold_answer_value=100.0,
        gold_answer_unit="millions",
    )


def test_agent_direct_answer_no_tool_calls():
    """Agent answers immediately; parsed_value/unit populated."""
    mock_llm = MagicMock()
    mock_llm.complete_with_tools.return_value = ("The answer is $100 million.", 250)

    agent = FinqaAgent(llm_client=mock_llm, wiki_dir=WIKI_DIR)
    record = agent.answer(_case())

    assert record.parsed_value == pytest.approx(100.0)
    assert record.parsed_unit == "millions"
    assert record.parse_error is None
    assert record.tool_call_count == 0
    assert record.final_text.endswith("$100 million.")


def test_agent_unparseable_answer_sets_parse_error():
    """Model returns text with no extractable number → parse_error set."""
    mock_llm = MagicMock()
    mock_llm.complete_with_tools.return_value = ("I do not know.", 100)

    agent = FinqaAgent(llm_client=mock_llm, wiki_dir=WIKI_DIR)
    record = agent.answer(_case())

    assert record.parsed_value is None
    assert record.parsed_unit is None
    assert record.parse_error == "regex_fail"


def test_agent_not_available_answer():
    """Model emits NOT_AVAILABLE → parse_error='not_available'."""
    mock_llm = MagicMock()
    mock_llm.complete_with_tools.return_value = ("NOT_AVAILABLE", 60)

    agent = FinqaAgent(llm_client=mock_llm, wiki_dir=WIKI_DIR)
    record = agent.answer(_case())

    assert record.parsed_value is None
    assert record.parse_error == "not_available"


def test_counting_dispatcher_caps_calls():
    """After _MAX_TOOL_CALLS, dispatch returns a cap-exceeded error JSON."""
    from ci_wiki.llm.tools import ToolCall

    # Real dispatcher over real wiki so the first call is legitimate.
    page_io = MagicMock()
    search = MagicMock()
    disp = _CountingDispatcher(page_io, search, WIKI_DIR)
    tc = ToolCall(id="1", name="list_companies_with_financials", input={})

    for _ in range(_MAX_TOOL_CALLS):
        out = disp.dispatch(tc)
        assert "tool_call_cap_exceeded" not in out
    assert disp.tool_call_count == _MAX_TOOL_CALLS

    # (_MAX_TOOL_CALLS + 1)th call must be short-circuited.
    out = disp.dispatch(tc)
    assert "tool_call_cap_exceeded" in out
    assert disp.tool_call_count == _MAX_TOOL_CALLS  # counter DOES NOT increment past cap


def test_extract_answer_prefers_unit_tagged_over_trailing_year():
    """Model text like 'was 194% for the five years ended 2015' must pick 194%, not 2015."""
    from benchmarks.runner.finqa_agent import _extract_answer
    value, unit, err = _extract_answer(
        "The cumulative total shareholder return was 194% for the five years ended 2015."
    )
    assert err is None
    assert unit == "%"
    assert value == 194.0


def test_extract_answer_falls_back_to_bare_number_when_no_unit_tagged():
    """No unit token anywhere -> keep old last-number-wins behavior."""
    from benchmarks.runner.finqa_agent import _extract_answer
    value, unit, err = _extract_answer("The change was 47")
    assert err is None
    assert unit == "raw"
    assert value == 47.0
