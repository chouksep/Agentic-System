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


def test_tables_for_coerces_list_pre_and_post_text_to_string():
    """Live FinQA rows expose pre_text/post_text as list[str]; schema requires string."""
    row = {
        "id": "XYZ/2020/page_1.pdf-0",
        "pre_text": ["First paragraph.", "Second paragraph."],
        "post_text": ["Trailing note one.", "Trailing note two."],
        "table": [["", "2020"], ["Revenue", "100"]],
    }
    tables = finqa_index.tables_for([row], ticker="XYZ", year=2020)
    assert len(tables) == 1
    assert isinstance(tables[0]["pre_text"], str)
    assert isinstance(tables[0]["post_text"], str)
    assert tables[0]["pre_text"] == "First paragraph.\n\nSecond paragraph."
    assert tables[0]["post_text"] == "Trailing note one.\n\nTrailing note two."


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


from ci_wiki.ops import financials as financials_validator
from tools.seed_finance import generate


def test_build_sidecar_passes_p1_validator():
    """A minimally-populated sidecar dict must pass ci_wiki.ops.financials.validate()."""
    data = generate.build_sidecar(
        ticker="JPM",
        cik="0000019617",
        metrics_by_period={
            "2018-FY": {"revenue": 108783.0, "net_income": 32474.0},
        },
        metric_metadata={
            "revenue": {
                "xbrl_concept": "us-gaap:Revenues",
                "description": "Total net sales / revenue",
            },
            "net_income": {
                "xbrl_concept": "us-gaap:NetIncomeLoss",
                "description": "Bottom-line profit after tax",
            },
        },
        filings=[
            {
                "id": "jpm-10k-2018",
                "form": "10-K",
                "filed": "2019-02-26",
                "period_covered": "2018-FY",
                "source_url": "https://www.sec.gov/example",
                "tables": [
                    {
                        "id": "income_statement",
                        "pre_text": "The following table...",
                        "header": ["", "2018"],
                        "rows": [["Revenue", "$108,783"]],
                        "post_text": "Solid year.",
                    }
                ],
            }
        ],
    )
    errors = financials_validator.validate(data)
    assert errors == [], f"validator errors: {errors}"


def test_build_sidecar_top_level_keys():
    data = generate.build_sidecar(
        ticker="X", cik="0000000123",
        metrics_by_period={"2020-FY": {"revenue": 100.0}},
        metric_metadata={"revenue": {"description": "x"}},
        filings=[],
    )
    # Schema requires these top-level keys
    assert data["schema_version"] == 1
    assert data["ticker"] == "X"
    assert data["cik"] == "0000000123"
    assert data["metrics"]["currency"] == "USD"
    assert data["metrics"]["units"] == "millions"


def test_build_sidecar_omits_empty_filings():
    """When filings list is empty, the 'filings' key should be omitted (spec allows optional)."""
    data = generate.build_sidecar(
        ticker="X", cik="0000000123",
        metrics_by_period={"2020-FY": {"revenue": 100.0}},
        metric_metadata={"revenue": {"description": "x"}},
        filings=[],
    )
    # Either 'filings' is absent, or it's an empty list — both valid per schema
    assert data.get("filings", []) == []


def test_build_stub_markdown_has_required_frontmatter_and_sections():
    md = generate.build_stub_markdown(slug="apple", name="Apple Inc.")
    # Frontmatter fence
    assert md.startswith("---\n")
    # Required company frontmatter fields (from schema/wiki_schema.md)
    assert 'name: "Apple Inc."' in md
    assert "type: company" in md
    assert "last_updated:" in md
    # Required section headers
    for section in ("## Overview", "## Pricing", "## Funding & Financials",
                     "## Competitive Position"):
        assert section in md, f"missing section: {section}"
    # Points readers at the sidecar
    assert "apple.financials.yaml" in md


import yaml
from tools.seed_finance import run


def _fake_edgar_client(known_facts: dict, known_submissions: dict, known_ticker_map: dict):
    """Build a SecEdgarClient-shaped stub for run.seed(edgar_client=...)."""
    class _Stub:
        def load_ticker_map(self):
            return known_ticker_map

        def fetch_company_facts(self, cik):
            if cik not in known_facts:
                raise sec_edgar.NotFound(f"cik {cik} not in stub")
            return known_facts[cik]

        def fetch_submissions(self, cik):
            if cik not in known_submissions:
                raise sec_edgar.NotFound(f"cik {cik} not in stub")
            return known_submissions[cik]

    return _Stub()


def test_seed_writes_valid_sidecar_and_stub_markdown(tmp_path):
    """One-ticker happy path: fetch, transform, validate, write."""
    facts = json.loads((FIXTURES / "company_facts_JPM.json").read_text())
    submissions = json.loads((FIXTURES / "submissions_JPM.json").read_text())
    finqa_rows = json.loads((FIXTURES / "finqa_rows.json").read_text())

    edgar = _fake_edgar_client(
        known_facts={"0000019617": facts},
        known_submissions={"0000019617": submissions},
        known_ticker_map={"JPM": "0000019617"},
    )

    result = run.seed(
        tickers=["JPM"],
        out_dir=tmp_path,
        force=False,
        dry_run=False,
        edgar_client=edgar,
        finqa_rows=finqa_rows,
    )

    assert result.succeeded == 1
    assert result.failed == 0
    yaml_path = tmp_path / "companies" / "jpmorgan-chase.financials.yaml"
    md_path = tmp_path / "companies" / "jpmorgan-chase.md"
    assert yaml_path.exists()
    assert md_path.exists()

    # Sidecar must be schema-valid
    data = yaml.safe_load(yaml_path.read_text())
    errors = financials_validator.validate(data)
    assert errors == [], f"generated sidecar failed validation: {errors}"

    # Sidecar carries the JPM 2018 revenue we fed via fixture, in millions
    assert data["metrics"]["by_period"]["2018-FY"]["revenue"] == 108783.0  # from 108,783,000,000 → millions


def test_seed_is_idempotent_without_force(tmp_path):
    facts = json.loads((FIXTURES / "company_facts_JPM.json").read_text())
    submissions = json.loads((FIXTURES / "submissions_JPM.json").read_text())
    finqa_rows = json.loads((FIXTURES / "finqa_rows.json").read_text())

    edgar = _fake_edgar_client(
        known_facts={"0000019617": facts},
        known_submissions={"0000019617": submissions},
        known_ticker_map={"JPM": "0000019617"},
    )

    # First run: writes files
    run.seed(["JPM"], tmp_path, force=False, dry_run=False,
             edgar_client=edgar, finqa_rows=finqa_rows)

    # Second run: skips because sidecar already exists
    edgar2 = _fake_edgar_client(
        known_facts={"0000019617": facts},
        known_submissions={"0000019617": submissions},
        known_ticker_map={"JPM": "0000019617"},
    )
    result2 = run.seed(["JPM"], tmp_path, force=False, dry_run=False,
                       edgar_client=edgar2, finqa_rows=finqa_rows)
    assert result2.skipped == 1
    assert result2.per_ticker["JPM"]["reason"] == "sidecar_exists"


def test_seed_per_ticker_failure_does_not_poison_run(tmp_path):
    """One bad ticker (SEC 404) doesn't stop other tickers from succeeding."""
    facts = json.loads((FIXTURES / "company_facts_JPM.json").read_text())
    submissions = json.loads((FIXTURES / "submissions_JPM.json").read_text())
    finqa_rows = json.loads((FIXTURES / "finqa_rows.json").read_text())

    edgar = _fake_edgar_client(
        known_facts={"0000019617": facts},  # only JPM has facts
        known_submissions={"0000019617": submissions},
        known_ticker_map={"JPM": "0000019617", "AAPL": "0000320193"},
    )

    result = run.seed(["AAPL", "JPM"], tmp_path, force=False, dry_run=False,
                      edgar_client=edgar, finqa_rows=finqa_rows)
    assert result.succeeded == 1
    assert result.failed == 1
    assert result.per_ticker["JPM"]["seeded"] is True
    assert result.per_ticker["AAPL"]["seeded"] is False


def test_seed_preserves_diluted_eps_unscaled(tmp_path):
    """diluted_eps must NOT be divided by 1_000_000 — it's per-share, not millions of USD.

    Regression for P2 review finding C1: _to_millions_if_usd (now
    _scale_to_units) was blindly applied to every resolved metric, including
    EarningsPerShareDiluted (unit USD/shares, typical value $1-$15).
    round(5.30 / 1_000_000, 2) == 0.0 — silent corruption on live data.
    """
    facts = {
        "cik": 320193,
        "facts": {
            "us-gaap": {
                "EarningsPerShareDiluted": {
                    "label": "Earnings Per Share, Diluted",
                    "units": {
                        "USD/shares": [
                            {
                                "start": "2023-01-01",
                                "end": "2023-12-31",
                                "val": 5.30,
                                "accn": "0000320193-24-000001",
                                "fy": 2023,
                                "fp": "FY",
                                "form": "10-K",
                                "filed": "2024-02-01",
                            }
                        ]
                    },
                }
            }
        },
    }

    edgar = _fake_edgar_client(
        known_facts={"0000320193": facts},
        known_submissions={},  # no filings needed for this test
        known_ticker_map={"AAPL": "0000320193"},
    )

    result = run.seed(
        tickers=["AAPL"],
        out_dir=tmp_path,
        force=False,
        dry_run=False,
        edgar_client=edgar,
        finqa_rows=None,
    )

    assert result.succeeded == 1, result.per_ticker
    yaml_path = tmp_path / "companies" / "apple.financials.yaml"
    assert yaml_path.exists()
    data = yaml.safe_load(yaml_path.read_text())
    assert data["metrics"]["by_period"]["2023-FY"]["diluted_eps"] == 5.30


def test_find_10k_matches_non_calendar_fiscal_year():
    """AAPL's Sep-fiscal-year 10-K for FY2023 files in Nov-2023, not Nov-2024.

    Regression for P2 review finding I1: the old guard only accepted a
    filing date starting with `year + 1`, which assumes a Dec-31 fiscal year
    end. That silently drops filings for companies whose 10-K is filed
    within the fiscal year itself, leaving `filings` empty for roughly half
    the top-20 tickers.
    """
    filings_recent = {
        "accessionNumber": ["0000320193-23-000106"],
        "filingDate": ["2023-11-03"],
        "reportDate": ["2023-09-30"],
        "form": ["10-K"],
        "primaryDocument": ["aapl-20230930.htm"],
    }
    entry = run._find_10k_for_year(filings_recent, 2023, "0000320193")
    assert entry is not None
    assert entry["form"] == "10-K"
    assert entry["filed"] == "2023-11-03"
    assert "0000320193" in entry["source_url"]


def test_seed_dry_run_writes_nothing(tmp_path):
    facts = json.loads((FIXTURES / "company_facts_JPM.json").read_text())
    submissions = json.loads((FIXTURES / "submissions_JPM.json").read_text())
    finqa_rows = json.loads((FIXTURES / "finqa_rows.json").read_text())

    edgar = _fake_edgar_client(
        known_facts={"0000019617": facts},
        known_submissions={"0000019617": submissions},
        known_ticker_map={"JPM": "0000019617"},
    )
    result = run.seed(["JPM"], tmp_path, force=False, dry_run=True,
                      edgar_client=edgar, finqa_rows=finqa_rows)
    assert result.succeeded == 1
    assert not (tmp_path / "companies" / "jpmorgan-chase.financials.yaml").exists()


from tools.seed_finance import __main__ as cli


def test_cli_parses_n_companies():
    args = cli.parse_args([
        "--n-companies", "5",
        "--out-dir", "/tmp/out",
        "--dry-run",
    ])
    assert args.n_companies == 5
    assert args.out_dir == "/tmp/out"
    assert args.dry_run is True
    assert args.force is False


def test_cli_parses_ticker_list():
    args = cli.parse_args([
        "--ticker", "JPM",
        "--ticker", "AAPL",
    ])
    assert args.ticker == ["JPM", "AAPL"]
