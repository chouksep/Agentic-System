"""Tests for the LLM-based entity-mention verifier.

All tests inject `verifier_fn` or a fake anthropic client — no real API calls.
"""
from __future__ import annotations

from benchmarks.runner.datasets.llm_verifier import (
    ENTITY_DESCRIPTIONS,
    verify,
)


def test_verifier_fn_short_circuits_llm():
    calls: list[tuple] = []

    def fake_verifier(question: str, entity_key: tuple) -> bool:
        calls.append((question, entity_key))
        return question.startswith("KEEP:")

    ok = verify("KEEP: Who founded OpenAI?", "openai", "company", verifier_fn=fake_verifier)
    drop = verify("Jean-Claude Killy Olympic gold", "claude", "product", verifier_fn=fake_verifier)
    assert ok is True
    assert drop is False
    assert calls == [
        ("KEEP: Who founded OpenAI?", ("openai", "company")),
        ("Jean-Claude Killy Olympic gold", ("claude", "product")),
    ]


def test_unknown_entity_key_drops_case():
    # Entity not in ENTITY_DESCRIPTIONS should be conservatively dropped.
    result = verify("Some question", "tesla", "company")
    assert result is False


def test_all_wiki_entities_have_descriptions():
    # Sanity: every entity we plan to feed the verifier must have a description
    # so the LLM has enough context to disambiguate.
    expected_min_keys = {
        ("openai", "company"),
        ("anthropic", "company"),
        ("claude", "product"),
        ("chatgpt", "product"),
        ("gemini", "product"),
        ("dario-amodei", "person"),
        ("sam-altman", "person"),
    }
    missing = expected_min_keys - set(ENTITY_DESCRIPTIONS.keys())
    assert not missing, f"missing descriptions: {missing}"


class _FakeBlock:
    def __init__(self, type_, text=""):
        self.type = type_
        self.text = text


class _FakeUsage:
    input_tokens = 0
    output_tokens = 0


class _FakeResp:
    def __init__(self, text):
        self.content = [_FakeBlock("text", text=text)]
        self.stop_reason = "end_turn"
        self.usage = _FakeUsage()


class _FakeMessages:
    def __init__(self, response_text: str):
        self._text = response_text
        self.calls: list[dict] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return _FakeResp(self._text)


class _FakeAnthropicClient:
    def __init__(self, response_text: str):
        self.messages = _FakeMessages(response_text)


def test_llm_yes_response_returns_true():
    client = _FakeAnthropicClient("YES")
    result = verify(
        "Who founded OpenAI?",
        "openai", "company",
        anthropic_client=client,
    )
    assert result is True
    # Verify the prompt actually mentions our target entity + question
    prompt = client.messages.calls[0]["messages"][0]["content"]
    assert "Openai" in prompt or "openai" in prompt.lower()
    assert "Who founded OpenAI?" in prompt


def test_llm_no_response_returns_false():
    client = _FakeAnthropicClient("NO — this question is about Jean-Claude Killy the skier")
    result = verify(
        "Give either the year or the venue when Jean-Claude Killy won gold",
        "claude", "product",
        anthropic_client=client,
    )
    assert result is False


def test_llm_api_error_returns_false_fail_closed():
    class _BrokenClient:
        class messages:
            @staticmethod
            def create(**_):
                raise RuntimeError("API is down")

    result = verify(
        "Who founded OpenAI?",
        "openai", "company",
        anthropic_client=_BrokenClient(),
    )
    # Fail-closed: rather drop a candidate than accept a mis-labelled one.
    assert result is False


def test_llm_response_is_case_insensitive_yes():
    for text in ("YES", "yes", "Yes.", " YES\n", "yes."):
        client = _FakeAnthropicClient(text)
        assert verify(
            "Who is Dario Amodei?", "dario-amodei", "person",
            anthropic_client=client,
        ) is True, f"failed for {text!r}"


def test_llm_response_is_case_insensitive_no():
    for text in ("NO", "no", "No.", " no\n", "No — unrelated entity"):
        client = _FakeAnthropicClient(text)
        assert verify(
            "Who is Dario Argento?", "dario-amodei", "person",
            anthropic_client=client,
        ) is False, f"failed for {text!r}"
