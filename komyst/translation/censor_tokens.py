"""Keep censored words censored through translation.

A machine translator reads "B****" as a word to guess and writes the uncensored profanity in the
target language, undoing the source's own censoring. Censored tokens travel as bracketed numbers,
which translators keep verbatim, and are put back afterwards.
"""
from __future__ import annotations

import re

_CENSORED = re.compile(r"(?<![\w*])[A-Za-z]*\*[A-Za-z*]*(?![\w*])")
_PLACEHOLDER = re.compile(r"\[(\d+)\]")


def protect(text: str) -> tuple[str, list[str]]:
    """Replace each censored token with ``[n]``; return the text and the tokens in order."""
    tokens: list[str] = []

    def keep(match: re.Match) -> str:
        if match.group(0).count("*") < 1 or len(match.group(0)) < 2:
            return match.group(0)
        tokens.append(match.group(0))
        return f"[{len(tokens)}]"

    if "*" not in str(text or ""):
        return str(text or ""), tokens
    return _CENSORED.sub(keep, str(text)), tokens


def restore(text: str, tokens: list[str]) -> str:
    """Put the censored tokens back where the translation kept their placeholders."""
    if not tokens:
        return text

    def back(match: re.Match) -> str:
        index = int(match.group(1)) - 1
        return tokens[index] if 0 <= index < len(tokens) else match.group(0)

    return _PLACEHOLDER.sub(back, str(text or ""))
