from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class Config:
    repo_root: Path
    wiki_dir: Path
    sources_dir: Path
    schema_file: Path
    db_path: Path
    anthropic_api_key: str
    model: str = "claude-sonnet-4-6"
    max_tokens: int = 8192
    max_context_pages: int = 5
    bm25_top_k: int = 8
    rate_limit_rpm: int = 50
    rate_limit_tpm: int = 40000

    @classmethod
    def from_env(cls, repo_root: Path | None = None) -> "Config":
        if repo_root is None:
            repo_root = Path(__file__).parent.parent.resolve()

        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY environment variable is not set. "
                "Export it before running: export ANTHROPIC_API_KEY=sk-..."
            )

        cfg: dict = {}
        config_yaml = repo_root / "config.yaml"
        if config_yaml.exists():
            with config_yaml.open() as f:
                cfg = yaml.safe_load(f) or {}

        return cls(
            repo_root=repo_root,
            wiki_dir=repo_root / "wiki",
            sources_dir=repo_root / "sources",
            schema_file=repo_root / "schema" / "wiki_schema.md",
            db_path=repo_root / "data" / "ci_wiki.db",
            anthropic_api_key=api_key,
            model=cfg.get("model", "claude-sonnet-4-6"),
            max_tokens=int(cfg.get("max_tokens", 8192)),
            max_context_pages=int(cfg.get("max_context_pages", 5)),
            bm25_top_k=int(cfg.get("bm25_top_k", 8)),
            rate_limit_rpm=int(cfg.get("rate_limit_rpm", 50)),
            rate_limit_tpm=int(cfg.get("rate_limit_tpm", 40000)),
        )
