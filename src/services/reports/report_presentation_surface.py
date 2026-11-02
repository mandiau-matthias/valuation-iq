"""Presentation-only copy for internal report surfaces.

The authenticated assurance contract remains untouched. Only the screen context
used inside the advisor workspace receives calmer start-proposal wording; PDF
and other final artifacts continue to render the full assurance marking.
"""

from __future__ import annotations

from collections.abc import Mapping

ADVISOR_WORKSPACE = "advisor_workspace"
FINAL_ARTIFACT = "final_artifact"


def normalize_presentation_surface(value: object) -> str:
    return ADVISOR_WORKSPACE if value == ADVISOR_WORKSPACE else FINAL_ARTIFACT


def screen_context_for_presentation_surface(
    context: Mapping[str, object],
    *,
    presentation_surface: object,
    locale: str,
) -> dict[str, object]:
    """Return a screen-only context without mutating assurance metadata."""

    surface = normalize_presentation_surface(presentation_surface)
    rendered = dict(context)
    rendered["report_presentation_surface"] = surface
    if surface != ADVISOR_WORKSPACE:
        return rendered

    status = str(rendered.get("report_certification_status") or "")
    if not status:
        # The calculate-time aggregator does not project assurance metadata,
        # while ``_assurance_banner.html`` defaults a missing status to
        # ``legacy_uncertified`` and draws the chip regardless. Mirror that
        # default here so the chip never renders as an empty box (the white
        # square on advisor covers, 2026-09-11).
        status = "legacy_uncertified"
        rendered["report_certification_status"] = status
    if status not in {"legacy_uncertified", "canonical_uncertified"}:
        return rendered

    lang = str(locale or "nl").lower()[:2]
    labels = {
        "nl": "Startvoorstel op basis van beschikbare cijfers",
        "en": "Starting proposal based on available figures",
        "fr": "Proposition initiale basée sur les chiffres disponibles",
    }
    details = {
        "nl": (
            "Controleer of pas cijfers en aannames aan; wijzigingen worden als nieuwe "
            "versie bewaard."
        ),
        "en": ("Review or adjust figures and assumptions; changes are saved as a new version."),
        "fr": (
            "Vérifiez ou adaptez les chiffres et hypothèses ; les modifications sont "
            "enregistrées dans une nouvelle version."
        ),
    }
    rendered["report_certification_label"] = labels.get(lang, labels["en"])
    rendered["report_certification_detail"] = details.get(lang, details["en"])
    return rendered
