"""Preparer multiple-adjustment footnote helpers for report contexts."""

from collections.abc import Mapping
from dataclasses import dataclass

from src.services.infrastructure.translations import get_translations, normalize_report_locale


@dataclass(frozen=True)
class _PreparerOverrideSnapshot:
    baseline: float
    applied: float
    reason_key: str
    note: str | None

    @property
    def delta(self) -> float:
        return self.applied - self.baseline


def build_preparer_ebitda_override_footnote(
    metadata: Mapping[str, object] | None,
    locale: str,
    country_code: str = "BE",
) -> str | None:
    """Render the PDF/HTML footnote for preparer EV/EBITDA multiple adjustments."""
    snapshot = _preparer_override_snapshot(metadata)
    if snapshot is None or abs(snapshot.delta) < 0.005:
        return None

    loc = normalize_report_locale(locale)
    t = get_translations(loc, country_code=country_code)
    rendered = _render_preparer_override_template(
        snapshot=snapshot,
        translations=t,
    )
    return _append_preparer_override_note(rendered, note=snapshot.note, locale=loc)


def _preparer_override_snapshot(
    metadata: Mapping[str, object] | None,
) -> _PreparerOverrideSnapshot | None:
    if not metadata:
        return None
    snap = metadata.get("preparer_ebitda_adjustment") or metadata.get("preparer_ebitda_override")
    if not isinstance(snap, Mapping):
        return None

    baseline = _positive_float(snap.get("baseline_median"))
    applied = _positive_float(snap.get("applied_median"))
    reason_key = snap.get("reason_key")
    if baseline is None or applied is None or not reason_key:
        return None
    note = snap.get("note")
    return _PreparerOverrideSnapshot(
        baseline=baseline,
        applied=applied,
        reason_key=str(reason_key),
        note=note.strip() if isinstance(note, str) and note.strip() else None,
    )


def _positive_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _preparer_reason_label(translations: object, reason_key: str) -> str:
    reason_map = {
        "strategic_buyer_premium": str(translations.preparer_reason_strategic_buyer_premium),
        "exceptional_management_premium": str(
            translations.preparer_reason_exceptional_management_premium
        ),
        "key_person_discount": str(translations.preparer_reason_key_person_discount),
        "real_estate_included": str(translations.preparer_reason_real_estate_included),
        "customer_concentration": str(translations.preparer_reason_customer_concentration),
        "distressed_sale": str(translations.preparer_reason_distressed_sale),
        "recurring_revenue_premium": str(translations.preparer_reason_recurring_revenue_premium),
        "other": str(translations.preparer_reason_other),
    }
    return reason_map.get(reason_key, reason_key)


def _render_preparer_override_template(
    *,
    snapshot: _PreparerOverrideSnapshot,
    translations: object,
) -> str:
    adjustment_label = (
        str(translations.preparer_adjustment_premium)
        if snapshot.delta > 0
        else str(translations.preparer_adjustment_discount)
    )
    return str(translations.disc_preparer_override_template).format(
        baseline=f"{snapshot.baseline:.2f}",
        applied=f"{snapshot.applied:.2f}",
        delta_abs=f"{abs(snapshot.delta):.2f}",
        adjustment_label=adjustment_label,
        reason=_preparer_reason_label(translations, snapshot.reason_key),
    )


def _append_preparer_override_note(rendered: str, *, note: str | None, locale: str) -> str:
    if not note:
        return rendered
    if locale == "en":
        return f"{rendered} Additional note: {note}"
    return f"{rendered} Aanvullende notitie: {note}"
