"""Client-facing indicative copy, isolated from calculation/assurance authority.

Never changes monetary values, certification status, qualifications or release gates.
"""

from src.services.reports.report_pagination import assign_sme_html_footer_page_numbers


def prepare_indicative_presentation(context: dict, *, locale: str) -> dict:
    rendered = dict(context)
    if rendered.get("report_certification_status") == "canonical_certified":
        return rendered
    assurance = rendered.get("report_assurance") or {}
    attestation = (assurance.get("legal_attestation") or {}) if isinstance(assurance, dict) else {}
    if attestation.get("status") == "attested":
        return rendered
    if rendered.get("report_scope") in {"audit", "certified", "fiscal"}:
        return rendered

    lang = locale.lower()[:2]
    copy = {
        "en": ("Indicative valuation", "Estimate based on the supplied financials and stated assumptions. Actual transaction terms may differ."),
        "nl": ("Indicatieve waardering", "Raming op basis van de aangeleverde cijfers en vermelde aannames. De uiteindelijke transactievoorwaarden kunnen afwijken."),
        "fr": ("Valorisation indicative", "Estimation fondée sur les données financières fournies et les hypothèses indiquées. Les conditions réelles de transaction peuvent différer."),
    }
    label, detail = copy.get(lang, copy["en"])
    rendered.update(
        indicative_presentation=True,
        report_certification_label=label,
        report_certification_footer_label=label,
        report_certification_detail=detail,
    )
    # Sealed manifests remain immutable. This only selects relevant sections for
    # unsealed legacy indicative reports and regenerates their page numbering.
    if not rendered.get("is_sealed_advisor_memorandum"):
        # Pure fiscal engagements keep their method-specific legal structure.
        if rendered.get("is_fiscal_method") or rendered.get("is_fiscal_method_only"):
            return rendered
        rendered["has_attestation_page"] = False
        if rendered.get("country_code") != "BE":
            rendered["show_fiscal_reference"] = False
        assign_sme_html_footer_page_numbers(rendered)
    return rendered
