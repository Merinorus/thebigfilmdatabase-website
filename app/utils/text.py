"""Convert imported HTML fragments to plain text for the database and API."""

import re
from html import unescape
from html.parser import HTMLParser
from urllib.parse import urlsplit

import nh3

# Keep structural separators until text extraction; inline formatting is stripped
# without adding spaces (e.g. <b>I</b>sopan must remain Isopan).
_BLOCK_TAGS = {
    "blockquote",
    "br",
    "div",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "hr",
    "li",
    "ol",
    "p",
    "table",
    "td",
    "th",
    "tr",
    "ul",
}
_CLEANER = nh3.Cleaner(tags=_BLOCK_TAGS, attributes={}, link_rel=None)
_FORMATTING_TAGS = _BLOCK_TAGS | {
    "a",
    "abbr",
    "b",
    "cite",
    "code",
    "del",
    "em",
    "i",
    "ins",
    "pre",
    "q",
    "s",
    "small",
    "span",
    "strike",
    "strong",
    "sub",
    "sup",
    "u",
}


class _ImportGuard(HTMLParser):
    """Fail closed on HTML beyond simple formatting; nh3 still sanitizes it."""

    def handle_starttag(self, tag, attrs):
        if tag not in _FORMATTING_TAGS:
            raise ValueError(f"HTML tag <{tag}> is not allowed")
        for name, value in attrs:
            if name == "href" and tag == "a":
                url = re.sub(r"[\s\x00-\x1f\x7f]+", "", value or "")
                if urlsplit(url).scheme.lower() not in {"", "http", "https", "mailto"}:
                    raise ValueError("Unsafe link URL")
            elif name not in {"title", "class", "lang", "dir"}:
                raise ValueError(f"HTML attribute {name!r} is not allowed")

    def handle_endtag(self, tag):
        if tag not in _FORMATTING_TAGS:
            raise ValueError(f"HTML tag </{tag}> is not allowed")


def validate_imported_text(value: str) -> None:
    """Inspect raw and entity-encoded HTML before any data is discarded."""
    for _ in range(5):
        parser = _ImportGuard(convert_charrefs=True)
        parser.feed(value)
        parser.close()
        decoded = unescape(value)
        if decoded == value:
            return
        value = decoded
    raise ValueError("Excessively nested HTML entities")


class _TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_starttag(self, tag, attrs):
        self.parts.append(" ")

    def handle_endtag(self, tag):
        self.parts.append(" ")

    def handle_data(self, data):
        self.parts.append(data)


def clean_imported_text(value: str) -> str:
    """Strip HTML and normalize whitespace, returning text, not HTML-safe markup.

    Entities are decoded by the parser only after sanitization. The result must
    still be escaped by templates (never mark database fields as HTML-safe).
    """
    parser = _TextExtractor()
    parser.feed(_CLEANER.clean(value))
    parser.close()
    return " ".join("".join(parser.parts).split())
