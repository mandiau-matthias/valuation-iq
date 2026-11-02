"""Automatic private M&A estimates: release mathematics without asserting certification."""

from collections.abc import Mapping

from src.api.schemas.valuation_contracts import ValuationRunV2
from src.domain.financial_arithmetic import decimal_number

SCOPE = "automated_indicative"


def automatic_release_blockers(run: ValuationRunV2) -> list[str]:
    """Require a numerical, coherent saved range and deterministic report copy.

    Source maturity and advisor decisions affect the evidence label, not private
    ownership of an indicative artifact. Hash validation remains mandatory at
    the existing producer/consumer boundaries.
    """
    points: list[str] = []
    for band in (run.valuation_range, run.enterprise_value_range):
        if band is None:
            continue
        low, mid, high = (decimal_number(getattr(band, key)) for key in ("low", "mid", "high"))
        if not low <= mid <= high:
            points.append("Contradictory saved valuation range")
    for qualification in run.qualifications:
        if isinstance(qualification, Mapping) and qualification.get("severity") in {
            "critical",
            "error",
        }:
            points.append("The saved calculation has an unresolved mathematical or input error")
    content = run.content_provenance
    if "llm_generated" in {content.narrative_origin, content.evidence_origin}:
        points.append("Automatic export requires deterministic report narrative")
    return points


COPY = {
    "en": (
        "Automatic indicative valuation",
        "Standalone 100% control value unless the saved ownership basis specifies otherwise. Financial inputs, modeled adjustments and market assumptions retain their stated evidence status. The saved range is not statistically validated coverage. Private saving and sharing are permitted; this report does not certify accounting, tax or legal value.",
    ),
    "nl": (
        "Automatische indicatieve waardering",
        "Zelfstandige waarde bij 100% zeggenschap, tenzij de opgeslagen eigendomsbasis anders vermeldt. Financiële invoer, gemodelleerde correcties en marktaannames behouden hun vermelde bewijsstatus. De opgeslagen bandbreedte is geen statistisch gevalideerd interval. Privé opslaan en delen is toegestaan; dit rapport certificeert geen boekhoudkundige, fiscale of juridische waarde.",
    ),
    "fr": (
        "Valorisation indicative automatique",
        "Valeur autonome avec contrôle à 100 %, sauf indication contraire de la base de participation enregistrée. Les données financières, ajustements modélisés et hypothèses de marché conservent leur statut de preuve déclaré. La fourchette enregistrée ne constitue pas un intervalle statistiquement validé. La sauvegarde privée et le partage sont autorisés ; ce rapport ne certifie aucune valeur comptable, fiscale ou juridique.",
    ),
}


def automatic_report_context(locale: str) -> dict[str, object]:
    title, detail = COPY.get(locale[:2].lower(), COPY["en"])
    return {
        "report_certification_status": "canonical_uncertified",
        "report_certification_label": title,
        "report_certification_detail": detail,
        "honest_present_range": True,
        "has_attestation_page": False,
        "scope_prohibits_customer_persistence": False,
        "scope_prohibits_t4": True,
        "client_delivery_verdict": title,
    }
