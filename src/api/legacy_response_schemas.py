"""Legacy valuation response schema."""

from datetime import date
from decimal import Decimal
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from src.api.legacy_input_schemas import YearDataInput
from src.api.report_data_schemas import ValuationReportData
from src.domain.models import ConfidenceLevel
from src.domain.owner_models.owner_dependency import OwnerDependencyResult
from src.domain.sellability_models import SellabilityAssessmentRender
from src.domain.transparency import TransparencyData

JsonObject = Dict[str, object]

from src.api.valuation_response_components import (
    DCFValuationResponse,
    FinancialMetricsResponse,
    MCPInsightsResponse,
    MethodologySelection,
    MonteCarloResults,
    MultiplePipeline,
    MultiplePipelineStage,
    MultiplesValuationResponse,
    OwnerCompensationSwap,
    SmallFirmAdjustments,
    ValuationDataQuality,
)


class ValuationResponse(BaseModel):
    """Complete valuation response."""

    # Valuation summary
    valuation_id: str = Field(..., description="Unique identifier for this valuation")
    company_name: str
    valuation_date: date
    currency: Optional[str] = Field(None, pattern=r"^[A-Z]{3}$")

    # Valuation range
    equity_value_low: Decimal = Field(..., gt=0, description="Low end of valuation range")
    equity_value_mid: Decimal = Field(..., gt=0, description="Mid-point valuation")
    equity_value_high: Decimal = Field(..., gt=0, description="High end of valuation range")
    range_methodology: Optional[str] = Field(
        None,
        description="Methodology used for range calculation: 'multiple_dispersion' (P25/P50/P75 from comparables) or 'confidence_spread' (confidence-based spread)",
    )

    # Recommendation
    recommended_asking_price: Decimal = Field(..., gt=0, description="Recommended asking price")
    recommended_asking_multiple: Optional[Decimal] = Field(
        None, gt=0, description="Strategic asking multiple (premium applied to multiple)"
    )

    # Methodology weights
    dcf_weight: Decimal = Field(..., ge=Decimal("0.0"), le=Decimal("1.0"))
    multiples_weight: Decimal = Field(..., ge=Decimal("0.0"), le=Decimal("1.0"))

    # Detailed results
    financial_metrics: FinancialMetricsResponse
    dcf_valuation: Optional[DCFValuationResponse] = None
    multiples_valuation: Optional[MultiplesValuationResponse] = None

    # Overall assessment
    overall_confidence: ConfidenceLevel
    confidence_score: int = Field(..., ge=0, le=100)

    # Insights
    valuation_summary: str
    key_value_drivers: List[str] = Field(..., max_length=10)
    risk_factors: List[str] = Field(..., max_length=10)
    methodology_notes: str

    # MCP Intelligence (Ilara Pattern: ML-Powered Valuation Intelligence)
    mcp_insights: Optional[MCPInsightsResponse] = Field(
        None, description="ML-powered valuation intelligence from historical patterns"
    )

    # Advanced Integration: Owner Profiling (12-factor dependency assessment)
    owner_profiling: Optional[JsonObject] = Field(
        None, description="DEPRECATED: Use owner_dependency_result instead"
    )

    # Owner Dependency Analysis (Phase 4: 12-factor assessment)
    owner_dependency_result: Optional[OwnerDependencyResult] = Field(
        None, description="Complete owner dependency assessment with valuation adjustment"
    )
    owner_dependency_adjustment: Decimal = Field(
        default=Decimal("0.0"),
        description="Valuation adjustment from owner dependency (-40% to 0%)",
    )

    # M&A-grade Owner Risk Ledger — single auditable reconciliation of
    # the structural (multiple-side) + behavioural (equity-side)
    # owner-risk discounts. Built post-synthesis; pure presentation
    # metadata that makes the dossier defensible for Big-4 / IVS-grade
    # diligence. Absence (None) drives the "no ledger" branch in
    # renderers — happens for DCF-only / NAV / fiscal paths or
    # back-compat fixtures. See `src/domain/owner_risk_ledger.py`.
    owner_risk_ledger: Optional[JsonObject] = Field(
        None,
        description=(
            "Reconciliation ledger of every owner-related discount with "
            "full source attribution. Serialised dict shape; renderers "
            "consume verbatim and MUST NOT re-derive any field."
        ),
    )

    # SELLABILITY-MVP (BET-204) — render-time payload for the Sellability
    # section in the main valuation report. Attached by Titan when the
    # owner has a recent persisted sellability_assessment row. Absence
    # (None) drives the "skipped" empty-state in the rendered section.
    sellability_assessment: Optional[SellabilityAssessmentRender] = Field(
        None,
        description=(
            "Render-time Sellability score payload — composed into the main "
            "report as a section, not a separate PDF. See "
            "src/templates/main_report/pages/sellability.html."
        ),
    )

    # Advanced Integration: Business Type Intelligence
    business_type_intelligence: Optional[JsonObject] = Field(
        None, description="Business type analysis and methodology optimization"
    )

    # Phase 2A: Probabilistic Valuation (Monte Carlo)
    monte_carlo_results: Optional[MonteCarloResults] = Field(
        None, description="Probabilistic valuation results from Monte Carlo simulation"
    )

    # Optional: Detailed results from triage system (for transparency)
    detailed_results: Optional[JsonObject] = Field(
        None, description="Detailed step results from triage system for transparency reporting"
    )

    # BANK-GRADE: Data Sources Tracking (Titan Enrichment Visibility)
    data_sources: Optional[JsonObject] = Field(
        None,
        description="Tracks the source of each major valuation parameter. "
        "Shows whether data came from a resolved benchmark contract via Titan "
        "or an explicitly disclosed fallback. Key for audit trail.",
    )

    # BANK-GRADE: Data Quality Indicators (January 2026)
    data_quality: Optional[ValuationDataQuality] = Field(
        None,
        description="Data quality indicators showing source and reliability of valuation multiples. "
        "Helps identify when a resolved benchmark contract was used vs. fallbacks.",
    )

    # ==========================================================================
    # HYBRID FLOW ARCHITECTURE: Field-Level Source Attribution
    # ==========================================================================
    # These fields enable the "Trust Layer" in the Calculator UI:
    # - Show source attribution (e.g., "Bron: KBO")
    # - Display confidence indicators (green/orange/red)
    # - Track normalization decisions for audit trail

    field_metadata: Optional[JsonObject] = Field(
        None,
        description="Field-level metadata for source attribution and confidence indicators. "
        "Keys are field names, values contain: status, source, confidence, originalValue, "
        "normalizedValue, normalizationReason, sourceReference, lastUpdated.",
    )

    gap_analysis: Optional[JsonObject] = Field(
        None,
        description="Gap analysis result showing data completeness and routing decisions. "
        "Contains: completenessScore, readyForCalculation, fieldsByStatus, actionItems, "
        "chatActionCount, manualActionCount.",
    )

    # TRANSPARENCY DATA (NEW - Radical Transparency Strategy)
    transparency: Optional[TransparencyData] = Field(
        None,
        description="Complete transparency data: data sources, calculations, benchmarks, validation.",
    )

    academic_validation_issues: Optional[List[str]] = Field(
        None,
        description="Academic guardrail failures (e.g. WACC range) surfaced in report disclaimers.",
    )

    # DEFENSIBILITY REPORT (structured 0-10 academic + ICP scores, typed warnings,
    # override prompts, submit-gate). The cover chip and BFF Submit-flow consume
    # this; backwards compatible with the existing classifier verdict — see
    # ``src.services.defensibility.report.DefensibilityReport.to_serializable``.
    defensibility_report: Optional[JsonObject] = Field(
        None,
        description=(
            "Structured defensibility output: 0-10 academic score with pillar "
            "breakdown, 0-10 ICP fit score, typed warnings with severity + "
            "remediation, override prompts, and submit-gate recommendation "
            "(allow / warn / block_soft)."
        ),
    )

    # SMALL FIRM EFFECT TRANSPARENCY (Phase: Small Firm Transparency)
    methodology_selection: Optional[MethodologySelection] = Field(
        None, description="Detailed explanation of methodology selection for transparency"
    )
    small_firm_adjustments: Optional[SmallFirmAdjustments] = Field(
        None, description="Detailed breakdown of small firm adjustments with explanations"
    )
    dcf_exclusion_reason: Optional[str] = Field(
        None, description="Reason DCF was excluded (backward compatibility field)"
    )
    methodology_downgrade_reason: Optional[str] = Field(
        None,
        description="Reason methodology was downgraded (e.g., HYBRID → MULTIPLES) with explanation",
    )
    methodology_substitution: Optional[JsonObject] = Field(
        None,
        description=(
            "Structured methodology-substitution payload when the requested "
            "methodology could not be executed (requested/executed/reason/"
            "missing_fields/remediation)."
        ),
    )

    # Multiple-First Discounting pipeline (DEPRECATED)
    multiple_pipeline: Optional[MultiplePipeline] = Field(
        None, description="DEPRECATED: Multiple discount pipeline. Kept for backward compatibility."
    )

    # Business Card Post-Deal lens (OWNER-PROFILING-2)
    # `post_deal_equity_value` is the headline figure the FE flips to when
    # the user toggles the Pre-Deal/Post-Deal switch. Computed by
    # `orchestration/builders/post_deal_swap.py` from the Step 2.5 owner-
    # compensation normalization. Top-level convenience copy of
    # `owner_compensation_swap.post_deal_equity_value` so consumers don't
    # have to walk into the nested object for the most common read.
    post_deal_equity_value: Optional[Decimal] = Field(
        None,
        gt=0,
        description=(
            "Equity value after replacing owner compensation with market-rate "
            "manager (Post-Deal lens). Mirrors `equity_value_mid` when the "
            "swap is unavailable. See `owner_compensation_swap` for details."
        ),
    )
    owner_compensation_swap: Optional[OwnerCompensationSwap] = Field(
        None,
        description=(
            "Pre-Deal / Post-Deal SDE-driven equity swap details. Populated "
            "for Multiples and Hybrid valuation paths; null for DCF-only."
        ),
    )

    # Current year financial data (for frontend display and calculations)
    current_year_data: Optional[YearDataInput] = Field(
        None,
        description="Current year financial data (revenue, EBITDA, etc.) used for valuation calculations",
    )

    official_financials: Optional[JsonObject] = Field(
        None,
        description="Official filing enrichment snapshot preserved in the response for trust/report surfaces.",
    )

    official_variance_analysis: Optional[JsonObject] = Field(
        None,
        description=(
            "Filing vs user variance: state, explanation, percent deltas, severity (none/soft/hard)."
        ),
    )

    official_verification_badge: Optional[JsonObject] = Field(
        None,
        description="Reserved verification badge output for trust layer rendering.",
    )

    # ==========================================================================
    # AGGREGATED DATA-QUALITY WARNINGS (Pass 3 — Metaalbewerking robustness)
    # ==========================================================================
    # Top-level rollup of every quality warning produced by the calculation
    # pipeline. Sourced from:
    #   - detailed_results.data_quality_warnings (Pass 8: top-level slot for
    #     orchestrator-emitted cross-cutting flags, e.g. method_substitution)
    #   - step_2.result.data_quality_warnings (already populated)
    #   - step_2_5.result.data_quality_warnings (Pass 8: owner_compensation_estimated)
    #   - step_4.metadata.quality_warning (added 2026-04-27)
    #   - step_7.result.data_quality_warnings (Pass 8: net_debt_unavailable)
    #   - request.metadata._integrity_warnings (Pass 8: pre-validation flags
    #     such as impossible_margin, drained from BusinessLogicValidator)
    #   - any future StepOutput.metadata.quality_warning entries
    # Frontends should prefer this list over rummaging through detailed_results.
    #
    # Known warning types (catalog also lives in
    # ``main_report_data_aggregator._localize_warnings``):
    #   Data-quality (opt-in Page-1 callout via ``show_quality_warnings_callout``):
    #     - thin_comparables_proxy
    #     - owner_concentration_skipped_missing_inputs
    #     - ebitda_divergence
    #     - forecast_margin_expansion
    #   Pass-8 methodological-integrity (force Page-1 callout always):
    #     - method_substitution     (NAV requested but multiples ran)
    #     - net_debt_unavailable     (Step 7 had to assume net debt = 0)
    #     - owner_compensation_estimated (Step 2.5 auto-estimated owner comp)
    #     - ebitda_benchmark_deviation   (Step 2: margin >50% off a MEASURED
    #                                     sector median; derived bands are context)
    #     - book_equity_unavailable      (fiscal page incomplete)
    data_quality_warnings: Optional[List[JsonObject]] = Field(
        None,
        description=(
            "Aggregated data quality warnings collected from all calculation steps. "
            "Each entry contains at minimum: type, severity ('low'|'medium'|'high'), "
            "message, and may include impact/recommendation/details/step_number. "
            "An empty list means the run produced no quality concerns; null means "
            "the field was not populated (legacy responses)."
        ),
    )

    # BET-293 — consolidation result and durable read-model metadata. These are
    # additive: standalone valuations leave them null, while consolidated parent
    # reports expose the deterministic roll-up for Titan persistence and report
    # surfaces.
    holdings_consolidation: Optional[JsonObject] = Field(
        None,
        description="Deterministic parent/subsidiary roll-up result used for this valuation.",
    )
    consolidation_mode: Optional[str] = Field(
        None,
        pattern="^(standalone|consolidated_pro_rata|consolidated_full)$",
        description="Persistence mode for multi-entity reports.",
    )
    subsidiary_run_ids: Optional[List[str]] = Field(
        None,
        max_length=50,
        description="Subsidiary valuation report ids included in the consolidated parent run.",
    )

    # ==========================================================================
    # REPORT DATA (NEW: Structured JSON for React template)
    # ==========================================================================
    report_data: Optional[ValuationReportData] = Field(
        None,
        description="Structured report data for React template rendering. "
        "Replaces html_report with JSON that frontend renders as React component.",
    )

    report_context: Optional[JsonObject] = Field(
        None,
        description="Canonical aggregated template context used for HTML/PDF rendering. "
        "Titan persists this so all report surfaces can reuse one valuation payload.",
    )

    ev_equity_waterfall_steps: Optional[List[JsonObject]] = Field(
        None,
        description="Enterprise value to equity bridge steps (same as report valuation_waterfall_steps). "
        "Populated when HTML report context is aggregated for API/clients (e.g. Venus Results chart).",
    )

    # HTML Report (DEPRECATED - kept for backward compatibility)
    html_report: Optional[str] = Field(
        None,
        description="DEPRECATED: Use report_data instead. Complete Accountant View HTML report.",
    )

    # PDF-optimized HTML Report (WeasyPrint-compatible, table-based layout with cover page)
    pdf_html_report: Optional[str] = Field(
        None,
        description="PDF-optimized HTML rendered from main_report_pdf/ templates. "
        "Used by Titan/ValuationIQ for WeasyPrint PDF generation. "
        "Separate from html_report which is screen-optimized (flexbox/grid).",
    )

    report_generation_error: Optional[str] = Field(
        None,
        description="Error message when HTML/PDF report generation fails. None when successful.",
    )

    # PDF Report (Complete valuation report in PDF format)
    pdf_bytes: Optional[str] = Field(
        None, description="Base64 encoded PDF bytes. Titan decodes and stores in Supabase Storage."
    )

    pdf_url: Optional[str] = Field(
        None, description="URL to downloadable PDF report (signed URL with expiration)"
    )

    pdf_expires_at: Optional[str] = Field(
        None, description="ISO 8601 timestamp when PDF URL expires (for signed URLs)"
    )

    # Omni-Calc method map: all valuation methods calculated simultaneously.
    # Keys: upswitch_adaptive, ebitda_multiple, dcf, sde_multiple, omzet_multiple, fiscal_4x
    valuation_results: Optional[JsonObject] = Field(
        None,
        description="Omni-calc method map. Each key is a valuation method with value, label, "
        "multiple_used, available flag, and method-specific details.",
    )

    # User-configured blended valuation (Waarderingssynthese)
    weighted_valuation: Optional[JsonObject] = Field(
        None,
        description="Present when user_weights were supplied. Contains blended_equity_value, "
        "contributions (per-method breakdown), and user_justification.",
    )

    fiscal_4x_anchor: Optional[Decimal] = Field(
        None,
        description="Belgian fiscal reference: 4x EBITDA component (accountant-only, never on client PDF)",
    )

    # === Legacy presentation class (BET-434/435) ===
    # Wire-identical to the v2 stateless CalculateResponse. How much real,
    # company-specific data backs this number (indicative ⇒ a discussion range, never
    # a false-precision point); the honest presentation contract keyed off it. Additive
    # + inert — consumers that ignore these see no change. Derived from input provenance
    # only; never mutates the number. `attested` is reserved for the legal layer.
    data_tier: str = Field(
        default="indicative",
        description=(
            "Compatibility presentation class from input provenance: 'indicative' (registry / "
            "fallback benchmarks — a discussion range) or 'defensible' (resolved Upswitch "
            "Index benchmark + real financials). 'attested' is reserved for the legal layer."
        ),
    )
    data_tier_rationale: Optional[str] = Field(
        default=None, description="One-line explanation of how data_tier was derived."
    )
    valuation_method_label: Optional[str] = Field(
        default=None,
        description="Honest method label for the computed number, keyed off data_tier.",
    )
    confidence_label: Optional[str] = Field(
        default=None,
        description=(
            "Qualitative, brand-oath-aligned confidence sentence (never 'absolute accuracy')."
        ),
    )
    present_point_estimate: bool = Field(
        default=True,
        description=(
            "False for indicative valuations — surfaces should headline the low–high "
            "range, not a false-precision point. Default True preserves current behavior."
        ),
    )
    valuation_disclaimer: Optional[str] = Field(
        default=None,
        description="One-line, brand-oath-aligned presentation disclaimer for this tier.",
    )
