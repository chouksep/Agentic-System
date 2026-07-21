"""Disk-backed per-(model, case, schema) cache for AgentRecord.

Atomic writes (write-temp-then-rename) guarantee a partially-written cache
cell can never be read. Corrupt JSON cells are silently re-computed.

Key composition includes RUNNER_VERSION + a hash of the tools schema, so any
schema-affecting change forces recomputation without erasing prior cells.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Callable

from benchmarks.runner.types import AgentRecord
from benchmarks.runner.version import RUNNER_VERSION

log = logging.getLogger(__name__)


def build_key(*, model_id: str, case_id: str, tools_schema: str) -> str:
    """Return a stable sha256 hex digest used as both cache key and filename."""
    digest = hashlib.sha256()
    digest.update(RUNNER_VERSION.encode())
    digest.update(b"\x00")
    digest.update(model_id.encode())
    digest.update(b"\x00")
    digest.update(case_id.encode())
    digest.update(b"\x00")
    digest.update(tools_schema.encode())
    return digest.hexdigest()


class Cache:
    def __init__(self, root: Path) -> None:
        self._root = Path(root)
        self._root.mkdir(parents=True, exist_ok=True)

    # 16 hex chars = 64 bits of entropy — comfortably collision-free for a
    # per-project cache (birthday bound ~2^32 entries before any 50/50 risk),
    # and keeps filenames + tempfile-suffixed paths well below Windows MAX_PATH
    # even under deep OneDrive directories.
    _LEAF_HEX_LEN = 16

    def _path_for_key(self, key: str) -> Path:
        # Shard into 2-char directory to avoid one huge flat dir.
        leaf = key[: self._LEAF_HEX_LEN]
        return self._root / key[:2] / f"{leaf}.json"

    def get_or_compute(
        self,
        key: str,
        compute_fn: Callable[[], AgentRecord],
    ) -> AgentRecord:
        path = self._path_for_key(key)
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                return AgentRecord.from_dict(data)
            except (json.JSONDecodeError, OSError) as exc:
                log.warning("cache cell %s unreadable (%s) — recomputing", key, exc)
        record = compute_fn()
        self._write(path, record)
        return record

    @staticmethod
    def _write(path: Path, record: AgentRecord) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        # Atomic: write to a sibling temp file, then rename into place.
        fd, tmp_name = tempfile.mkstemp(
            prefix=path.name + ".",
            suffix=".tmp",
            dir=str(path.parent),
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(record.to_dict(), f, indent=2, sort_keys=True)
            os.replace(tmp_name, path)
        except Exception:
            # Clean up the temp file on failure.
            try:
                os.unlink(tmp_name)
            except OSError:
                pass
            raise
