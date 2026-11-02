"""Shared finalization for report template contexts."""

from __future__ import annotations

from collections.abc import Mapping

from src.services.reports.adaptive_report_gates import refresh_adaptive_gates_on_context
from src.services.reports.sde_blend_bridge_context import apply_sde_blend_bridge_context
from src.services.reports.attestation_context import build_attestation_context
from src.services.reports.formula_consistency_gate import apply_gate_to_context
from src.services.reports.report_pagination import (
    assign_sme_html_footer_page_numbers,
    assign_startup_html_footer_page_numbers,
    build_sme_report_page_flags,
    compute_total_pages,
)
from src.services.reports.report_readiness_context import build_report_readiness_context
from src.services.reports.transaction_readiness_context import (
    build_transaction_readiness_context,
)
from src.services.reports.weighted_synthesis_context import (
    promote_weighted_synthesis_headline_context,
)

ReportContext = dict[str, object]
ReportMetadata = Mapping[str, object]


def _adaptive_multiples_only_label(locale: str) -> str:
    lang = (locale or "nl").lower()[:2]
    if lang == "fr":
        return "Upswitch Adaptive - approche de marché"
    if lang == "en":
        return "Upswitch Adaptive - market approach"
    return "Upswitch Adaptive - marktbenadering"


def _adaptive_multiples_only_statement(locale: str) -> str:
    lang = (locale or "nl").lower()[:2]
    if lang == "fr":
        return (
            "La valeur d’entreprise est calculée selon une approche de marché fondée "
            "sur des multiples de transactions comparables. La DCF n’est pas retenue "
            "comme composante pondérée de la conclusion pour ce profil."
        )
    if lang == "en":
        return (
            "Enterprise value is calculated using a market approach based on comparable "
            "transaction multiples. DCF is not included as a weighted leg of the "
            "conclusion for this profile."
        )
    return (
        "De ondernemingswaarde is berekend op basis van de marktbenadering met "
        "vergelijkbare transactie-multiples. DCF is voor dit profiel niet opgenomen "
        "als afzonderlijk gewogen onderdeel van de conclusie."
    )


def _adaptive_multiples_only_justification(locale: str) -> str:
    lang = (locale or "nl").lower()[:2]
    if lang == "fr":
        return "DCF non retenue pour ce profil ; la conclusion utilise des multiples de marché calibrés."
    if lang == "en":
        return (
            "DCF is not included for this profile; the conclusion uses calibrated market multiples."
        )
    return (
        "DCF is voor dit profiel niet opgenomen; de conclusie gebruikt gekalibreerde "
        "marktmultiples."
    )


def _apply_adaptive_multiples_only_presentation(context: ReportContext, *, locale: str) -> None:
    if not context.get("is_adaptive_multiples_only"):
        return

    label = _adaptive_multiples_only_label(locale)
    context["valuation_methodology_display"] = label
    context["primary_method_label"] = label
    context["methodology_statement"] = _adaptive_multiples_only_statement(locale)
    context["adaptive_primary_basis"] = "market"
    context["adaptive_methodology_justification"] = _adaptive_multiples_only_justification(locale)


def finalize_report_context(
    context: ReportContext,
    *,
    locale: str,
    metadata: ReportMetadata | None = None,
    include_attestation: bool = False,
    refresh_adaptive_gates: bool = False,
    apply_formula_gate: bool = False,
) -> None:
    """Apply the common last-mile report context mutations in one place."""
    if refresh_adaptive_gates:
        refresh_adaptive_gates_on_context(context)
    _apply_adaptive_multiples_only_presentation(context, locale=locale)

    if include_attestation:
        context.update(
            build_attestation_context(
                context,
                metadata=metadata,
                locale=locale,
            )
        )

    context["is_fiscal_method_only"] = str(
        context.get("selected_method") or ""
    ).strip() == "fiscal_4x" and bool(context.get("fiscal_value_complete"))
    promote_weighted_synthesis_headline_context(context)
    apply_sde_blend_bridge_context(context, locale=locale)
    context.update(build_transaction_readiness_context(context, locale=locale, metadata=metadata))
    context["total_pages"] = compute_total_pages(build_sme_report_page_flags(context))
    assign_sme_html_footer_page_numbers(context)
    assign_startup_html_footer_page_numbers(context)

    if apply_formula_gate:
        apply_gate_to_context(context, soft=True)

    context.update(build_report_readiness_context(context))
