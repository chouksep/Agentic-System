"""Tests for TokenBucket and RateLimiter."""
from __future__ import annotations

import pytest
import time

from ci_wiki.utils.ratelimit import TokenBucket, RateLimiter


class TestTokenBucket:
    def test_initial_tokens_at_capacity(self):
        bucket = TokenBucket(capacity=100, refill_rate=10.0)
        assert bucket._tokens == 100.0

    def test_consume_reduces_tokens(self):
        bucket = TokenBucket(capacity=100, refill_rate=10.0)
        bucket.consume(30)
        assert bucket._tokens == pytest.approx(70.0, abs=1.0)

    def test_try_consume_returns_true_when_available(self):
        bucket = TokenBucket(capacity=100, refill_rate=10.0)
        result = bucket.try_consume(50)
        assert result is True
        assert bucket._tokens == pytest.approx(50.0, abs=1.0)

    def test_try_consume_returns_false_when_insufficient(self):
        bucket = TokenBucket(capacity=100, refill_rate=10.0)
        bucket.try_consume(100)  # drain the bucket
        result = bucket.try_consume(1)
        assert result is False

    def test_refund_tokens_increases_balance(self):
        bucket = TokenBucket(capacity=100, refill_rate=10.0)
        bucket.try_consume(80)  # 20 tokens left
        bucket.refund_tokens(30)
        assert bucket._tokens == pytest.approx(50.0, abs=1.0)

    def test_refund_tokens_does_not_exceed_capacity(self):
        bucket = TokenBucket(capacity=100, refill_rate=10.0)
        bucket.try_consume(10)  # 90 tokens left
        bucket.refund_tokens(50)  # would push to 140, should cap at 100
        assert bucket._tokens == pytest.approx(100.0, abs=0.01)

    def test_refund_tokens_from_empty_bucket_caps_at_capacity(self):
        bucket = TokenBucket(capacity=50, refill_rate=5.0)
        bucket.try_consume(50)  # fully drained
        bucket.refund_tokens(200)  # large refund — should cap at 50
        assert bucket._tokens == pytest.approx(50.0, abs=0.01)

    def test_refund_zero_tokens_is_noop(self):
        bucket = TokenBucket(capacity=100, refill_rate=10.0)
        bucket.try_consume(40)
        before = bucket._tokens
        bucket.refund_tokens(0)
        assert bucket._tokens == pytest.approx(before, abs=0.01)


class TestRateLimiter:
    def test_record_actual_tokens_refunds_overestimate(self):
        limiter = RateLimiter(rpm=60, tpm=10000)
        # Drain most of the TPM bucket
        limiter._tpm_bucket.try_consume(8000)  # 2000 left
        tokens_before = limiter._tpm_bucket._tokens

        # Simulate: estimated 500, actual 200 → should refund 300
        limiter.record_actual_tokens(estimated_tokens=500, actual_tokens=200)
        assert limiter._tpm_bucket._tokens == pytest.approx(tokens_before + 300, abs=1.0)

    def test_record_actual_tokens_no_refund_when_underestimate(self):
        limiter = RateLimiter(rpm=60, tpm=10000)
        limiter._tpm_bucket.try_consume(5000)  # 5000 left
        tokens_before = limiter._tpm_bucket._tokens

        # Actual > estimated → nothing to refund
        limiter.record_actual_tokens(estimated_tokens=100, actual_tokens=300)
        assert limiter._tpm_bucket._tokens == pytest.approx(tokens_before, abs=0.01)

    def test_record_actual_tokens_refund_does_not_exceed_capacity(self):
        limiter = RateLimiter(rpm=60, tpm=1000)
        # bucket is nearly full (950 tokens)
        limiter._tpm_bucket.try_consume(50)
        # Refund 200 tokens — should cap at 1000
        limiter.record_actual_tokens(estimated_tokens=200, actual_tokens=0)
        assert limiter._tpm_bucket._tokens <= limiter._tpm_bucket._capacity

    def test_acquire_request_consumes_rpm_and_tpm(self):
        limiter = RateLimiter(rpm=60, tpm=10000)
        initial_rpm = limiter._rpm_bucket._tokens
        initial_tpm = limiter._tpm_bucket._tokens
        limiter.acquire_request(estimated_tokens=500)
        assert limiter._rpm_bucket._tokens < initial_rpm
        assert limiter._tpm_bucket._tokens < initial_tpm
