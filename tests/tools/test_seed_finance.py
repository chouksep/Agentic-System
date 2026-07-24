"""Tests for tools/seed_finance/ (P2 seeder package).

All tests are self-contained: they use hand-authored fixtures under
tests/tools/fixtures/. No live network calls (SEC EDGAR or HuggingFace).
"""
from __future__ import annotations

from pathlib import Path

import pytest

from tools import seed_finance  # noqa: F401 — import smoke test


FIXTURES = Path(__file__).parent / "fixtures"


def test_module_imports():
    """Sanity: the seed_finance package can be imported."""
    assert seed_finance is not None


def test_fixture_files_exist():
    """Sanity: all committed fixtures are present on disk."""
    for name in (
        "company_facts_JPM.json",
        "submissions_JPM.json",
        "company_tickers.json",
        "finqa_rows.json",
    ):
        assert (FIXTURES / name).exists(), f"missing fixture: {name}"


import json

from tools.seed_finance import xbrl_metric_map


def _company_facts_us_gaap() -> dict:
    """Load the fixture's .facts["us-gaap"] sub-tree."""
    return json.loads((FIXTURES / "company_facts_JPM.json").read_text())["facts"]["us-gaap"]


def test_metric_map_covers_expected_metric_names():
    """METRIC_MAP must contain the standardized short-names used by the sidecar schema."""
    expected = {
        "revenue", "cost_of_revenue", "gross_profit", "operating_income",
        "net_income", "diluted_eps", "total_assets", "total_liabilities",
        "total_equity", "cash_and_equivalents", "total_debt",
        "operating_cash_flow", "capex", "free_cash_flow", "employees",
    }
    missing = expected - set(xbrl_metric_map.METRIC_MAP.keys())
    assert not missing, f"missing metric names: {missing}"


def test_resolve_concept_happy_path():
    facts = _company_facts_us_gaap()
    v = xbrl_metric_map.resolve_concept(
        ["Revenues", "SalesRevenueNet"], facts, "2018-FY",
    )
    assert v == 108783000000  # raw USD from the fixture


def test_resolve_concept_priority_order():
    """First concept in list should win when both are present.

    Fixture has 'Revenues' but not 'RevenueFromContractWithCustomerExcludingAssessedTax'.
    Priority ['Revenues', 'RevenueFromContractWithCustomerExcludingAssessedTax'] should
    return the Revenues value (108783000000). Reversed order should also return
    108783000000 because the ASC 606 concept is absent, so the fallback wins.
    """
    facts = _company_facts_us_gaap()
    v_priority_order = xbrl_metric_map.resolve_concept(
        ["Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax"],
        facts, "2018-FY",
    )
    v_reversed = xbrl_metric_map.resolve_concept(
        ["RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues"],
        facts, "2018-FY",
    )
    assert v_priority_order == 108783000000
    assert v_reversed == 108783000000


def test_resolve_concept_missing_period():
    facts = _company_facts_us_gaap()
    v = xbrl_metric_map.resolve_concept(["Revenues"], facts, "2010-FY")
    assert v is None


def test_resolve_concept_empty_priority_list():
    facts = _company_facts_us_gaap()
    v = xbrl_metric_map.resolve_concept([], facts, "2018-FY")
    assert v is None


from tools.seed_finance import ticker_slug_map


def test_ticker_slug_map_covers_top20_finqa_tickers():
    """The 20 hand-authored entries must include the tickers we plan to seed."""
    # Top-20 tickers by FinQA question count (from prior FinQA sample).
    expected = {
        "ETR", "LMT", "JPM", "AMT", "GS", "AAPL", "PNC", "MRO",
        "UNP", "AWK", "IPG", "AON", "STT", "AES", "RSG", "GPN",
        "AAL", "RE", "ZBH", "CME",
    }
    missing = expected - set(ticker_slug_map.TICKER_SLUG.keys())
    assert not missing, f"missing ticker→slug entries: {missing}"


def test_slug_for_known_ticker():
    assert ticker_slug_map.slug_for("JPM") == "jpmorgan-chase"


def test_slug_for_unknown_ticker_raises():
    with pytest.raises(KeyError, match="ZZZ"):
        ticker_slug_map.slug_for("ZZZ")


def test_all_slugs_are_lowercase_hyphenated():
    """Slug rules: lowercase letters, digits, hyphens only."""
    import re
    slug_pattern = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    for ticker, slug in ticker_slug_map.TICKER_SLUG.items():
        assert slug_pattern.match(slug), f"invalid slug for {ticker}: {slug!r}"


from tools.seed_finance import finqa_index


def _finqa_rows() -> list[dict]:
    return json.loads((FIXTURES / "finqa_rows.json").read_text())


def test_enumerate_top_by_question_count():
    """JPM has 3 rows (2 in 2018, 1 in 2017); GS has 1 (2018); AAPL has 1 (2018)."""
    rows = _finqa_rows()
    top = finqa_index.enumerate_top_by_question_count(rows, n=3)
    tickers = [t for t, _years in top]
    assert tickers[0] == "JPM"  # highest count
    assert set(tickers) == {"JPM", "GS", "AAPL"}
    # JPM's year set should include both 2017 and 2018
    jpm_years = dict(top)["JPM"]
    assert set(jpm_years) == {2017, 2018}


def test_enumerate_top_caps_at_n():
    rows = _finqa_rows()
    top = finqa_index.enumerate_top_by_question_count(rows, n=1)
    assert len(top) == 1


def test_tables_for_dedupes_by_page():
    """The two JPM/2018/page_43 rows share the same table — should return 1 unique table."""
    rows = _finqa_rows()
    tables = finqa_index.tables_for(rows, ticker="JPM", year=2018)
    assert len(tables) == 1
    tbl = tables[0]
    assert "pre_text" in tbl
    assert "header" in tbl
    assert "rows" in tbl
    assert "post_text" in tbl
    assert tbl["header"] == ["", "2018", "2017"]
    # Numeric rows come through as strings, verbatim
    assert any("Net income" in row[0] for row in tbl["rows"])


def test_tables_for_returns_empty_when_no_match():
    rows = _finqa_rows()
    assert finqa_index.tables_for(rows, ticker="ZZZ", year=2018) == []
    assert finqa_index.tables_for(rows, ticker="JPM", year=1999) == []


def test_years_by_ticker_covers_every_ticker():
    """years_by_ticker returns EVERY ticker (not top-N) with sorted year lists."""
    rows = _finqa_rows()
    m = finqa_index.years_by_ticker(rows)
    assert set(m.keys()) == {"JPM", "GS", "AAPL"}
    assert m["JPM"] == [2017, 2018]      # sorted ascending
    assert m["GS"] == [2018]
    assert m["AAPL"] == [2018]


from tools.seed_finance import sec_edgar


class _FakeResp:
    def __init__(self, status_code: int, body: bytes | str = b""):
        self.status_code = status_code
        if isinstance(body, str):
            body = body.encode("utf-8")
        self._body = body
        self.text = body.decode("utf-8")

    def json(self):
        return json.loads(self._body)


class _FakeSession:
    """Records .get() calls and returns predetermined responses in order."""

    def __init__(self, responses: list):
        self._responses = list(responses)
        self.calls: list[tuple[str, dict]] = []

    def get(self, url: str, headers: dict | None = None, timeout: int | None = None):
        self.calls.append((url, headers or {}))
        if not self._responses:
            raise RuntimeError("scripted responses exhausted")
        return self._responses.pop(0)


def test_fetch_company_facts_returns_parsed_json():
    body = (FIXTURES / "company_facts_JPM.json").read_bytes()
    session = _FakeSession([_FakeResp(200, body)])
    client = sec_edgar.SecEdgarClient(
        user_agent="test-agent test@example.com",
        session=session,
        sleep_seconds=0.0,
    )
    data = client.fetch_company_facts("0000019617")
    assert data["cik"] == 19617
    # Correct URL called, correct User-Agent sent
    called_url, called_headers = session.calls[0]
    assert "companyfacts/CIK0000019617.json" in called_url
    assert called_headers.get("User-Agent") == "test-agent test@example.com"


def test_fetch_submissions_returns_parsed_json():
    body = (FIXTURES / "submissions_JPM.json").read_bytes()
    session = _FakeSession([_FakeResp(200, body)])
    client = sec_edgar.SecEdgarClient(
        user_agent="test-agent", session=session, sleep_seconds=0.0,
    )
    data = client.fetch_submissions("0000019617")
    assert data["cik"] == "0000019617"
    assert data["tickers"] == ["JPM"]


def test_load_ticker_map_zero_pads_cik():
    body = (FIXTURES / "company_tickers.json").read_bytes()
    session = _FakeSession([_FakeResp(200, body)])
    client = sec_edgar.SecEdgarClient(
        user_agent="test-agent", session=session, sleep_seconds=0.0,
    )
    m = client.load_ticker_map()
    assert m["JPM"] == "0000019617"  # 5-digit CIK zero-padded to 10
    assert m["AAPL"] == "0000320193"


def test_retries_on_429_then_succeeds():
    """Two 429s then a 200; final result is the 200 body."""
    body = b'{"cik": 19617}'
    session = _FakeSession([
        _FakeResp(429),
        _FakeResp(429),
        _FakeResp(200, body),
    ])
    client = sec_edgar.SecEdgarClient(
        user_agent="test", session=session, sleep_seconds=0.0,
    )
    data = client.fetch_company_facts("0000019617")
    assert data == {"cik": 19617}
    assert len(session.calls) == 3


def test_gives_up_after_3_retries():
    session = _FakeSession([_FakeResp(429), _FakeResp(429), _FakeResp(429), _FakeResp(429)])
    client = sec_edgar.SecEdgarClient(
        user_agent="test", session=session, sleep_seconds=0.0,
    )
    with pytest.raises(sec_edgar.RateLimitExceeded):
        client.fetch_company_facts("0000019617")
    # Exactly 3 attempts (1 initial + 2 retries), then give up
    assert len(session.calls) == 3


def test_fetch_company_facts_404_raises_notfound():
    session = _FakeSession([_FakeResp(404, b"not found")])
    client = sec_edgar.SecEdgarClient(
        user_agent="test", session=session, sleep_seconds=0.0,
    )
    with pytest.raises(sec_edgar.NotFound):
        client.fetch_company_facts("9999999999")
