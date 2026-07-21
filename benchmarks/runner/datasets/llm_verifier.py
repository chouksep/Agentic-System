"""LLM-based verifier for wiki-entity mentions in QA-corpus questions.

The naive whole-word slug match in `EntityIndex.match()` over-triggers on
broad-domain corpora — "Jean-Claude Killy" matches slug `claude` (our AI
product); "Gemini zodiac" matches slug `gemini`; etc. This module raises
precision to near-perfect by asking a cheap LLM (Claude Haiku 4.5 by
default) to confirm each candidate mention.

Two-stage pipeline:
    1. `EntityIndex.match(question)` yields (slug, page_type) candidates.
    2. For each candidate, call `verify(question, slug, page_type)` — the
       loader keeps only questions where the LLM returns True.

Cost is negligible for our scale — a Haiku-4.5 call on a ~50-token prompt
runs ~$0.0002. Filtering a full 200-candidate slice of NQ-open + TriviaQA
therefore costs roughly $0.04 total, one-shot per corpus.

Tests inject `verifier_fn` and never hit the real API.
"""
from __future__ import annotations

import logging
from typing import Callable, Protocol

log = logging.getLogger(__name__)

# The cheap model used by default. Override by passing `anthropic_client=`
# or `verifier_fn=` to `verify()`.
_VERIFIER_MODEL = "claude-haiku-4-5-20251001"
_VERIFIER_SYSTEM = (
    "You verify whether a question is about a specific target entity, or "
    "about an unrelated entity that happens to share the same or similar name."
)

_VERIFIER_PROMPT = """\
Target entity: "{entity_name}" ({page_type}) - {entity_description}

Question: "{question}"

Is this question about the target entity above, or about a different entity \
that happens to share the same or similar name (e.g., a person, place, \
astrological sign, fictional character, brand, or unrelated product)?

Answer with only one word: YES or NO.
- YES = the question is genuinely about the target entity above
- NO  = the question is about a differently-named entity, OR a same-named \
but unrelated entity (e.g., "Claude Francois the singer" vs "Claude the AI product")
"""

# Short human-readable descriptions of our ~18 wiki entities. Keeps the
# verifier prompt tight and makes the disambiguation unambiguous.
# Keys are (slug, page_type) tuples matching EntityIndex.match() output.
ENTITY_DESCRIPTIONS: dict[tuple[str, str], str] = {
    ("openai", "company"): "the AI company that built ChatGPT and GPT-4",
    ("anthropic", "company"): "the AI company that built Claude, founded by former OpenAI researchers",
    ("google-deepmind", "company"): "Google's AI research lab (formerly DeepMind)",
    ("claude", "product"): "Anthropic's AI assistant / large language model product",
    ("chatgpt", "product"): "OpenAI's chat product built on GPT-family models",
    ("gemini", "product"): "Google's AI assistant / large language model product",
    ("sam-altman", "person"): "CEO of OpenAI",
    ("dario-amodei", "person"): "CEO and co-founder of Anthropic",
    ("daniela-amodei", "person"): "President and co-founder of Anthropic",
    ("greg-brockman", "person"): "co-founder of OpenAI",
    ("ilya-sutskever", "person"): "co-founder and former Chief Scientist of OpenAI",
    ("demis-hassabis", "person"): "co-founder and CEO of Google DeepMind",
    ("mustafa-suleyman", "person"): "co-founder of DeepMind, later Inflection AI, now Microsoft AI",
    ("elon-musk", "person"): "billionaire; co-founder of OpenAI, later founder of xAI",
    ("generative-ai-rise", "trend"): "the industry-wide rise of generative AI (LLMs, image models) since ~2022",
}


class _AnthropicLike(Protocol):
    class messages:
        def create(self, **kwargs) -> object: ...


# Signature for injected test verifiers. Takes (question, (slug, page_type))
# and returns True to keep, False to drop.
VerifierFn = Callable[[str, tuple[str, str]], bool]


def verify(
    question: str,
    slug: str,
    page_type: str,
    *,
    verifier_fn: VerifierFn | None = None,
    anthropic_client: _AnthropicLike | None = None,
) -> bool:
    """Ask the verifier whether `question` is genuinely about (slug, page_type).

    Returns True to keep the case, False to drop.

    Failure-mode: on any LLM error, returns False (fail-closed — we'd rather
    silently drop a case than accept a wrongly-labelled one that would then
    penalize the agent).

    Test injection: `verifier_fn(question, entity_key) -> bool` bypasses the
    LLM entirely. When None (default), builds an Anthropic client from the
    session's Config on first call.
    """
    entity_key = (slug, page_type)

    if verifier_fn is not None:
        return verifier_fn(question, entity_key)

    description = ENTITY_DESCRIPTIONS.get(entity_key)
    if description is None:
        # Unknown target entity — conservatively drop. The caller should
        # only be feeding us entities whose description we own.
        log.warning("llm_verifier: no description for %s — dropping case", entity_key)
        return False

    if anthropic_client is None:
        anthropic_client = _default_client()

    # Convert slug to a readable display name (e.g., "dario-amodei" ->
    # "Dario Amodei"). Uses the slug rather than any frontmatter `name`
    # field to stay robust to the wiki's YAML being unreadable.
    entity_display = " ".join(w.capitalize() for w in slug.split("-"))
    prompt = _VERIFIER_PROMPT.format(
        entity_name=entity_display,
        page_type=page_type,
        entity_description=description,
        question=question,
    )
    try:
        resp = anthropic_client.messages.create(
            model=_VERIFIER_MODEL,
            max_tokens=8,
            system=_VERIFIER_SYSTEM,
            messages=[{"role": "user", "content": prompt}],
        )
        text = ""
        for block in resp.content:
            if getattr(block, "type", None) == "text":
                text += block.text
        answer = text.strip().upper()
        return answer.startswith("YES")
    except Exception as exc:
        log.warning("llm_verifier: API call failed for %s: %s — dropping case",
                    entity_key, exc)
        return False


def _default_client():
    """Build an Anthropic client from ci_wiki.config. Lazy import."""
    import anthropic  # type: ignore[import-not-found]
    from ci_wiki.config import Config
    cfg = Config.from_env()
    if not cfg.anthropic_api_key:
        raise RuntimeError(
            "llm_verifier requires ANTHROPIC_API_KEY (loaded by ci_wiki.config). "
            "Either pass `verifier_fn=` explicitly or set the env var."
        )
    return anthropic.Anthropic(api_key=cfg.anthropic_api_key, max_retries=3)
