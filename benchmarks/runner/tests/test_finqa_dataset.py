"""Tests for benchmarks.runner.datasets.finqa — pure adapter, no HF network."""
from __future__ import annotations

import pytest

from benchmarks.runner.datasets import finqa


# --- _parse_answer ---

@pytest.mark.parametrize("raw,value,unit", [
    ("$3.2 million", 3.2, "millions"),
    ("3,200", 3200.0, "raw"),
    ("25%", 25.0, "%"),
    ("25 %", 25.0, "%"),
    ("1.5x", 1.5, "ratio"),
    ("1.5:1", 1.5, "ratio"),
    ("$1.4 billion", 1.4, "billions"),
    ("-45.3", -45.3, "raw"),
    ("$1,234", 1234.0, "raw"),
])
def test_parse_answer_handles_all_five_units(raw, value, unit):
    v, u = finqa._parse_answer(raw)
    assert v == pytest.approx(value)
    assert u == unit


def test_parse_answer_raises_on_garbage():
    with pytest.raises(ValueError):
        finqa._parse_answer("n/a")
    with pytest.raises(ValueError):
        finqa._parse_answer("")


# --- load ---

def _row(id_, answer, question="q?"):
    return {"id": id_, "question": question, "answer": answer,
            "table": [], "pre_text": "", "post_text": ""}


def test_load_filters_by_ticker():
    rows = [
        _row("JPM/2018/page_43.pdf-0", "$100 million"),
        _row("NVDA/2020/page_10.pdf-0", "$50 million"),  # not seeded
        _row("AAPL/2019/page_5.pdf-0", "3.2%"),
    ]
    cases = finqa.load(rows=rows, tickers=frozenset({"JPM", "AAPL"}))
    ids = [c.id for c in cases]
    assert "JPM/2018/page_43.pdf-0" in ids
    assert "AAPL/2019/page_5.pdf-0" in ids
    assert all("NVDA" not in i for i in ids)


def test_load_truncates_to_n_deterministically():
    rows = [
        _row("JPM/2018/page_43.pdf-3", "$100"),
        _row("JPM/2018/page_43.pdf-1", "$200"),
        _row("JPM/2018/page_43.pdf-2", "$300"),
    ]
    cases = finqa.load(rows=rows, tickers=frozenset({"JPM"}), n=2)
    # Sort-by-id then take first 2 -> pdf-1, pdf-2 (not pdf-3)
    assert [c.id for c in cases] == [
        "JPM/2018/page_43.pdf-1",
        "JPM/2018/page_43.pdf-2",
    ]


def test_load_min_year_drops_older_cases():
    rows = [
        _row("AAPL/2002/page_23.pdf-1", "5%"),
        _row("AAPL/2015/page_10.pdf-0", "$100"),
        _row("AAPL/2020/page_5.pdf-0", "$200"),
    ]
    cases = finqa.load(rows=rows, tickers=frozenset({"AAPL"}), min_year=2010)
    years = [c.year for c in cases]
    assert years == [2015, 2020]


def test_load_drops_unparseable_gold_rows():
    rows = [
        _row("JPM/2018/page_43.pdf-0", "n/a"),
        _row("JPM/2018/page_43.pdf-1", "$100"),
    ]
    cases = finqa.load(rows=rows, tickers=frozenset({"JPM"}))
    assert len(cases) == 1
    assert cases[0].id.endswith("pdf-1")


def test_finqa_case_shape():
    rows = [_row("JPM/2018/page_43.pdf-0", "$100", question="revenue?")]
    case = finqa.load(rows=rows, tickers=frozenset({"JPM"}))[0]
    assert case.id == "JPM/2018/page_43.pdf-0"
    assert case.ticker == "JPM"
    assert case.year == 2018
    assert case.question == "revenue?"
    assert case.gold_answer_raw == "$100"
    assert case.gold_answer_value == 100.0
    assert case.gold_answer_unit == "raw"


def test_seeded_tickers_is_frozenset_of_str():
    assert isinstance(finqa.SEEDED_TICKERS, frozenset)
    # Real check: seeded pool has at least the 5-company first rollout
    assert {"JPM", "ETR", "UNP", "AMT", "LMT"}.issubset(finqa.SEEDED_TICKERS)
