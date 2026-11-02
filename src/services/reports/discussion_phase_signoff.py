"""Discussion-phase sign-off copy for report covers."""

from datetime import date, datetime
from typing import Mapping, Optional

JsonObject = Mapping[str, object]


_DISCUSSION_MONTHS = {
    "en": (
        "January",
        "February",
        "March",
        "April",
        "May",
        "June",
        "July",
        "August",
        "September",
        "October",
        "November",
        "December",
    ),
    "nl": (
        "januari",
        "februari",
        "maart",
        "april",
        "mei",
        "juni",
        "juli",
        "augustus",
        "september",
        "oktober",
        "november",
        "december",
    ),
    "fr": (
        "janvier",
        "février",
        "mars",
        "avril",
        "mai",
        "juin",
        "juillet",
        "août",
        "septembre",
        "octobre",
        "novembre",
        "décembre",
    ),
}

_ADVISOR_FALLBACKS = {
    "en": "advisor",
    "nl": "adviseur",
    "fr": "conseiller",
}

_SIGNOFF_TEMPLATES = {
    "en": "Discussed and signed off by {advisor} on {date_text}.",
    "fr": "Discuté et validé par {advisor} le {date_text}.",
    "nl": "Besproken en goedgekeurd door {advisor} op {date_text}.",
}


def _clean_discussion_text(value: object, max_length: int = 120) -> Optional[str]:
    if not isinstance(value, str):
        return None
    text = " ".join(value.strip().split())
    if not text:
        return None
    return text[:max_length]


def _parse_discussion_date(value: object) -> Optional[date]:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if not isinstance(value, str):
        return None
    raw = value.strip()
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).date()
    except ValueError:
        try:
            return date.fromisoformat(raw[:10])
        except ValueError:
            return None


def _format_discussion_date(value: object, locale: str) -> Optional[str]:
    parsed = _parse_discussion_date(value)
    if parsed is not None:
        months = _DISCUSSION_MONTHS.get(locale, _DISCUSSION_MONTHS["nl"])
        return f"{parsed.day} {months[parsed.month - 1]} {parsed.year}"
    return _clean_discussion_text(value, 40)


def _discussion_phase(metadata: JsonObject | None) -> Mapping[str, object] | None:
    if not metadata:
        return None
    discussion = metadata.get("discussion_phase")
    return discussion if isinstance(discussion, Mapping) else None


def _discussion_date_source(discussion: Mapping[str, object]) -> object:
    return (
        discussion.get("completed_at")
        or discussion.get("discussion_completed_at")
        or discussion.get("skipped_at")
    )


def _discussion_advisor(discussion: Mapping[str, object], locale: str) -> str:
    return _clean_discussion_text(discussion.get("advisor_name")) or _ADVISOR_FALLBACKS.get(
        locale, "adviseur"
    )


def build_discussion_signoff_line(metadata: JsonObject | None, locale: str) -> Optional[str]:
    """Return localized cover sign-off copy from ``metadata.discussion_phase``."""

    discussion = _discussion_phase(metadata)
    if discussion is None:
        return None

    date_text = _format_discussion_date(_discussion_date_source(discussion), locale)
    if not date_text:
        return None

    template = _SIGNOFF_TEMPLATES.get(locale, _SIGNOFF_TEMPLATES["nl"])
    return template.format(
        advisor=_discussion_advisor(discussion, locale),
        date_text=date_text,
    )
