"""End-to-end: loader (mocked rows) -> agent (mocked LLM) -> evaluator."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import yaml

from benchmarks.runner import finqa_evaluator as evaluator
from benchmarks.runner.datasets.finqa import FinqaCase
from benchmarks.runner.finqa_agent import FinqaAgent

_FIXTURE = Path(__file__).resolve().parents[2] / "finqa-faithful" / "fixtures" / "cases.yaml"


def test_integration_three_cases_two_correct():
    fixture = yaml.safe_load(_FIXTURE.read_text(encoding="utf-8"))
    cases_data = fixture["cases"]

    # Build cases + a per-id script for the mocked LLM.
    cases = [
        FinqaCase(
            id=c["id"], ticker=c["ticker"], year=c["year"],
            question=c["question"], gold_answer_raw=c["gold_answer_raw"],
            gold_answer_value=float(c["gold_answer_value"]),
            gold_answer_unit=c["gold_answer_unit"],
        )
        for c in cases_data
    ]
    script = {c["id"]: c["scripted_final_text"] for c in cases_data}
    expected_correct = {c["id"]: bool(c["expected_correct"]) for c in cases_data}

    mock_llm = MagicMock()
    mock_llm.complete_with_tools.side_effect = [
        (script[c.id], 200) for c in cases
    ]

    wiki_dir = Path(__file__).resolve().parents[3] / "wiki"
    agent = FinqaAgent(llm_client=mock_llm, wiki_dir=wiki_dir)

    results = []
    for case in cases:
        record = agent.answer(case)
        r = evaluator.score(case, record.parsed_value, record.parsed_unit, record.parse_error)
        results.append((case.id, r.correct))

    got = dict(results)
    assert got == expected_correct
    assert sum(1 for _, ok in results if ok) == 2
