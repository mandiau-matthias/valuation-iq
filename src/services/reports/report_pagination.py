"""
Centralized report page numbering.

Every conditional page in the report must be registered here.
Python consumers call ``compute_total_pages`` instead of doing
scattered ``+1`` arithmetic.
"""

from dataclasses import dataclass
from typing import Callable, Iterable

from src.services.reports.method_component_registry import (
    build_method_component_coverage,
    get_method_report_profile,
)


@dataclass(frozen=True)
class ReportPageFlags:
    """Boolean flags that toggle optional report pages."""

    has_dcf: bool = False
    # DCF carries a material weight in the blend (>= 30%). When True, the full
    # DCF chapter (FCFF projection, terminal value, WACC x terminal-growth
    # sensitivity) renders even on the unified Adaptive path — an M&A reader
    # needs the workings when discounted cash flow drives ~half the valuation.
    dcf_is_material: bool = False
    is_adaptive_only_path: bool = False
    is_asset_anchored_methodology: bool = False
    is_asset_methodology: bool = False
    is_fiscal_method_only: bool = False
    show_fiscal_reference: bool = False
    show_method_override: bool = False
    has_weighted_synthesis: bool = False
    show_saas_appendix: bool = False
    show_saas_cap_table: bool = False
    include_ebitda_normalization_page: bool = True
    has_upswitch_adaptive_page: bool = False
    has_adjusted_nav_page: bool = False
    has_ebitda_multiple_page: bool = False
    has_sde_page: bool = False
    has_revenue_multiple_page: bool = False
    has_holding_sotp_page: bool = False
    show_advisor_multiple_transparency_appendix: bool = False
    show_canonical_evidence_adjustments_appendix: bool = False
    # Full-transparency addenda (additive; advisor + seller audience). Share the
    # multiple-transparency gate so they appear whenever a multiple was used.
    show_multiple_evidence_appendix: bool = False
    show_discount_methodology_appendix: bool = False
    show_stage_aware_breakdown_section: bool = False
    show_business_growth_maturity_section: bool = False
    show_owner_profiling_section: bool = False
    show_sellability_section: bool = False
    show_transaction_readiness_section: bool = False
    has_attestation_page: bool = False
    # Advisor M&A analysis sections (additive, non-weighted; advisor audience only).
    show_growth_multiple_sensitivity: bool = False
    show_dcf_crosscheck: bool = False
    show_equivalent_wacc: bool = False
    has_negative_ebitda_recovery: bool = False


BASE_PAGES = 5  # cover, executive summary, EBITDA normalization, valuation calibration, disclaimers


@dataclass(frozen=True)
class SMEReportSection:
    """One registered page in the SME report pack."""

    section_id: str
    screen_template: str
    pdf_template: str
    page_number_key: str | None = None
    section_number_key: str | None = None
    applies: Callable[[ReportPageFlags], bool] = lambda flags: True
    method_key: str | None = None

    def template_for(self, tree_root: str) -> str:
        if tree_root == "main_report_pdf":
            return self.pdf_template
        return self.screen_template

    def as_template_context(self, method_coverage: dict | None = None) -> dict:
        payload = {
            "id": self.section_id,
            "screen_template": self.screen_template,
            "pdf_template": self.pdf_template,
            "method_key": self.method_key,
        }
        profile = get_method_report_profile(self.method_key)
        if profile is not None:
            payload["method_report_profile"] = profile.as_template_context()
            if method_coverage:
                payload["method_component_coverage"] = method_coverage.get(
                    profile.method_key
                )
        return payload


def _not_fiscal(flags: ReportPageFlags) -> bool:
    return not flags.is_fiscal_method_only and not flags.has_holding_sotp_page


def _show_saas_cap_table(flags: ReportPageFlags) -> bool:
    return flags.show_saas_appendix and flags.show_saas_cap_table


def _show_ebitda_normalization(flags: ReportPageFlags) -> bool:
    return flags.include_ebitda_normalization_page and not flags.has_holding_sotp_page


def _show_adaptive(flags: ReportPageFlags) -> bool:
    return (
        flags.has_upswitch_adaptive_page
        and not flags.is_fiscal_method_only
        and not flags.has_holding_sotp_page
    )


def _show_dcf(flags: ReportPageFlags) -> bool:
    # Suppressed on the unified Adaptive path UNLESS DCF carries a material
    # weight in the blend — then the full DCF chapter (workings + WACC x
    # terminal-growth sensitivity) is surfaced for the M&A reader.
    if flags.is_fiscal_method_only or flags.has_holding_sotp_page or not flags.has_dcf:
        return False
    return (not flags.is_adaptive_only_path) or flags.dcf_is_material


def _show_adjusted_nav(flags: ReportPageFlags) -> bool:
    return (
        flags.has_adjusted_nav_page
        and not flags.is_fiscal_method_only
        and not flags.has_holding_sotp_page
    )


def _show_ebitda_multiple(flags: ReportPageFlags) -> bool:
    return (
        flags.has_ebitda_multiple_page
        and not flags.is_adaptive_only_path
        and not flags.is_fiscal_method_only
        and not flags.has_holding_sotp_page
    )


def _show_sde(flags: ReportPageFlags) -> bool:
    return (
        flags.has_sde_page
        and not flags.is_fiscal_method_only
        and not flags.has_holding_sotp_page
    )


def _show_revenue_multiple(flags: ReportPageFlags) -> bool:
    return (
        flags.has_revenue_multiple_page
        and not flags.is_fiscal_method_only
        and not flags.has_holding_sotp_page
    )


def _show_holding_sotp(flags: ReportPageFlags) -> bool:
    return flags.has_holding_sotp_page and not flags.is_fiscal_method_only


def _show_weighted_synthesis(flags: ReportPageFlags) -> bool:
    return (
        flags.has_weighted_synthesis
        and not flags.is_adaptive_only_path
        and not flags.is_fiscal_method_only
        and not flags.has_holding_sotp_page
    )


def _show_advisor_multiple_transparency(flags: ReportPageFlags) -> bool:
    return (
        flags.show_advisor_multiple_transparency_appendix
        and not flags.is_fiscal_method_only
        and not flags.has_holding_sotp_page
    )


def _show_canonical_evidence_adjustments(flags: ReportPageFlags) -> bool:
    return flags.show_canonical_evidence_adjustments_appendix


def _show_multiple_evidence_appendix(flags: ReportPageFlags) -> bool:
    return (
        flags.show_multiple_evidence_appendix
        and not flags.is_fiscal_method_only
        and not flags.has_holding_sotp_page
    )


def _show_discount_methodology_appendix(flags: ReportPageFlags) -> bool:
    return (
        flags.show_discount_methodology_appendix
        and not flags.is_fiscal_method_only
        and not flags.has_holding_sotp_page
    )


def _show_stage_aware_breakdown(flags: ReportPageFlags) -> bool:
    return flags.show_stage_aware_breakdown_section


def _show_business_growth_maturity(flags: ReportPageFlags) -> bool:
    return (
        flags.show_business_growth_maturity_section and not flags.is_fiscal_method_only
    )


def _show_owner_profiling(flags: ReportPageFlags) -> bool:
    return (
        flags.show_owner_profiling_section
        and not (flags.is_asset_anchored_methodology or flags.is_asset_methodology)
        and not flags.is_fiscal_method_only
    )


def _show_sellability(flags: ReportPageFlags) -> bool:
    return (
        flags.show_sellability_section
        and not (flags.is_asset_anchored_methodology or flags.is_asset_methodology)
        and not flags.is_fiscal_method_only
    )


def _show_transaction_readiness(flags: ReportPageFlags) -> bool:
    # Asset/NAV and yield dossiers still need a transaction-readiness memo
    # (price mechanics, evidence gaps, SPA handoff) — especially in mixed
    # OpCo/PropCo structures where the stand-alone NAV/yield is only a
    # diagnostic and the signing-grade answer is a SOTP bridge.
    return flags.show_transaction_readiness_section and not flags.is_fiscal_method_only


def _show_growth_multiple_sensitivity(flags: ReportPageFlags) -> bool:
    return flags.show_growth_multiple_sensitivity and not flags.is_fiscal_method_only


def _show_dcf_crosscheck(flags: ReportPageFlags) -> bool:
    return flags.show_dcf_crosscheck and not flags.is_fiscal_method_only


def _show_equivalent_wacc(flags: ReportPageFlags) -> bool:
    return flags.show_equivalent_wacc and not flags.is_fiscal_method_only


def _show_negative_ebitda_recovery(flags: ReportPageFlags) -> bool:
    return flags.has_negative_ebitda_recovery and not flags.is_fiscal_method_only


SME_REPORT_MANIFEST: tuple[SMEReportSection, ...] = (
    SMEReportSection(
        "cover",
        "main_report/pages/cover_page.html",
        "main_report_pdf/pages/cover_page.html",
    ),
    SMEReportSection(
        "executive_summary",
        "main_report/pages/executive_summary.html",
        "main_report_pdf/pages/executive_summary.html",
        "executive_summary_page_number",
        "executive_summary_section_number",
    ),
    SMEReportSection(
        "holding_sotp",
        "main_report/pages/holding_sotp_valuation.html",
        "main_report_pdf/pages/holding_sotp_valuation.html",
        "holding_sotp_page_number",
        "holding_sotp_section_number",
        _show_holding_sotp,
        method_key="holding_sotp",
    ),
    SMEReportSection(
        "saas_appendix",
        "main_report/pages/saas_appendix.html",
        "main_report_pdf/pages/saas_appendix.html",
        "saas_appendix_page_number",
        "saas_appendix_section_number",
        lambda flags: flags.show_saas_appendix,
        method_key="arr_multiple",
    ),
    SMEReportSection(
        "saas_cap_table",
        "main_report/pages/saas_cap_table.html",
        "main_report_pdf/pages/saas_cap_table.html",
        "saas_cap_table_page_number",
        "saas_cap_table_section_number",
        _show_saas_cap_table,
    ),
    SMEReportSection(
        "ebitda_normalization",
        "main_report/pages/ebitda_normalization.html",
        "main_report_pdf/pages/ebitda_normalization.html",
        "ebitda_normalization_page_number",
        "ebitda_normalization_section_number",
        _show_ebitda_normalization,
    ),
    SMEReportSection(
        "negative_ebitda_recovery",
        "main_report/pages/negative_ebitda_recovery.html",
        "main_report_pdf/pages/negative_ebitda_recovery.html",
        "negative_ebitda_recovery_page_number",
        "negative_ebitda_recovery_section_number",
        _show_negative_ebitda_recovery,
    ),
    SMEReportSection(
        "upswitch_adaptive",
        "main_report/pages/upswitch_adaptive_valuation.html",
        "main_report_pdf/pages/upswitch_adaptive_valuation.html",
        "upswitch_adaptive_page_number",
        "upswitch_adaptive_section_number",
        _show_adaptive,
        method_key="upswitch_adaptive",
    ),
    SMEReportSection(
        "dcf",
        "main_report/pages/dcf_valuation.html",
        "main_report_pdf/pages/dcf_valuation.html",
        "dcf_valuation_page_number",
        "dcf_valuation_section_number",
        _show_dcf,
        method_key="dcf",
    ),
    SMEReportSection(
        "adjusted_nav",
        "main_report/pages/adjusted_nav_valuation.html",
        "main_report_pdf/pages/adjusted_nav_valuation.html",
        "adjusted_nav_page_number",
        "adjusted_nav_section_number",
        _show_adjusted_nav,
        method_key="adjusted_nav",
    ),
    SMEReportSection(
        "ebitda_multiple",
        "main_report/pages/ebitda_multiple_valuation.html",
        "main_report_pdf/pages/ebitda_multiple_valuation.html",
        "ebitda_multiple_page_number",
        "ebitda_multiple_section_number",
        _show_ebitda_multiple,
        method_key="ebitda_multiple",
    ),
    SMEReportSection(
        "sde",
        "main_report/pages/sde_valuation.html",
        "main_report_pdf/pages/sde_valuation.html",
        "sde_page_number",
        "sde_section_number",
        _show_sde,
        method_key="sde_multiple",
    ),
    SMEReportSection(
        "revenue_multiple",
        "main_report/pages/revenue_multiple_valuation.html",
        "main_report_pdf/pages/revenue_multiple_valuation.html",
        "revenue_multiple_page_number",
        "revenue_multiple_section_number",
        _show_revenue_multiple,
        method_key="revenue_multiple",
    ),
    SMEReportSection(
        "valuation_calibration",
        "main_report/pages/valuation_calibration.html",
        "main_report_pdf/pages/valuation_calibration.html",
        "valuation_calibration_page_number",
        "valuation_calibration_section_number",
        _not_fiscal,
    ),
    SMEReportSection(
        "valuation_synthesis",
        "main_report/pages/valuation_synthesis.html",
        "main_report_pdf/pages/valuation_synthesis.html",
        "valuation_synthesis_page_number",
        "valuation_synthesis_section_number",
        _show_weighted_synthesis,
    ),
    SMEReportSection(
        "stage_aware_breakdown",
        "main_report/pages/stage_aware_breakdown.html",
        "main_report_pdf/pages/stage_aware_breakdown.html",
        "stage_aware_breakdown_page_number",
        "stage_aware_breakdown_section_number",
        _show_stage_aware_breakdown,
    ),
    SMEReportSection(
        "business_growth_maturity",
        "main_report/pages/business_growth_maturity.html",
        "main_report_pdf/pages/business_growth_maturity.html",
        "business_growth_maturity_page_number",
        "business_growth_maturity_section_number",
        _show_business_growth_maturity,
    ),
    SMEReportSection(
        "owner_profiling",
        "main_report/pages/owner_profiling.html",
        "main_report_pdf/pages/owner_profiling.html",
        "owner_profiling_page_number",
        "owner_profiling_section_number",
        _show_owner_profiling,
    ),
    SMEReportSection(
        "sellability",
        "main_report/pages/sellability.html",
        "main_report_pdf/pages/sellability.html",
        "sellability_page_number",
        "sellability_section_number",
        _show_sellability,
    ),
    SMEReportSection(
        "transaction_readiness",
        "main_report/pages/transaction_readiness.html",
        "main_report_pdf/pages/transaction_readiness.html",
        "transaction_readiness_page_number",
        "transaction_readiness_section_number",
        _show_transaction_readiness,
    ),
    # ── Advisor M&A analysis sections (additive, non-weighted; advisor audience) ──
    SMEReportSection(
        "advisor_growth_multiple",
        "main_report_pdf/pages/advisor_growth_multiple.html",
        "main_report_pdf/pages/advisor_growth_multiple.html",
        "advisor_growth_multiple_page_number",
        "advisor_growth_multiple_section_number",
        _show_growth_multiple_sensitivity,
    ),
    SMEReportSection(
        "advisor_dcf_crosscheck",
        "main_report_pdf/pages/advisor_dcf_crosscheck.html",
        "main_report_pdf/pages/advisor_dcf_crosscheck.html",
        "advisor_dcf_crosscheck_page_number",
        "advisor_dcf_crosscheck_section_number",
        _show_dcf_crosscheck,
    ),
    SMEReportSection(
        "advisor_equivalent_wacc",
        "main_report_pdf/pages/advisor_equivalent_wacc.html",
        "main_report_pdf/pages/advisor_equivalent_wacc.html",
        "advisor_equivalent_wacc_page_number",
        "advisor_equivalent_wacc_section_number",
        _show_equivalent_wacc,
    ),
    SMEReportSection(
        "advisor_multiple_transparency",
        "main_report/pages/advisor_multiple_transparency_appendix.html",
        "main_report_pdf/pages/advisor_multiple_transparency_appendix.html",
        "advisor_multiple_transparency_page_number",
        "advisor_multiple_transparency_section_number",
        _show_advisor_multiple_transparency,
    ),
    SMEReportSection(
        "canonical_evidence_adjustments",
        "main_report/pages/canonical_evidence_adjustments.html",
        "main_report_pdf/pages/canonical_evidence_adjustments.html",
        "canonical_evidence_adjustments_page_number",
        "canonical_evidence_adjustments_section_number",
        _show_canonical_evidence_adjustments,
    ),
    SMEReportSection(
        "canonical_actionable_adjustments",
        "main_report/pages/canonical_actionable_adjustments.html",
        "main_report_pdf/pages/canonical_actionable_adjustments.html",
        "canonical_actionable_adjustments_page_number",
        "canonical_actionable_adjustments_section_number",
        _show_canonical_evidence_adjustments,
    ),
    SMEReportSection(
        "disclaimers",
        "main_report/pages/disclaimers.html",
        "main_report_pdf/pages/disclaimers.html",
        "disclaimers_page_number",
        "disclaimers_section_number",
    ),
    SMEReportSection(
        "fiscal_reference",
        "main_report/pages/fiscal_reference.html",
        "main_report_pdf/pages/fiscal_reference.html",
        "fiscal_reference_page_number",
        "fiscal_reference_section_number",
        lambda flags: flags.show_fiscal_reference,
        method_key="fiscal_4x",
    ),
    SMEReportSection(
        "method_override",
        "main_report/pages/method_override.html",
        "main_report_pdf/pages/method_override.html",
        "method_override_page_number",
        "method_override_section_number",
        lambda flags: flags.show_method_override and not flags.has_holding_sotp_page,
    ),
    SMEReportSection(
        "attestation",
        "main_report/pages/attestation.html",
        "main_report_pdf/pages/attestation.html",
        "attestation_page_number",
        "attestation_section_number",
        lambda flags: flags.has_attestation_page,
    ),
    # ── Full-transparency addenda (closing the report) ──────────────────
    # Dedicated multiple-sourcing/evidence and discount-methodology pages.
    # Placed after the signature page as annexes so the auditable build-up
    # (where the multiple came from, why each discount applies) lives at the
    # very end without displacing the core narrative.
    SMEReportSection(
        "multiple_evidence_appendix",
        "main_report/pages/multiple_evidence_appendix.html",
        "main_report_pdf/pages/multiple_evidence_appendix.html",
        "multiple_evidence_appendix_page_number",
        "multiple_evidence_appendix_section_number",
        _show_multiple_evidence_appendix,
    ),
    SMEReportSection(
        "discount_methodology_appendix",
        "main_report/pages/discount_methodology_appendix.html",
        "main_report_pdf/pages/discount_methodology_appendix.html",
        "discount_methodology_appendix_page_number",
        "discount_methodology_appendix_section_number",
        _show_discount_methodology_appendix,
    ),
)


def iter_sme_report_sections(flags: ReportPageFlags) -> Iterable[SMEReportSection]:
    """Yield the ordered SME report sections that render for *flags*."""

    for section in SME_REPORT_MANIFEST:
        if section.applies(flags):
            yield section


def is_fiscal_method_only_context(context: dict) -> bool:
    """Return True when the SME report is the standalone fiscal-4x dossier."""

    return bool(
        str(context.get("selected_method") or "").strip() == "fiscal_4x"
        and context.get("fiscal_value_complete")
    )


def build_sme_report_page_flags(context: dict) -> ReportPageFlags:
    """Build page-count flags from the same gates used by the master templates."""

    is_fiscal_method_only = is_fiscal_method_only_context(context)
    is_adaptive_only_path = bool(context.get("is_adaptive_only_path"))
    dcf_method_available = context.get("dcf_method_available")
    has_publishable_dcf = (
        bool(context.get("has_dcf")) or bool(context.get("show_dcf_before_calibration"))
    ) and dcf_method_available is not False
    is_asset_methodology = bool(context.get("is_asset_methodology"))
    is_asset_anchored_methodology = bool(
        context.get("is_asset_anchored_methodology", is_asset_methodology)
    )
    is_specialty_report = bool(
        context.get("is_startup_valuation_report")
        or context.get("is_liquidation_report")
    )
    # DCF is "material" when it carries >= 30% of the blended valuation. Parsed
    # defensively (the weight may arrive as Decimal/float/str/None).
    try:
        _dcf_weight = float(context.get("dcf_weight") or 0)
    except (TypeError, ValueError):
        _dcf_weight = 0.0
    dcf_is_material = has_publishable_dcf and _dcf_weight >= 0.30
    return ReportPageFlags(
        has_dcf=has_publishable_dcf,
        dcf_is_material=dcf_is_material,
        is_adaptive_only_path=is_adaptive_only_path,
        is_asset_anchored_methodology=is_asset_anchored_methodology,
        is_asset_methodology=is_asset_methodology,
        is_fiscal_method_only=is_fiscal_method_only,
        show_fiscal_reference=bool(context.get("show_fiscal_reference")),
        show_method_override=bool(context.get("show_method_override")),
        has_weighted_synthesis=bool(context.get("has_weighted_synthesis")),
        show_saas_appendix=bool(context.get("show_saas_appendix")),
        show_saas_cap_table=bool(context.get("show_saas_cap_table")),
        include_ebitda_normalization_page=(
            context.get("include_ebitda_normalization_page") is not False
        ),
        has_upswitch_adaptive_page=bool(context.get("has_upswitch_adaptive_page")),
        has_adjusted_nav_page=bool(context.get("has_adjusted_nav_page")),
        has_ebitda_multiple_page=bool(context.get("has_ebitda_multiple_page")),
        has_sde_page=bool(context.get("has_sde_page")),
        has_revenue_multiple_page=bool(context.get("has_revenue_multiple_page")),
        has_holding_sotp_page=bool(context.get("has_holding_sotp_page")),
        show_advisor_multiple_transparency_appendix=bool(
            context.get("show_advisor_multiple_transparency_appendix")
        ),
        show_canonical_evidence_adjustments_appendix=bool(
            context.get("show_canonical_evidence_adjustments_appendix")
        ),
        # Transparency addenda share the multiple-transparency gate (a multiple
        # was used) unless explicitly toggled off in context.
        show_multiple_evidence_appendix=bool(
            context.get(
                "show_multiple_evidence_appendix",
                context.get("show_advisor_multiple_transparency_appendix"),
            )
        ),
        show_discount_methodology_appendix=bool(
            context.get(
                "show_discount_methodology_appendix",
                context.get("show_advisor_multiple_transparency_appendix"),
            )
        ),
        show_stage_aware_breakdown_section=bool(
            context.get("show_stage_aware_breakdown_section")
        ),
        show_business_growth_maturity_section=bool(
            context.get("show_business_growth_maturity_section")
        ),
        show_owner_profiling_section=bool(context.get("show_owner_profiling_section")),
        show_sellability_section=bool(context.get("show_sellability_section")),
        show_transaction_readiness_section=bool(
            context.get("show_transaction_readiness_section")
        ),
        has_attestation_page=bool(context.get("has_attestation_page"))
        and not is_specialty_report,
        show_growth_multiple_sensitivity=bool(
            context.get("show_growth_multiple_sensitivity")
        ),
        show_dcf_crosscheck=bool(context.get("show_dcf_crosscheck")),
        show_equivalent_wacc=bool(context.get("show_equivalent_wacc")),
        has_negative_ebitda_recovery=bool(context.get("has_negative_ebitda_recovery")),
    )


def sme_page_index_to_section_badge(page_index: int) -> str:
    """Map a 1-based PDF page index to the SME section header badge (cover = page 1).

    Executive summary is page 2 → badge ``01``. Keeps header ordinals aligned with
    ``assign_sme_html_footer_page_numbers`` regardless of optional inserts.
    """

    return f"{max(int(page_index) - 1, 1):02d}"


def compute_total_pages(flags: ReportPageFlags) -> int:
    """Return the report's total page count from a set of boolean flags.

    Page order follows ``main_report/master_report.html`` (cover fixed; inner sections
    shift indices). Each optional flag below adds one counted page to the SME dossier:

        • ``has_upswitch_adaptive_page`` — Adaptive flagship insert after EBITDA normalization
        • ``has_dcf`` — full DCF chapter when rendered
        • ``show_fiscal_reference``, ``show_method_override``
        • ``has_weighted_synthesis``
        • ``show_saas_appendix``, ``show_saas_cap_table``
    """
    return sum(1 for _ in iter_sme_report_sections(flags))


def startup_page_index_to_section_badge(page_index: int) -> str:
    """Mirror of :func:`sme_page_index_to_section_badge` for the startup
    track.  Cover is page 1, one-pager is page 2 → badge ``01``.

    Pinned in :func:`assign_startup_html_footer_page_numbers` so the
    five startup pages can stop hardcoding ``"01".."05"`` in their
    templates (audit issue B11).  Inserting a new page in the future
    only requires registering it inside the assignment function — the
    badges then renumber automatically.
    """

    return f"{max(int(page_index) - 1, 1):02d}"


def assign_startup_html_footer_page_numbers(context: dict) -> None:
    """Set footer page indices + section badges for the startup track.

    Mirrors the include order in ``main_report/master_report.html``:

        cover (page 1, fixed) →
        [startup_one_pager] (omitted from a sealed valuation memorandum) →
        startup_executive_summary →
        startup_method_breakdown →
        [startup_cap_table] (page 5, badge 04) — only when cap_table data exists →
        [startup_risks] (page 6, badge 05) — only when risks_register has rows →
        disclaimers

    No-op when ``is_startup_valuation_report`` is false.  The function
    is idempotent — calling it twice produces the same context — so
    the aggregator can invoke it from multiple entry points without
    drift.

    Templates read the resulting context keys via:
        startup_one_pager_section_number          (always "01")
        startup_executive_summary_section_number  (always "02")
        startup_method_breakdown_section_number   (always "03")
        startup_cap_table_section_number          (when cap_table renders)
        startup_risks_section_number              (when risks render)
        startup_advisor_cta_section_number        (legacy/fundraising deliverable only)
    """

    if not context.get("is_startup_valuation_report"):
        return

    sealed_memorandum = bool(context.get("is_sealed_advisor_memorandum"))

    # Cover is page 1. The investor one-pager is a fundraising deliverable,
    # not part of an advisor's sealed valuation memorandum.
    p = 1
    if not sealed_memorandum:
        p += 1
        context["startup_one_pager_page_number"] = p
        context["startup_one_pager_section_number"] = (
            startup_page_index_to_section_badge(p)
        )
    else:
        context.pop("startup_one_pager_page_number", None)
        context.pop("startup_one_pager_section_number", None)

    p += 1  # executive summary
    context["startup_executive_summary_page_number"] = p
    context["startup_executive_summary_section_number"] = (
        startup_page_index_to_section_badge(p)
    )

    p += 1  # method breakdown
    context["startup_method_breakdown_page_number"] = p
    context["startup_method_breakdown_section_number"] = (
        startup_page_index_to_section_badge(p)
    )

    # Cap-table page renders only when the founder supplied cap-table
    # context (option pool, SAFEs, last round). Master template guards
    # this with ``startup_report.cap_table``; we mirror the same gate.
    sr = context.get("startup_report") or {}
    has_cap_table = bool(sr.get("cap_table"))
    if has_cap_table:
        p += 1
        context["startup_cap_table_page_number"] = p
        context["startup_cap_table_section_number"] = (
            startup_page_index_to_section_badge(p)
        )

    # Risks page renders only when the engine produced ≥1 finding.
    risks = sr.get("risks_register") or []
    if isinstance(risks, list) and len(risks) > 0:
        p += 1
        context["startup_risks_page_number"] = p
        context["startup_risks_section_number"] = startup_page_index_to_section_badge(p)

    # The conversion CTA belongs to the founder/fundraising deck only.
    if not sealed_memorandum:
        p += 1
        context["startup_advisor_cta_page_number"] = p
        context["startup_advisor_cta_section_number"] = (
            startup_page_index_to_section_badge(p)
        )
    else:
        context.pop("startup_advisor_cta_page_number", None)
        context.pop("startup_advisor_cta_section_number", None)


def assign_sme_html_footer_page_numbers(context: dict) -> None:
    """Set footer page indices for ``main_report/master_report.html`` (SME track).

    Mirrors the include order in ``master_report.html``. PDF numbering stays on
    WeasyPrint ``counter(page)``; this fixes the inline footer in screen HTML when
    optional sections shift page boundaries (e.g. Upswitch Adaptive insert).

    No-op for startup / venture reports (different master).
    """
    if context.get("is_startup_valuation_report") or context.get(
        "is_liquidation_report"
    ):
        return

    context["is_fiscal_method_only"] = is_fiscal_method_only_context(context)

    flags = build_sme_report_page_flags(context)
    sections = list(iter_sme_report_sections(flags))
    method_coverage = build_method_component_coverage(
        context,
        (section.method_key for section in sections if section.method_key),
    )
    context["method_component_coverage"] = method_coverage
    context["total_pages"] = len(sections)
    context["sme_report_sections"] = [
        section.as_template_context(method_coverage) for section in sections
    ]

    for page_index, section in enumerate(sections, start=1):
        if section.page_number_key:
            context[section.page_number_key] = page_index
        if section.section_number_key:
            context[section.section_number_key] = sme_page_index_to_section_badge(
                page_index
            )
