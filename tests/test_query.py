"""Tests for QueryOp — uses mocked LLM client."""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock

from ci_wiki.ops.query import QueryOp
from ci_wiki.wiki.index import WikiIndex
from ci_wiki.wiki.page import WikiPageIO
from tests.conftest import make_wiki_page


@pytest.fixture
def populated_wiki(tmp_wiki_dir, test_db):
    openai = make_wiki_page(
        tmp_wiki_dir, "openai", "company", "OpenAI",
        "## Overview\nOpenAI builds GPT models.\n\n## Pricing\nGPT-4o: $5/1M tokens.\n<!-- confidence: high | source_count: 2 -->\n\n## Sources\nhttp://example.com"
    )
    gpt4o = make_wiki_page(
        tmp_wiki_dir, "gpt-4o", "product", "GPT-4o",
        "## Overview\nFlagship multimodal model.\n\n## Pricing\n$5 per 1M input tokens, $15 per 1M output tokens.\n\n## Sources\nhttp://openai.com/pricing"
    )
    test_db.upsert_page(openai)
    test_db.upsert_page(gpt4o)
    return tmp_wiki_dir


@pytest.fixture
def query_op(test_config, test_db, populated_wiki):
    page_io = WikiPageIO(populated_wiki)
    index = WikiIndex(populated_wiki, page_io)
    mock_llm = MagicMock()
    mock_llm.complete_with_tools.return_value = (
        "**Direct Answer**: GPT-4o costs $5 per 1M input tokens.\n\n"
        "**Supporting Evidence**: Per [[product:gpt-4o]], pricing is $5/1M input, $15/1M output.\n\n"
        "**Confidence**: high\n\n**Gaps**: Enterprise pricing not available.",
        1500,
    )
    return QueryOp(config=test_config, db=test_db, llm=mock_llm, page_io=page_io, index=index)


def test_query_returns_answer(query_op):
    result = query_op.run("What is GPT-4o pricing?")
    assert result.answer != ""
    assert "GPT-4o" in result.answer or "gpt-4o" in result.answer.lower()


def test_query_reports_tokens(query_op):
    result = query_op.run("What is GPT-4o pricing?")
    assert result.tokens_used > 0


def test_query_has_question(query_op):
    result = query_op.run("What is GPT-4o pricing?")
    assert result.question == "What is GPT-4o pricing?"


def test_query_save_files_to_wiki(query_op, populated_wiki):
    result = query_op.run("What is GPT-4o pricing?", save=True)
    assert result.filed_to is not None
    from pathlib import Path
    assert Path(result.filed_to).exists()


def test_query_save_contains_question(query_op, populated_wiki):
    result = query_op.run("What is GPT-4o pricing?", save=True)
    from pathlib import Path
    content = Path(result.filed_to).read_text()
    assert "GPT-4o" in content


def test_query_empty_wiki(test_config, test_db, tmp_wiki_dir, tmp_schema_file):
    page_io = WikiPageIO(tmp_wiki_dir)
    index = WikiIndex(tmp_wiki_dir, page_io)
    mock_llm = MagicMock()
    mock_llm.complete_with_tools.return_value = (
        "The wiki does not contain information about this topic.", 200
    )
    op = QueryOp(config=test_config, db=test_db, llm=mock_llm, page_io=page_io, index=index)
    result = op.run("What is the meaning of life?")
    assert result.answer != ""
