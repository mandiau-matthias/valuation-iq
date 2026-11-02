"""Deterministic spacing cleanup for generated French report copy."""

from __future__ import annotations

import re
from typing import Mapping


FRENCH_PROTECTED_GLOSSARY_TERMS: tuple[str, ...] = (
    "EBITDA",
    "DCF",
    "SDE",
    "WACC",
    "Upswitch",
    "NAV",
    "ARR",
)

UNICODE_LETTER_RE = r"[^\W\d_]"
TEMPLATE_VARIABLE_PATTERN = r"\{[A-Za-z_][A-Za-z0-9_]*(?::[^{}]+)?\}"
INLINE_HTML_TAG_PATTERN = r"</?(?:em|strong|span|small|sup|sub)\b[^>]*>"
INLINE_HTML_CLOSING_TAG_PATTERN = r"</"

TEMPLATE_VARIABLE_RE = re.compile(TEMPLATE_VARIABLE_PATTERN)
INLINE_HTML_TAG_RE = re.compile(INLINE_HTML_TAG_PATTERN)
INLINE_HTML_CLOSING_TAG_RE = re.compile(INLINE_HTML_CLOSING_TAG_PATTERN)


def repair_french_report_copy_spacing(payload: Mapping[str, object]) -> dict[str, object]:
    """Return a copy with safe spaces around protected generated-copy tokens.

    This intentionally does not translate or rewrite meaning. It only repairs
    deterministic token-boundary defects created by the generated FR seed
    catalog, such as ``viaEBITDAMultiples``, ``{count}signaux`` and
    ``montre<em>comment</em>votre``.
    """

    repaired: dict[str, object] = {}
    for field_name, value in payload.items():
        if isinstance(value, str):
            repaired[field_name] = _repair_value_spacing(value)
        else:
            repaired[field_name] = value
    return repaired


def _repair_value_spacing(value: str) -> str:
    repaired = value
    for term in sorted(FRENCH_PROTECTED_GLOSSARY_TERMS, key=len, reverse=True):
        escaped = re.escape(term)
        repaired = re.sub(rf"(?<={UNICODE_LETTER_RE})({escaped})", r" \1", repaired)
        repaired = re.sub(rf"({escaped})(?={UNICODE_LETTER_RE})", r"\1 ", repaired)

    repaired = re.sub(
        rf"(?<={UNICODE_LETTER_RE})({TEMPLATE_VARIABLE_PATTERN})",
        r" \1",
        repaired,
    )
    repaired = re.sub(
        rf"({TEMPLATE_VARIABLE_PATTERN})(?={UNICODE_LETTER_RE})",
        r"\1 ",
        repaired,
    )

    repaired = re.sub(
        rf"(?<={UNICODE_LETTER_RE})({INLINE_HTML_TAG_PATTERN})",
        r" \1",
        repaired,
    )
    repaired = re.sub(
        rf"(</(?:em|strong|span|small|sup|sub)>)(?={UNICODE_LETTER_RE})",
        r"\1 ",
        repaired,
    )
    return repaired
