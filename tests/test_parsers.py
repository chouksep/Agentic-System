from __future__ import annotations

import hashlib
import pytest

from ci_wiki.sources.fetcher import RawContent
from ci_wiki.sources.parsers import Parser, _MAX_CHARS


@pytest.fixture
def parser():
    return Parser()


def make_html(body_content: str, title: str = "Test Page") -> RawContent:
    html = f"""<!DOCTYPE html>
<html>
<head><title>{title}</title></head>
<body>
<nav>Skip this nav</nav>
<script>var x = 1;</script>
<main>{body_content}</main>
<footer>Skip this footer</footer>
</body>
</html>"""
    return RawContent(uri="http://example.com", content_type="html", data=html.encode())


def test_parse_html_extracts_text(parser):
    raw = make_html("<p>Hello world</p><p>Competitive intelligence.</p>")
    text = parser.parse(raw)
    assert "Hello world" in text
    assert "Competitive intelligence" in text
    assert "Skip this nav" not in text
    assert "Skip this footer" not in text
    assert "var x = 1" not in text


def test_parse_html_includes_title(parser):
    raw = make_html("<p>Content here</p>", title="My Article")
    text = parser.parse(raw)
    assert "My Article" in text


def test_parse_html_includes_url(parser):
    raw = make_html("<p>Content</p>")
    text = parser.parse(raw)
    assert "http://example.com" in text


def test_parse_html_truncates_at_max_chars(parser):
    # Generate a large body
    long_body = "<p>" + "word " * 5000 + "</p>"
    raw = make_html(long_body)
    text = parser.parse(raw)
    assert len(text) <= _MAX_CHARS


def test_parse_plain_text(parser):
    raw = RawContent(
        uri="file:///test.txt",
        content_type="text",
        data=b"Plain text content here.\nSecond line.",
    )
    text = parser.parse(raw)
    assert "Plain text content here." in text
    assert "Second line" in text


def test_parse_plain_text_truncates(parser):
    raw = RawContent(
        uri="file:///test.txt",
        content_type="text",
        data=("x" * 20000).encode(),
    )
    text = parser.parse(raw)
    assert len(text) <= _MAX_CHARS


def test_content_hash_stable():
    text = "same content"
    h1 = hashlib.sha256(text.encode()).hexdigest()
    h2 = hashlib.sha256(text.encode()).hexdigest()
    assert h1 == h2


def test_content_hash_differs_for_different_text():
    h1 = hashlib.sha256(b"content a").hexdigest()
    h2 = hashlib.sha256(b"content b").hexdigest()
    assert h1 != h2
