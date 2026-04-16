# Contributing to ci-wiki

Thank you for your interest in contributing! This document describes how to set up a development environment, run tests, and submit changes.

## Getting Started

```bash
git clone https://github.com/chouksep/Agentic-System.git
cd Agentic-System
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

Configure Databricks credentials before running integration tests (see [README.md § Setup](README.md#setup)).

## Running Tests

```bash
pytest                     # all tests
pytest tests/test_db.py    # single module
pytest -x                  # stop on first failure
```

All tests must pass before a pull request can be merged.

## Code Style

- **Formatter**: [`ruff format`](https://docs.astral.sh/ruff/) — run before committing.
- **Linter**: `ruff check` — CI will fail on lint errors.
- **Type hints**: all public functions must have type annotations.
- **Imports**: use `from __future__ import annotations` at the top of every module.

```bash
ruff format .
ruff check .
```

## Submitting Changes

1. **Fork** the repository and create a branch from `main`:
   ```bash
   git checkout -b feat/my-feature
   ```
2. Make your changes with focused, atomic commits.
3. Add or update tests for any new behaviour.
4. Open a **pull request** against `main` with a clear description of *what* changed and *why*.

## Commit Message Convention

Use the [Conventional Commits](https://www.conventionalcommits.org/) format:

```
<type>(<scope>): <short summary>

[optional body]
```

Common types: `feat`, `fix`, `docs`, `test`, `refactor`, `chore`.

Examples:
```
feat(ingest): add support for .docx source files
fix(fetcher): handle redirect loops when fetching RSS feeds
docs(readme): add troubleshooting section
```

## Reporting Issues

Open a [GitHub Issue](https://github.com/chouksep/Agentic-System/issues) with:
- A clear title and description
- Steps to reproduce (for bugs)
- Expected vs. actual behaviour
- Python version and OS

For security vulnerabilities, see [SECURITY.md](SECURITY.md) — **do not open a public issue**.
