from __future__ import annotations

import html as html_module
import re
from html.parser import HTMLParser

from ci_wiki.sources.fetcher import RawContent

_MAX_CHARS = 12_000
_SKIP_TAGS = frozenset(
    ["script", "style", "nav", "footer", "aside", "header", "noscript", "iframe"]
)


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._skip_depth = 0
        self._parts: list[str] = []
        self.title: str = ""
        self._in_title = False

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag in _SKIP_TAGS:
            self._skip_depth += 1
        if tag == "title":
            self._in_title = True

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in _SKIP_TAGS and self._skip_depth > 0:
            self._skip_depth -= 1
        if tag == "title":
            self._in_title = False
        if tag in ("p", "div", "section", "article", "h1", "h2", "h3", "h4", "li", "br", "tr"):
            self._parts.append("\n")

    def handle_data(self, data):
        if self._skip_depth > 0:
            return
        text = data.strip()
        if not text:
            return
        if self._in_title:
            self.title = text
        self._parts.append(text + " ")

    def get_text(self) -> str:
        raw = "".join(self._parts)
        # collapse whitespace
        raw = re.sub(r" {2,}", " ", raw)
        raw = re.sub(r"\n{3,}", "\n\n", raw)
        return raw.strip()


class Parser:
    def parse(self, raw: RawContent) -> str:
        """Convert raw content to plain text, truncated at _MAX_CHARS."""
        if raw.content_type == "html":
            text = self._parse_html(raw.text(), raw.uri)
        elif raw.content_type == "pdf":
            text = self._parse_pdf(raw.data)
        else:
            text = self._parse_plain_text(raw.text())

        return text[:_MAX_CHARS]

    def _parse_html(self, html: str, url: str) -> str:
        extractor = _TextExtractor()
        try:
            extractor.feed(html)
        except Exception:
            pass  # best-effort

        text = extractor.get_text()
        title = extractor.title

        # Prepend URL and title for context
        header_parts = [f"URL: {url}"]
        if title:
            header_parts.append(f"Title: {title}")
        header = "\n".join(header_parts)
        return f"{header}\n\n{text}"

    def _parse_plain_text(self, text: str) -> str:
        # Unescape HTML entities just in case
        text = html_module.unescape(text)
        return text.strip()

    def _parse_pdf(self, data: bytes) -> str:
        """Minimal PDF text extraction using regex on raw bytes."""
        _MAX_PDF_BYTES = 50 * 1024 * 1024  # 50 MB
        if len(data) > _MAX_PDF_BYTES:
            raise ValueError(
                f"PDF too large ({len(data) // 1024 // 1024} MB); limit is 50 MB."
            )
        try:
            text_data = data.decode("latin-1", errors="replace")
            # Extract text between BT...ET markers (basic PDF text streams)
            bt_et = re.findall(r"BT\s+(.*?)\s+ET", text_data, re.DOTALL)
            parts = []
            for block in bt_et:
                # Extract string literals from Tj / TJ operators
                strings = re.findall(r"\((.*?)\)\s*Tj", block)
                strings += re.findall(r"\[(.*?)\]\s*TJ", block)
                for s in strings:
                    # Basic escape handling
                    s = s.replace("\\n", "\n").replace("\\r", "").replace("\\t", " ")
                    parts.append(s)
            return " ".join(parts).strip() or "[PDF content could not be extracted]"
        except Exception:
            return "[PDF content could not be extracted]"
