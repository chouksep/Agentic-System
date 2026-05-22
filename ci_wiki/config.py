from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from dotenv import load_dotenv

# Load .env from the repo root once at import time so any os.environ reads below
# pick up user-supplied secrets. override=False means shell-set vars still win.
load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=False)


_DATABRICKS_HOST_DEFAULT = "https://lnlp-databricks-dev-vpc133-shared.cloud.databricks.com"
_MODEL_DEFAULT = "databricks-claude-sonnet-4-6"
_ANTHROPIC_MODEL_DEFAULT = "claude-sonnet-4-5"


@dataclass
class Config:
    repo_root: Path
    wiki_dir: Path
    sources_dir: Path
    schema_file: Path
    db_path: Path
    databricks_host: str = _DATABRICKS_HOST_DEFAULT
    databricks_token: str = ""
    anthropic_api_key: str = ""
    model: str = _MODEL_DEFAULT
    max_tokens: int = 8192
    max_context_pages: int = 5
    bm25_top_k: int = 8
    rate_limit_rpm: int = 50
    rate_limit_tpm: int = 40000

    @property
    def use_anthropic(self) -> bool:
        """True when the Anthropic backend should be used instead of Databricks."""
        return bool(self.anthropic_api_key)

    @classmethod
    def from_env(cls, repo_root: Path | None = None) -> "Config":
        if repo_root is None:
            repo_root = Path(__file__).parent.parent.resolve()

        host = os.environ.get("DATABRICKS_HOST", _DATABRICKS_HOST_DEFAULT)
        token = os.environ.get("DATABRICKS_TOKEN", "")
        anthropic_api_key = os.environ.get("ANTHROPIC_API_KEY", "")

        cfg: dict = {}
        config_yaml = repo_root / "config.yaml"
        if config_yaml.exists():
            with config_yaml.open() as f:
                cfg = yaml.safe_load(f) or {}

        # If using Anthropic and the model has not been explicitly overridden,
        # default to the native Anthropic model name rather than the Databricks one.
        model = cfg.get("model", _MODEL_DEFAULT)
        if anthropic_api_key and model == _MODEL_DEFAULT:
            model = _ANTHROPIC_MODEL_DEFAULT

        return cls(
            repo_root=repo_root,
            wiki_dir=repo_root / "wiki",
            sources_dir=repo_root / "sources",
            schema_file=repo_root / "schema" / "wiki_schema.md",
            db_path=repo_root / "data" / "ci_wiki.db",
            databricks_host=host,
            databricks_token=token,
            anthropic_api_key=anthropic_api_key,
            model=model,
            max_tokens=int(cfg.get("max_tokens", 8192)),
            max_context_pages=int(cfg.get("max_context_pages", 5)),
            bm25_top_k=int(cfg.get("bm25_top_k", 8)),
            rate_limit_rpm=int(cfg.get("rate_limit_rpm", 50)),
            rate_limit_tpm=int(cfg.get("rate_limit_tpm", 40000)),
        )
