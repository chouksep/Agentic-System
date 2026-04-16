from __future__ import annotations

import time
import threading


class TokenBucket:
    """Thread-safe token bucket for rate limiting."""

    def __init__(self, capacity: int, refill_rate: float) -> None:
        """
        Args:
            capacity: Maximum tokens in the bucket.
            refill_rate: Tokens added per second.
        """
        self._capacity = capacity
        self._refill_rate = refill_rate
        self._tokens = float(capacity)
        self._last_refill = time.monotonic()
        self._lock = threading.Lock()

    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last_refill
        self._tokens = min(self._capacity, self._tokens + elapsed * self._refill_rate)
        self._last_refill = now

    def consume(self, tokens: int = 1) -> None:
        """Block until `tokens` are available, then consume them."""
        while True:
            with self._lock:
                self._refill()
                if self._tokens >= tokens:
                    self._tokens -= tokens
                    return
                # compute wait time
                deficit = tokens - self._tokens
                wait = deficit / self._refill_rate
            time.sleep(wait)

    def try_consume(self, tokens: int = 1) -> bool:
        """Non-blocking. Returns True if tokens were available and consumed."""
        with self._lock:
            self._refill()
            if self._tokens >= tokens:
                self._tokens -= tokens
                return True
            return False


class RateLimiter:
    """Dual token-bucket rate limiter for requests-per-minute and tokens-per-minute."""

    def __init__(self, rpm: int, tpm: int) -> None:
        self._rpm_bucket = TokenBucket(capacity=rpm, refill_rate=rpm / 60.0)
        self._tpm_bucket = TokenBucket(capacity=tpm, refill_rate=tpm / 60.0)

    def acquire_request(self, estimated_tokens: int = 1000) -> None:
        """Block until both RPM and TPM budgets allow the request."""
        self._rpm_bucket.consume(1)
        self._tpm_bucket.consume(estimated_tokens)

    def record_actual_tokens(self, estimated_tokens: int, actual_tokens: int) -> None:
        """Reconcile TPM bucket if actual usage differed from estimate.
        If we over-estimated, add tokens back.
        """
        diff = estimated_tokens - actual_tokens
        if diff > 0:
            # give back the over-estimated tokens (non-blocking)
            self._tpm_bucket.try_consume(-diff)  # effectively adds back
