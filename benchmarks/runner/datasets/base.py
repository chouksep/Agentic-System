"""BfclCase dataclass + wiki EntityIndex for dataset loaders."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class BfclCase:
    """One BFCL test case in the schema the existing evaluator already accepts.

    Matches benchmarks/bfcl-faithful/test_cases.json:
      {id, category, functions, question, possible_answer}
    """
    id: str
    category: str
    functions: list[str]
    question: str
    possible_answer: list[dict]

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "category": self.category,
            "functions": self.functions,
            "question": self.question,
            "possible_answer": self.possible_answer,
        }


# Tokenization for whole-word matching: alphanumeric or hyphen runs.
_TOKEN_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9\-]*")


def _parse_frontmatter(text: str) -> dict:
    """Return the YAML frontmatter dict from a markdown file, or empty dict."""
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end == -1:
        return {}
    try:
        return yaml.safe_load(text[3:end]) or {}
    except yaml.YAMLError:
        return {}


@dataclass
class EntityIndex:
    """Maps a normalised alias string to (slug, page_type).

    Built once per run by scanning wiki/**/*.md. Aliases come from the
    canonical name (frontmatter `name` field, falling back to the slug) and
    any `aliases:` list in the frontmatter. Matching is whole-word and
    case-insensitive.
    """
    _aliases: dict[str, tuple[str, str]] = field(default_factory=dict)

    @classmethod
    def from_wiki(cls, wiki_root: Path) -> "EntityIndex":
        aliases: dict[str, tuple[str, str]] = {}
        # Sort for stable insertion order across filesystems (NTFS / ext4 /
        # APFS iterate rglob differently); makes `match()[0]` reproducible.
        for md_file in sorted(wiki_root.rglob("*.md")):
            # Page type is the parent directory name, singularised.
            parent = md_file.parent.name
            page_type = {
                "companies": "company",
                "products": "product",
                "people": "person",
                "trends": "trend",
            }.get(parent)
            if page_type is None:
                # Skip index.md, log.md, queries/ etc.
                continue
            slug = md_file.stem
            fm = _parse_frontmatter(md_file.read_text(encoding="utf-8"))
            names: list[str] = []
            canonical = fm.get("name")
            if isinstance(canonical, str):
                names.append(canonical)
            names.append(slug)
            # Slugs in this wiki are lowercase-hyphenated canonical names
            # (e.g. dario-amodei, google-deepmind). De-hyphenate so multi-word
            # queries match even when frontmatter is unreadable.
            if "-" in slug:
                names.append(slug.replace("-", " "))
            extra = fm.get("aliases") or []
            if isinstance(extra, list):
                names.extend(str(n) for n in extra)
            for name in names:
                key = name.strip().lower()
                if key:
                    aliases.setdefault(key, (slug, page_type))
        return cls(_aliases=aliases)

    def match(self, text: str) -> list[tuple[str, str]]:
        """Return all unique (slug, page_type) entities mentioned in `text`."""
        if not text:
            return []
        lower = text.lower()
        seen: set[tuple[str, str]] = set()
        ordered: list[tuple[str, str]] = []

        # First pass: multi-word aliases via substring (whole-word boundary).
        for alias, target in self._aliases.items():
            if " " in alias or "-" in alias:
                # Boundary-aware match on multi-word/hyphenated aliases.
                if re.search(rf"(?<![A-Za-z0-9])"
                             rf"{re.escape(alias)}"
                             rf"(?![A-Za-z0-9])", lower):
                    if target not in seen:
                        seen.add(target)
                        ordered.append(target)

        # Second pass: single-word aliases via tokenized lookup.
        for token in _TOKEN_RE.findall(lower):
            target = self._aliases.get(token)
            if target and target not in seen:
                seen.add(target)
                ordered.append(target)
        return ordered
