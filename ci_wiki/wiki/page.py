from __future__ import annotations

import os
from datetime import datetime, UTC
from pathlib import Path

from ci_wiki import utils
from ci_wiki.utils import markdown
from ci_wiki.models import WikiPage

PAGE_TYPES = ("company", "product", "person", "trend")
_TYPE_DIR = {
    "company": "companies",
    "product": "products",
    "person": "people",
    "trend": "trends",
}


class WikiPageIO:
    def __init__(self, wiki_dir: Path) -> None:
        self.wiki_dir = wiki_dir

    def slug_to_path(self, slug: str, page_type: str) -> Path:
        subdir = _TYPE_DIR.get(page_type, page_type + "s")
        return self.wiki_dir / subdir / f"{slug}.md"

    def path_to_slug(self, path: Path) -> str:
        return path.stem

    def path_to_type(self, path: Path) -> str:
        dir_to_type = {v: k for k, v in _TYPE_DIR.items()}
        return dir_to_type.get(path.parent.name, path.parent.name)

    def exists(self, slug: str, page_type: str) -> bool:
        return self.slug_to_path(slug, page_type).exists()

    def read(self, path: Path) -> WikiPage:
        if not path.exists():
            raise FileNotFoundError(f"Wiki page not found: {path}")
        text = path.read_text(encoding="utf-8")
        fm, body = markdown.parse(text)
        slug = self.path_to_slug(path)
        page_type = self.path_to_type(path)

        last_updated_raw = fm.get("last_updated")
        if isinstance(last_updated_raw, str):
            try:
                last_updated = datetime.strptime(last_updated_raw, "%Y-%m-%d")
            except ValueError:
                last_updated = None
        elif hasattr(last_updated_raw, "year"):
            last_updated = datetime(
                last_updated_raw.year,
                last_updated_raw.month,
                last_updated_raw.day,
            )
        else:
            last_updated = None

        return WikiPage(
            path=path,
            slug=slug,
            page_type=page_type,
            frontmatter=fm,
            body=body,
            last_updated=last_updated,
        )

    def read_by_slug(self, slug: str, page_type: str) -> WikiPage:
        path = self.slug_to_path(slug, page_type)
        return self.read(path)

    def write(self, page: WikiPage) -> None:
        """Atomic write: write to .tmp then os.replace."""
        page.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = page.path.with_suffix(".md.tmp")
        content = markdown.dump(page.frontmatter, page.body)
        tmp.write_text(content, encoding="utf-8")
        os.replace(tmp, page.path)

    def write_content(self, slug: str, page_type: str, content: str) -> WikiPage:
        """Parse content string and write to disk. Returns the parsed WikiPage."""
        path = self.slug_to_path(slug, page_type)
        fm, body = markdown.parse(content)
        now = datetime.now(UTC).replace(tzinfo=None)
        if "last_updated" not in fm:
            fm["last_updated"] = now.strftime("%Y-%m-%d")
        page = WikiPage(
            path=path,
            slug=slug,
            page_type=page_type,
            frontmatter=fm,
            body=body,
            last_updated=now,
        )
        self.write(page)
        return page

    def read_all(self, page_type: str | None = None) -> list[WikiPage]:
        pages = []
        if page_type:
            dirs = [self.wiki_dir / _TYPE_DIR.get(page_type, page_type + "s")]
        else:
            dirs = [self.wiki_dir / d for d in _TYPE_DIR.values()]

        for d in dirs:
            if not d.exists():
                continue
            for md_file in sorted(d.glob("*.md")):
                try:
                    pages.append(self.read(md_file))
                except Exception:
                    pass
        return pages

    def list_slugs(self, page_type: str | None = None) -> list[str]:
        return [p.slug for p in self.read_all(page_type)]
