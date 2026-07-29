"""FinQA agent: run one question through ci_wiki's financials-tool loop.

Uses LLMClient.complete_with_tools with FINANCIALS_TOOLS only (no wiki
read/search). A _CountingDispatcher wraps ToolDispatcher to record tool-call
count and enforce a hard cap (_MAX_TOOL_CALLS).
"""
from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from pathlib import Path

from ci_wiki.llm.client import LLMClient
from ci_wiki.llm.tools import FINANCIALS_TOOLS, ToolCall, ToolDispatcher
from ci_wiki.wiki.page import WikiPageIO
from ci_wiki.wiki.search import WikiSearch

from benchmarks.runner.datasets.finqa import FinqaCase, _parse_answer

_MAX_TOOL_CALLS = 10
_MAX_ITERATIONS = 10  # matches LLMClient default; kept explicit


_SYSTEM_PROMPT = (
    "You are a financial-QA assistant. Answer with a single number and a "
    "unit (millions / billions / % / ratio / raw). "
    "If the question asks 'what percentage of X is Y' or 'what portion of X', "
    "you MUST compute Y/X and answer as a percentage; do NOT answer with the "
    "raw dollar amount of Y or X. Similarly, if the question asks for a "
    "'change' or 'growth rate' expressed as a percentage, compute "
    "(new - old) / old * 100 and answer as %. "
    "If the value is not in the sidecar, respond exactly NOT_AVAILABLE. "
    "Do not show your work. "
    "End your response with a line 'FINAL_ANSWER: <number> <unit>' where unit "
    "is one of millions/billions/%/ratio/raw. "
    "When the question references a specific segment, business line, table "
    "row, or footnote (e.g., 'Risk Solutions segment', 'aeronautics', "
    "'purchased technology'), prefer get_filing_table over get_metric_series "
    "— the standardized metric series is CONSOLIDATED and won't have the "
    "sub-line detail."
)

_USER_TEMPLATE = (
    "Company ticker: {ticker}\n"
    "Fiscal year hint: {year}\n"
    "Question: {question}\n"
    "Use the financials tools to look up the answer, then respond with the "
    "single number and unit."
)

# Very permissive: last non-empty line, or last number + trailing token.
_LAST_NUMBER_RE = re.compile(r"(-?\$?\s*\d[\d,]*(?:\.\d+)?\s*(?:%|million(?:s)?|billion(?:s)?|mn|bn|x|:\s*1)?)", re.IGNORECASE)

# Explicit marker the system prompt asks the model to emit as the last line,
# e.g. "FINAL_ANSWER: -12.4 %" or "FINAL_ANSWER: 47 raw". Preferred over the
# permissive regex below because it pins down exactly one value/unit and
# preserves a leading sign that the permissive scan can otherwise lose.
_FINAL_ANSWER_RE = re.compile(r"^\s*FINAL_ANSWER:\s*(\S+.*)$", re.IGNORECASE | re.MULTILINE)

# Unit tokens that mark a match as more likely the actual answer than a bare
# year or index reference. When any match carries one of these suffixes, we
# prefer the LAST such match over the LAST bare number.
_UNIT_TOKEN_RE = re.compile(r"(%|million|billion|mn|bn|x|:\s*1)", re.IGNORECASE)


class _CountingDispatcher(ToolDispatcher):
    def __init__(self, page_io, search, wiki_dir: Path) -> None:
        super().__init__(page_io, search, wiki_dir)
        self.tool_call_count = 0

    def dispatch(self, tool_call: ToolCall) -> str:
        if self.tool_call_count >= _MAX_TOOL_CALLS:
            return json.dumps({"error": "tool_call_cap_exceeded",
                               "cap": _MAX_TOOL_CALLS})
        self.tool_call_count += 1
        return super().dispatch(tool_call)


@dataclass
class FinqaAgentRecord:
    final_text: str
    parsed_value: float | None
    parsed_unit: str | None
    parse_error: str | None
    tool_call_count: int
    cost_usd: float
    latency_s: float


def _extract_answer(text: str) -> tuple[float | None, str | None, str | None]:
    """Return (value, unit, parse_error). parse_error one of None|'not_available'|'regex_fail'."""
    stripped = text.strip()
    if not stripped:
        return None, None, "regex_fail"
    if "NOT_AVAILABLE" in stripped.upper():
        return None, None, "not_available"

    # Prefer the explicit FINAL_ANSWER marker (last occurrence, in case the
    # model repeats it) — it is unambiguous about which value is the answer.
    marker_matches = list(_FINAL_ANSWER_RE.finditer(stripped))
    if marker_matches:
        candidate = marker_matches[-1].group(1).strip()
        try:
            value, unit = _parse_answer(candidate)
            return value, unit, None
        except ValueError:
            pass  # fall through to permissive scan below

    # Prefer the last match that carries a unit token (%, million, billion, x)
    # over trailing bare numbers, which are often years or index bases the
    # model quoted after the actual answer.
    matches = list(_LAST_NUMBER_RE.finditer(stripped))
    if not matches:
        return None, None, "regex_fail"
    unit_tagged = [m for m in matches if _UNIT_TOKEN_RE.search(m.group(0))]
    chosen = unit_tagged[-1] if unit_tagged else matches[-1]
    candidate = chosen.group(0)
    try:
        value, unit = _parse_answer(candidate)
    except ValueError:
        return None, None, "regex_fail"
    return value, unit, None


class FinqaAgent:
    def __init__(self, llm_client: LLMClient, wiki_dir: Path) -> None:
        self._llm = llm_client
        self._wiki_dir = Path(wiki_dir)
        # Real WikiPageIO / WikiSearch aren't used by FINANCIALS_TOOLS but
        # ToolDispatcher.__init__ requires them. Constructing them is cheap.
        self._page_io = WikiPageIO(self._wiki_dir)
        self._search = WikiSearch([])

    def answer(self, case: FinqaCase) -> FinqaAgentRecord:
        dispatcher = _CountingDispatcher(self._page_io, self._search, self._wiki_dir)
        user_msg = _USER_TEMPLATE.format(ticker=case.ticker, year=case.year, question=case.question)

        start = time.monotonic()
        final_text, _tokens = self._llm.complete_with_tools(
            system=_SYSTEM_PROMPT,
            initial_user_message=user_msg,
            tools=FINANCIALS_TOOLS,
            dispatcher=dispatcher,
            max_iterations=_MAX_ITERATIONS,
        )
        latency = time.monotonic() - start

        value, unit, parse_error = _extract_answer(final_text)

        # Cost approximation is deferred to a follow-up; report 0.0 for now.
        return FinqaAgentRecord(
            final_text=final_text,
            parsed_value=value,
            parsed_unit=unit,
            parse_error=parse_error,
            tool_call_count=dispatcher.tool_call_count,
            cost_usd=0.0,
            latency_s=latency,
        )
