"""SEC EDGAR HTTP client.

Three endpoints:
  - Company Facts:  data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json
  - Submissions:    data.sec.gov/submissions/CIK{cik}.json
  - Ticker master:  www.sec.gov/files/company_tickers.json

SEC requires a distinctive User-Agent per its docs. Rate limit is 10 req/s;
we target 8 req/s (0.125s min interval). Retries on 429 or 5xx with
exponential backoff (1s, 4s); gives up after 3 total attempts.
"""
from __future__ import annotations

import time
from typing import Any

import requests

_COMPANY_FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
_TICKER_MAP_URL = "https://www.sec.gov/files/company_tickers.json"

_MAX_ATTEMPTS = 3
_BACKOFF_SECONDS = (1.0, 4.0)  # index 0 = after 1st failure, etc.


class SecEdgarError(Exception):
    """Base exception for SEC EDGAR client failures."""


class NotFound(SecEdgarError):
    """SEC returned 404 (endpoint / CIK doesn't exist)."""


class RateLimitExceeded(SecEdgarError):
    """SEC returned 429 more times than the retry budget allows."""


class SecEdgarClient:
    def __init__(
        self,
        user_agent: str,
        session: Any = None,
        sleep_seconds: float = 0.125,
    ) -> None:
        if not user_agent:
            raise ValueError("SEC EDGAR requires a distinctive User-Agent")
        self._user_agent = user_agent
        self._session = session if session is not None else requests.Session()
        self._sleep = sleep_seconds
        self._last_request_at = 0.0

    def fetch_company_facts(self, cik: str) -> dict:
        return self._get(_COMPANY_FACTS_URL.format(cik=cik))

    def fetch_submissions(self, cik: str) -> dict:
        return self._get(_SUBMISSIONS_URL.format(cik=cik))

    def load_ticker_map(self) -> dict[str, str]:
        """Return {TICKER: cik10} with CIKs zero-padded to 10 digits."""
        raw = self._get(_TICKER_MAP_URL)
        out: dict[str, str] = {}
        for _idx, entry in raw.items():
            ticker = entry.get("ticker")
            cik_int = entry.get("cik_str")
            if ticker and cik_int is not None:
                out[ticker] = str(cik_int).zfill(10)
        return out

    def _get(self, url: str) -> dict:
        """GET with rate-limit + backoff + retry. Returns parsed JSON."""
        last_status: int | None = None
        for attempt in range(_MAX_ATTEMPTS):
            self._respect_rate_limit()
            resp = self._session.get(
                url,
                headers={"User-Agent": self._user_agent},
                timeout=30,
            )
            self._last_request_at = time.monotonic()
            last_status = resp.status_code
            if resp.status_code == 200:
                return resp.json()
            if resp.status_code == 404:
                raise NotFound(f"SEC EDGAR returned 404 for {url}")
            if resp.status_code == 429 or 500 <= resp.status_code < 600:
                # retryable — back off and try again unless we're out of attempts
                if attempt < len(_BACKOFF_SECONDS):
                    time.sleep(_BACKOFF_SECONDS[attempt])
                    continue
                break
            # Any other status is a hard error
            raise SecEdgarError(
                f"SEC EDGAR returned unexpected status {resp.status_code} for {url}"
            )
        # Fell out of the loop after exhausting retries
        if last_status == 429:
            raise RateLimitExceeded(
                f"SEC EDGAR rate-limited after {_MAX_ATTEMPTS} attempts on {url}"
            )
        raise SecEdgarError(
            f"SEC EDGAR failed after {_MAX_ATTEMPTS} attempts on {url} (last status {last_status})"
        )

    def _respect_rate_limit(self) -> None:
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < self._sleep:
            time.sleep(self._sleep - elapsed)
