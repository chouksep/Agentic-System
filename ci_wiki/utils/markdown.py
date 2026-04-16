"""Lightweight YAML frontmatter parser/serializer for wiki pages.

Handles the simple key: value frontmatter used by this project without
requiring PyYAML as a hard dependency for this specific layer (though
PyYAML is still used for config.yaml parsing in config.py).
"""
from __future__ import annotations

import re
from datetime import datetime, date
from typing import Any


_FENCE = "---"
_FM_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)", re.DOTALL)


def parse(text: str) -> tuple[dict, str]:
    """Split markdown text into (frontmatter_dict, body).

    If no frontmatter fence is found, returns ({}, original text).
    """
    m = _FM_RE.match(text)
    if not m:
        return {}, text
    fm_text, body = m.group(1), m.group(2)
    return _parse_yaml_subset(fm_text), body


def dump(frontmatter: dict, body: str) -> str:
    """Serialize frontmatter dict + body back to a markdown string."""
    fm_str = _dump_yaml_subset(frontmatter)
    return f"---\n{fm_str}---\n{body}"


# --- minimal YAML subset ---

def _parse_yaml_subset(text: str) -> dict:
    result: dict = {}
    for line in text.splitlines():
        if not line.strip() or line.strip().startswith("#"):
            continue
        if ":" not in line:
            continue
        key, _, val = line.partition(":")
        key = key.strip()
        val = val.strip()
        result[key] = _coerce(val)
    return result


def _coerce(val: str) -> Any:
    if not val:
        return None
    # list shorthand: [a, b, c]
    if val.startswith("[") and val.endswith("]"):
        inner = val[1:-1].strip()
        if not inner:
            return []
        items = [_coerce(i.strip()) for i in inner.split(",")]
        return items
    # quoted strings
    if (val.startswith('"') and val.endswith('"')) or (
        val.startswith("'") and val.endswith("'")
    ):
        return val[1:-1]
    # booleans
    if val.lower() == "true":
        return True
    if val.lower() == "false":
        return False
    # null
    if val.lower() in ("null", "~", "none"):
        return None
    # integers
    try:
        return int(val)
    except ValueError:
        pass
    # floats
    try:
        return float(val)
    except ValueError:
        pass
    # dates (YYYY-MM-DD)
    try:
        return datetime.strptime(val, "%Y-%m-%d").date()
    except ValueError:
        pass
    return val


def _dump_yaml_subset(d: dict) -> str:
    lines = []
    for k, v in d.items():
        lines.append(f"{k}: {_serialize_val(v)}")
    return "\n".join(lines) + "\n"


def _serialize_val(v: Any) -> str:
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, list):
        if not v:
            return "[]"
        items = ", ".join(_serialize_val(i) for i in v)
        return f"[{items}]"
    if isinstance(v, (date, datetime)):
        return str(v)[:10]
    if isinstance(v, str):
        # quote if contains special chars
        if any(c in v for c in (':', '#', '[', ']', '{', '}', ',', '"', "'")):
            escaped = v.replace('"', '\\"')
            return f'"{escaped}"'
        return v
    return str(v)
