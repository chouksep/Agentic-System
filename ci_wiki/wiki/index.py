from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from ci_wiki.models import LogEntry, WikiPage
from ci_wiki.wiki.page import WikiPageIO, _TYPE_DIR

_XREF_RE = re.compile(r"\[\[(\w+):([a-z0-9-]+)\]\]")


class WikiIndex:
    def __init__(self, wiki_dir: Path, page_io: WikiPageIO) -> None:
        self._wiki_dir = wiki_dir
        self._page_io = page_io
        self._index_path = wiki_dir / "index.md"
        self._log_path = wiki_dir / "log.md"

    def rebuild(self) -> None:
        """Full rebuild of wiki/index.md from all wiki pages."""
        all_pages = self._page_io.read_all()
        by_type: dict[str, list[WikiPage]] = {t: [] for t in _TYPE_DIR}
        for page in all_pages:
            if page.page_type in by_type:
                by_type[page.page_type].append(page)

        lines = [
            "# Competitive Intelligence Wiki — Index\n",
            f"_Last rebuilt: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}_\n",
            "",
        ]

        section_labels = {
            "company": "Companies",
            "product": "Products",
            "person": "People",
            "trend": "Trends",
        }

        for ptype, label in section_labels.items():
            pages = sorted(by_type.get(ptype, []), key=lambda p: p.slug)
            lines.append(f"## {label}\n")
            if not pages:
                lines.append("_No entries yet._\n")
            for page in pages:
                name = page.frontmatter.get("name", page.slug)
                subdir = _TYPE_DIR[page.page_type]
                rel_path = f"{subdir}/{page.slug}.md"
                updated = (
                    page.last_updated.strftime("%Y-%m-%d")
                    if page.last_updated
                    else "unknown"
                )
                lines.append(f"- [{name}]({rel_path}) — last updated {updated}")
            lines.append("")

        self._index_path.write_text("\n".join(lines), encoding="utf-8")

    def update(self, created: list[str], updated: list[str]) -> None:
        """Incremental update: rebuild if index exists, else create fresh."""
        self.rebuild()

    def append_log(self, entry: LogEntry) -> None:
        """Append a structured entry to wiki/log.md."""
        ts = entry.timestamp.strftime("%Y-%m-%dT%H:%M:%SZ")
        lines = [f"## {ts} — {entry.operation}\n"]
        if entry.source_uri:
            lines.append(f"- Source: {entry.source_uri}")
        if entry.pages_created:
            lines.append(f"- Pages created: {', '.join(entry.pages_created)}")
        if entry.pages_updated:
            lines.append(f"- Pages updated: {', '.join(entry.pages_updated)}")
        if entry.tokens_used:
            lines.append(f"- Tokens used: {entry.tokens_used:,}")
        if entry.notes:
            lines.append(f"- Notes: {entry.notes}")
        lines.append("")

        entry_text = "\n".join(lines) + "\n"

        # Prepend to log (reverse chronological)
        if self._log_path.exists():
            existing = self._log_path.read_text(encoding="utf-8")
            # Keep header if present
            if existing.startswith("# "):
                header_end = existing.find("\n\n") + 2
                header = existing[:header_end]
                rest = existing[header_end:]
                new_content = header + entry_text + rest
            else:
                new_content = entry_text + existing
        else:
            new_content = "# Competitive Intelligence Wiki — Change Log\n\n" + entry_text

        self._log_path.write_text(new_content, encoding="utf-8")

    def resolve_xrefs(self, body: str) -> str:
        """Convert [[type:slug]] to relative markdown links."""
        def replacer(m: re.Match) -> str:
            ptype = m.group(1)
            slug = m.group(2)
            if ptype in _TYPE_DIR:
                subdir = _TYPE_DIR[ptype]
                path = f"../{subdir}/{slug}.md"
                return f"[{slug}]({path})"
            return m.group(0)

        return _XREF_RE.sub(replacer, body)

    def find_broken_xrefs(self) -> list[tuple[str, str]]:
        """Return list of (page_slug, broken_ref) for non-existent cross-references."""
        broken = []
        all_pages = self._page_io.read_all()
        existing_paths = {
            (p.page_type, p.slug) for p in all_pages
        }
        for page in all_pages:
            for m in _XREF_RE.finditer(page.body):
                ptype = m.group(1)
                slug = m.group(2)
                if (ptype, slug) not in existing_paths:
                    broken.append((page.slug, f"[[{ptype}:{slug}]]"))
        return broken
