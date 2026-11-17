"""Plain-text helpers: HTML stripping, sentence splitting and extractive shortening."""

import html
import re

_TAG = re.compile(r"<[^>]+>")
_SPACE = re.compile(r"[ \t\r\f\v]+")
# Sentence end: . ! ? followed by space and an uppercase letter/quote/digit. Common German
# abbreviations are protected so "z. B." or "Nr. 5" do not split.
_ABBREVIATIONS = (
    "z. B.",
    "z.B.",
    "u. a.",
    "d. h.",
    "bzw.",
    "ca.",
    "Nr.",
    "Dr.",
    "Prof.",
    "St.",
    "vgl.",
    "etc.",
)
_SENTENCE_END = re.compile(r"(?<=[.!?…])\s+(?=[\"„»(A-ZÄÖÜ0-9])")


def strip_html(value: str | None) -> str:
    if not value:
        return ""
    text = _TAG.sub(" ", value)
    text = html.unescape(text)
    return _SPACE.sub(" ", text).strip()


def paragraphs(text: str) -> list[str]:
    return [p.strip() for p in re.split(r"\n\s*\n|\n", text or "") if p.strip()]


def sentences(text: str) -> list[str]:
    protected = text
    for i, abbr in enumerate(_ABBREVIATIONS):
        protected = protected.replace(abbr, f"\x00{i}\x00")
    parts = _SENTENCE_END.split(protected)
    result = []
    for part in parts:
        for i, abbr in enumerate(_ABBREVIATIONS):
            part = part.replace(f"\x00{i}\x00", abbr)
        if part.strip():
            result.append(part.strip())
    return result


def shorten(text: str, max_chars: int) -> list[str]:
    """Extractive summary: whole sentences from the start, grouped by paragraph, up to `max_chars`."""
    out: list[str] = []
    used = 0
    for para in paragraphs(text):
        kept: list[str] = []
        for sentence in sentences(para):
            if used + len(sentence) > max_chars and (out or kept):
                break
            kept.append(sentence)
            used += len(sentence) + 1
        if kept:
            out.append(" ".join(kept))
        if used >= max_chars or len(kept) < len(sentences(para)):
            break
    return out
