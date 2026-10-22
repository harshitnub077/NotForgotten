"""Source extraction: PDF, plain text, Markdown and web pages → pages of text."""
from __future__ import annotations

import ipaddress
import re
import socket
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import List, Tuple
from urllib.parse import urlparse

from nlp.text import clean_text

MAX_URL_BYTES = 5_000_000
_SECTION_CHARS = 3_000


@dataclass
class Extracted:
    title: str
    pages: List[Tuple[int, str]]   # (page number, text)


def extract_pdf(path: str, fallback_title: str) -> Extracted:
    from pypdf import PdfReader

    reader = PdfReader(path)
    pages = []
    for num, page in enumerate(reader.pages):
        text = clean_text(page.extract_text() or "")
        if text:
            pages.append((num, text))
    if not pages:
        raise ValueError("No extractable text found — is this a scanned PDF?")
    title = fallback_title
    meta_title = (reader.metadata or {}).get("/Title") if reader.metadata else None
    if isinstance(meta_title, str) and 3 < len(meta_title.strip()) < 120:
        title = meta_title.strip()
    return Extracted(title, pages)


def split_sections(text: str) -> List[Tuple[int, str]]:
    """Split long text into pseudo-pages at headings or paragraph boundaries."""
    text = clean_text(text)
    blocks = re.split(r"\n(?=#{1,3} )|\n\n", text)
    pages: List[Tuple[int, str]] = []
    buf = ""
    for block in blocks:
        if buf and (len(buf) + len(block) > _SECTION_CHARS or block.startswith("#")):
            pages.append((len(pages), buf.strip()))
            buf = ""
        buf += block + "\n\n"
    if buf.strip():
        pages.append((len(pages), buf.strip()))
    return pages


def extract_text(text: str, title: str) -> Extracted:
    pages = split_sections(text)
    if not pages:
        raise ValueError("The text is empty.")
    heading = re.match(r"^#\s+(.+)$", text.strip(), re.M)
    return Extracted(heading.group(1).strip() if heading else title, pages)


class _HTMLText(HTMLParser):
    _SKIP = {"script", "style", "nav", "footer", "header", "aside", "noscript", "svg", "form"}
    _BLOCK = {"p", "div", "section", "article", "li", "br", "h1", "h2", "h3", "h4", "tr", "pre"}

    def __init__(self) -> None:
        super().__init__()
        self.parts: List[str] = []
        self.title = ""
        self._skip = 0
        self._in_title = False

    def handle_starttag(self, tag, attrs):
        if tag in self._SKIP:
            self._skip += 1
        if tag == "title":
            self._in_title = True
        if tag in ("h1", "h2", "h3"):
            self.parts.append("\n\n# ")
        elif tag in self._BLOCK:
            self.parts.append("\n\n")

    def handle_endtag(self, tag):
        if tag in self._SKIP and self._skip:
            self._skip -= 1
        if tag == "title":
            self._in_title = False

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        elif not self._skip:
            self.parts.append(data)


def _assert_public_host(url: str) -> None:
    """Refuse URLs that resolve to private/loopback addresses (SSRF guard)."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise ValueError("Only http(s) URLs are supported.")
    for info in socket.getaddrinfo(parsed.hostname, None):
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            raise ValueError("That address is not publicly reachable.")


def extract_url(url: str) -> Extracted:
    import httpx

    _assert_public_host(url)
    with httpx.Client(follow_redirects=True, timeout=20, headers={"User-Agent": "NotForgotten/2.0"}) as client:
        resp = client.get(url)
        resp.raise_for_status()
        _assert_public_host(str(resp.url))
        if len(resp.content) > MAX_URL_BYTES:
            raise ValueError("Page is too large to import.")
        ctype = resp.headers.get("content-type", "")
        if "pdf" in ctype:
            import tempfile

            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=True) as tmp:
                tmp.write(resp.content)
                tmp.flush()
                return extract_pdf(tmp.name, Path(urlparse(url).path).name or url)
        if "html" not in ctype and "text" not in ctype:
            raise ValueError(f"Unsupported content type: {ctype or 'unknown'}")
        if "html" not in ctype:
            return extract_text(resp.text, urlparse(url).netloc)

    parser = _HTMLText()
    parser.feed(resp.text)
    text = re.sub(r"[ \t]+", " ", "".join(parser.parts))
    # Drop short boilerplate lines (menus, buttons) that survive tag stripping.
    lines = [ln.strip() for ln in text.split("\n")]
    kept = [ln for ln in lines if len(ln) > 60 or ln.startswith("#") or not ln]
    body = "\n".join(kept)
    title = re.sub(r"\s+", " ", parser.title).strip() or urlparse(url).netloc
    extracted = extract_text(body, title)
    if sum(len(t) for _, t in extracted.pages) < 300:
        raise ValueError("Couldn't find enough readable text on that page.")
    return Extracted(title[:160], extracted.pages)
