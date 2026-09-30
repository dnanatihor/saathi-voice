"""Deterministic emergency detection. Rules run before any language model."""

import re

_WHITESPACE = re.compile(r"\s+")
_LATIN_TOKEN = re.compile(r"^[a-z0-9]+$")
_NEGATION_AFTER = re.compile(r"^(?:\s|[.।,])*?(?:नहीं|नही|nahin|nahi|not\b)")
_NEGATION_WINDOW = 16


def normalize(text: str) -> str:
    return _WHITESPACE.sub(" ", text.casefold().strip())


def _span(normalized: str, phrase: str) -> tuple[int, int] | None:
    folded = phrase.casefold()
    if _LATIN_TOKEN.fullmatch(folded):
        found = re.search(rf"(?<!\w){re.escape(folded)}(?!\w)", normalized)
        if found is None:
            return None
        return found.start(), found.end()
    index = normalized.find(folded)
    if index < 0:
        return None
    return index, index + len(folded)


def _negated_after(normalized: str, end: int) -> bool:
    window = normalized[end : end + _NEGATION_WINDOW]
    return _NEGATION_AFTER.search(window) is not None


class EmergencyDetector:
    """Match the phrase list. A negation just after a phrase suppresses that hit."""

    def __init__(self, phrases: list[str]) -> None:
        self._phrases = sorted((phrase.strip() for phrase in phrases), key=len, reverse=True)

    def is_emergency(self, text: str) -> bool:
        normalized = normalize(text)
        if not normalized:
            return False
        for phrase in self._phrases:
            if not phrase:
                continue
            span = _span(normalized, phrase)
            if span is None:
                continue
            if _negated_after(normalized, span[1]):
                continue
            return True
        return False
