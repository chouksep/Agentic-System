"""Tests for CLI argument parsing and command dispatch (main.py)."""
from __future__ import annotations

import sys
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from main import build_parser, main


# ---------------------------------------------------------------------------
# Argument parser tests
# ---------------------------------------------------------------------------

def test_parser_ingest_source():
    parser = build_parser()
    args = parser.parse_args(["ingest", "--source", "https://openai.com/pricing"])
    assert args.command == "ingest"
    assert args.source == "https://openai.com/pricing"
    assert not args.all


def test_parser_ingest_all():
    parser = build_parser()
    args = parser.parse_args(["ingest", "--all"])
    assert args.command == "ingest"
    assert args.all
    assert args.source is None


def test_parser_query_basic():
    parser = build_parser()
    args = parser.parse_args(["query", "What is OpenAI's pricing strategy vs Anthropic?"])
    assert args.command == "query"
    assert args.question == "What is OpenAI's pricing strategy vs Anthropic?"
    assert not args.save


def test_parser_query_with_save():
    parser = build_parser()
    args = parser.parse_args(["query", "What is GPT-4o pricing?", "--save"])
    assert args.command == "query"
    assert args.save


def test_parser_lint_default():
    parser = build_parser()
    args = parser.parse_args(["lint"])
    assert args.command == "lint"
    assert not args.dry_run
    assert not args.no_llm


def test_parser_lint_dry_run():
    parser = build_parser()
    args = parser.parse_args(["lint", "--dry-run"])
    assert args.command == "lint"
    assert args.dry_run
    assert not args.no_llm


def test_parser_lint_no_llm():
    parser = build_parser()
    args = parser.parse_args(["lint", "--no-llm"])
    assert args.no_llm
    assert not args.dry_run


def test_parser_lint_dry_run_and_no_llm():
    parser = build_parser()
    args = parser.parse_args(["lint", "--dry-run", "--no-llm"])
    assert args.dry_run
    assert args.no_llm


def test_parser_status():
    parser = build_parser()
    args = parser.parse_args(["status"])
    assert args.command == "status"


def test_parser_index():
    parser = build_parser()
    args = parser.parse_args(["index"])
    assert args.command == "index"


def test_parser_model_override():
    parser = build_parser()
    args = parser.parse_args(["--model", "claude-opus-4-6", "query", "test question"])
    assert args.model == "claude-opus-4-6"
    assert args.command == "query"


def test_parser_requires_subcommand():
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args([])


# ---------------------------------------------------------------------------
# Command dispatch tests — components mocked to avoid real I/O or API calls
# ---------------------------------------------------------------------------

def _make_mock_components(tmp_path):
    """Return a tuple of mock objects mimicking _get_components() output."""
    from ci_wiki.config import Config
    from ci_wiki.db import Database
    from ci_wiki.wiki.page import WikiPageIO
    from ci_wiki.wiki.index import WikiIndex

    wiki_dir = tmp_path / "wiki"
    for sub in ("companies", "products", "people", "trends"):
        (wiki_dir / sub).mkdir(parents=True)
    (wiki_dir / "index.md").write_text("# Index\n")

    schema = tmp_path / "schema" / "wiki_schema.md"
    schema.parent.mkdir()
    schema.write_text("# Schema\nYou are an analyst.")

    (tmp_path / "data").mkdir(exist_ok=True)
    sources_dir = tmp_path / "sources"
    sources_dir.mkdir(exist_ok=True)

    config = Config(
        repo_root=tmp_path,
        wiki_dir=wiki_dir,
        sources_dir=sources_dir,
        schema_file=schema,
        db_path=tmp_path / "data" / "test.db",
        anthropic_api_key="test-key",
    )
    db = Database(":memory:")
    db.connect()
    mock_llm = MagicMock()
    mock_llm.complete_with_tools.return_value = ("Test answer.", 500)
    page_io = WikiPageIO(wiki_dir)
    index = WikiIndex(wiki_dir, page_io)
    return config, db, mock_llm, page_io, index


def test_cmd_status(tmp_path, capsys):
    config, db, llm, page_io, index = _make_mock_components(tmp_path)
    with patch("main._get_components", return_value=(config, db, llm, page_io, index)):
        args = build_parser().parse_args(["status"])
        from main import cmd_status
        rc = cmd_status(args)
    captured = capsys.readouterr()
    assert rc == 0
    assert "Sources total" in captured.out


def test_cmd_index(tmp_path, capsys):
    config, db, llm, page_io, index = _make_mock_components(tmp_path)
    with patch("main._get_components", return_value=(config, db, llm, page_io, index)):
        args = build_parser().parse_args(["index"])
        from main import cmd_index
        rc = cmd_index(args)
    captured = capsys.readouterr()
    assert rc == 0
    assert "Done" in captured.out


def test_cmd_ingest_requires_source_or_all(tmp_path, capsys):
    config, db, llm, page_io, index = _make_mock_components(tmp_path)
    with patch("main._get_components", return_value=(config, db, llm, page_io, index)):
        args = build_parser().parse_args(["ingest"])
        from main import cmd_ingest
        rc = cmd_ingest(args)
    assert rc == 1


def test_cmd_query_returns_answer(tmp_path, capsys):
    config, db, llm, page_io, index = _make_mock_components(tmp_path)
    with patch("main._get_components", return_value=(config, db, llm, page_io, index)):
        args = build_parser().parse_args(["query", "What is OpenAI's pricing strategy vs Anthropic?"])
        from main import cmd_query
        rc = cmd_query(args)
    captured = capsys.readouterr()
    assert rc == 0
    assert "Test answer." in captured.out


def test_cmd_lint_dry_run(tmp_path, capsys):
    config, db, llm, page_io, index = _make_mock_components(tmp_path)
    with patch("main._get_components", return_value=(config, db, llm, page_io, index)):
        args = build_parser().parse_args(["lint", "--dry-run"])
        from main import cmd_lint
        rc = cmd_lint(args)
    assert rc == 0


def test_main_dispatches_status(tmp_path, capsys):
    config, db, llm, page_io, index = _make_mock_components(tmp_path)
    with patch("main._get_components", return_value=(config, db, llm, page_io, index)):
        with patch("sys.argv", ["ci-wiki", "status"]):
            rc = main()
    assert rc == 0


def test_main_model_override_sets_env(tmp_path, monkeypatch):
    config, db, llm, page_io, index = _make_mock_components(tmp_path)
    import os
    monkeypatch.delenv("CI_WIKI_MODEL", raising=False)
    with patch("main._get_components", return_value=(config, db, llm, page_io, index)):
        with patch("sys.argv", ["ci-wiki", "--model", "claude-opus-4-6", "status"]):
            main()
    assert os.environ.get("CI_WIKI_MODEL") == "claude-opus-4-6"
