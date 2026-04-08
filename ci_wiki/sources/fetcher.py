from __future__ import annotations

import time
import urllib.request
import urllib.error
import urllib.parse
import xml.etree.ElementTree as ET
from dataclasses import dataclass


_USER_AGENT = (
    "ci-wiki/0.1 (competitive intelligence research bot; "
    "contact: admin@example.com)"
)
_TIMEOUT = 15
_MAX_RETRIES = 3


@dataclass
class RawContent:
    uri: str
    content_type: str    # "html", "text", "rss", "pdf", "unknown"
    data: bytes
    encoding: str = "utf-8"

    def text(self) -> str:
        return self.data.decode(self.encoding, errors="replace")


class Fetcher:
    def __init__(self) -> None:
        pass

    def fetch_url(self, url: str) -> RawContent:
        """Fetch a URL with retries on transient errors (429, 503)."""
        req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
        last_err: Exception | None = None

        for attempt in range(_MAX_RETRIES):
            try:
                with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
                    data = resp.read()
                    ct = resp.headers.get("Content-Type", "")
                    content_type = self._classify_content_type(ct)
                    encoding = self._parse_encoding(ct)
                    return RawContent(
                        uri=url,
                        content_type=content_type,
                        data=data,
                        encoding=encoding,
                    )
            except urllib.error.HTTPError as e:
                if e.code in (429, 503):
                    retry_after = int(e.headers.get("Retry-After", 2 ** (attempt + 1)))
                    time.sleep(retry_after)
                    last_err = e
                else:
                    raise
            except urllib.error.URLError as e:
                wait = 2 ** attempt
                time.sleep(wait)
                last_err = e

        raise RuntimeError(f"Failed to fetch {url} after {_MAX_RETRIES} attempts: {last_err}")

    def fetch_rss(self, feed_url: str) -> list[RawContent]:
        """Fetch and parse an RSS/Atom feed. Returns one RawContent per item."""
        raw = self.fetch_url(feed_url)
        try:
            root = ET.fromstring(raw.data)
        except ET.ParseError as e:
            raise ValueError(f"Invalid XML in feed {feed_url}: {e}") from e

        items = []
        # RSS 2.0
        for item in root.iter("item"):
            text = self._rss_item_to_text(item)
            link = self._find_text(item, "link") or feed_url
            items.append(RawContent(uri=link, content_type="text", data=text.encode()))

        # Atom
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        for entry in root.iter("{http://www.w3.org/2005/Atom}entry"):
            text = self._atom_entry_to_text(entry)
            link_el = entry.find("{http://www.w3.org/2005/Atom}link")
            link = link_el.get("href", feed_url) if link_el is not None else feed_url
            items.append(RawContent(uri=link, content_type="text", data=text.encode()))

        return items

    def fetch_github_readme(self, repo_url: str) -> RawContent:
        """Fetch raw README from a GitHub repo URL."""
        # Convert https://github.com/owner/repo to raw README URL
        parts = repo_url.rstrip("/").split("/")
        if len(parts) < 5 or "github.com" not in parts[2]:
            raise ValueError(f"Not a valid GitHub repo URL: {repo_url}")
        owner, repo = parts[3], parts[4]
        raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/main/README.md"
        try:
            return self.fetch_url(raw_url)
        except Exception:
            # try master branch
            raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/master/README.md"
            return self.fetch_url(raw_url)

    @staticmethod
    def _classify_content_type(ct: str) -> str:
        ct = ct.lower()
        if "html" in ct:
            return "html"
        if "xml" in ct or "rss" in ct or "atom" in ct:
            return "rss"
        if "pdf" in ct:
            return "pdf"
        if "text" in ct:
            return "text"
        return "unknown"

    @staticmethod
    def _parse_encoding(ct: str) -> str:
        for part in ct.split(";"):
            part = part.strip()
            if part.lower().startswith("charset="):
                return part[8:].strip().lower()
        return "utf-8"

    @staticmethod
    def _find_text(el: ET.Element, tag: str) -> str | None:
        child = el.find(tag)
        return child.text if child is not None else None

    def _rss_item_to_text(self, item: ET.Element) -> str:
        title = self._find_text(item, "title") or ""
        desc = self._find_text(item, "description") or ""
        pub_date = self._find_text(item, "pubDate") or ""
        link = self._find_text(item, "link") or ""
        parts = []
        if title:
            parts.append(f"Title: {title}")
        if pub_date:
            parts.append(f"Date: {pub_date}")
        if link:
            parts.append(f"URL: {link}")
        if desc:
            parts.append(f"\n{desc}")
        return "\n".join(parts)

    def _atom_entry_to_text(self, entry: ET.Element) -> str:
        def ftag(name):
            return f"{{http://www.w3.org/2005/Atom}}{name}"

        title_el = entry.find(ftag("title"))
        title = title_el.text if title_el is not None else ""
        summary_el = entry.find(ftag("summary"))
        content_el = entry.find(ftag("content"))
        body = (content_el or summary_el)
        body_text = body.text if body is not None else ""
        updated_el = entry.find(ftag("updated"))
        updated = updated_el.text if updated_el is not None else ""
        parts = []
        if title:
            parts.append(f"Title: {title}")
        if updated:
            parts.append(f"Date: {updated}")
        if body_text:
            parts.append(f"\n{body_text}")
        return "\n".join(parts)
