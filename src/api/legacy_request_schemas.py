"""Legacy valuation request schema."""

from decimal import Decimal
from typing import Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Field, field_validator, model_validator

from src.utils.percentage_input_contract import validate_context_percentage_units

from .dcf_readiness import explicitly_requests_dcf, require_dcf_readiness, resolve_dcf_readiness

from src.api.business_type_mix import normalize_business_type_mix_fields
from src.api.legacy_input_schemas import (
    BalanceSheetAdjustmentInput,
    HoldingConsolidationInput,
    OwnershipSummary,
    ShareholderRosterEntry,
    TaxLatencyInput,
    YearDataInput,
)
from src.api.legacy_schema_validation import (
    normalize_business_model_field,
    normalize_enrichment_multiple_distributions_request,
    normalize_historical_ebitda_weighting_mode_field,
    normalize_historical_ebitda_weights_field,
    normalize_key_metrics_field,
    normalize_real_estate_treatment_field,
    validate_advisor_controls_request,
    validate_historical_years_order,
    validate_year_buckets_request,
)
from src.domain.models import BusinessModel, ComparableCompany
from src.domain.owner_models.owner_dependency import OwnerDependencyFactors
from src.domain.startup_valuation.schemas import StartupInputs
from src.config.countries import normalize_country_code

JsonObject = Dict[str, object]


def _get_max_confirmable_year_from_facade() -> int:
    from src.api import legacy_schemas

    return legacy_schemas.get_max_confirmable_year()


def _validate_industry_from_facade(value: str) -> str:
    from src.api import legacy_schemas

    return legacy_schemas.validate_industry_field(value)


class ValuationRequest(BaseModel):
    """Request to calculate business valuation."""

    valuation_id: Optional[str] = Field(
        None,
        pattern=r"^val_\d+_[A-Za-z0-9_-]+(_[A-Za-z0-9_-]+)?$",
        description="Client-provided report ID for idempotency (supports hex and base64url session keys)",
    )
    presentation_surface: Literal["advisor_workspace", "final_artifact"] = Field(
        "final_artifact",
        description=(
            "Presentation-only surface. It never changes assurance metadata or calculation mode."
        ),
    )

    company_name: str = Field(..., min_length=1, max_length=200, description="Company name")
    registry_country: Optional[str] = Field(None, pattern=r"^[A-Z]{2}$")
    registration_number: Optional[str] = Field(
        None, max_length=50, description="Generic company registration number (KBO/KVK)"
    )
    kbo_number: Optional[str] = Field(None, max_length=50, description="Belgian KBO/BCE number")
    kvk_number: Optional[str] = Field(None, max_length=50, description="Dutch KVK number")
    vat_number: Optional[str] = Field(None, max_length=50, description="VAT number")
    legal_form: Optional[str] = Field(None, max_length=100, description="Legal form")
    country_code: str = Field(
        ..., pattern="^[A-Z]{2}$", description="2-letter ISO country code (e.g., DE, FR, US)"
    )
    currency: Optional[str] = Field(
        None,
        pattern=r"^[A-Z]{3}$",
        description=(
            "ISO-4217 currency of unconverted monetary inputs. Missing currency remains "
            "unresolved and must not be silently relabelled."
        ),
    )
    industry: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Industry classification (flexible string to support current business type catalog)",
    )
    business_model: Union[str, BusinessModel] = Field(
        ..., description="Business model type (accepts string or enum)"
    )
    founding_year: int = Field(..., ge=1900, le=2100, description="Year company was founded")

    use_monte_carlo: Optional[bool] = Field(False, description="Enable Monte Carlo simulation")
    use_intelligent_selection: Optional[bool] = Field(
        False, description="Enable Q-learning methodology selection"
    )
    use_asymmetric_ranges: Optional[bool] = Field(
        False, description="Enable asymmetric range calculation"
    )

    methodology: Optional[str] = Field("HYBRID", description="Valuation methodology to use")

    # Pass-5: advisor-configured asking-price buffer override (Mercury → Titan
    # → ValuationIQ). Fraction in [0, 0.25] — e.g. 0.10 for 10%. When unset
    # the engine falls back to the confidence-aware default (5–10%).
    asking_price_buffer_pct: Optional[Decimal] = Field(
        None,
        ge=Decimal("0.0"),
        le=Decimal("0.25"),
        description=(
            "Firm-level asking-price buffer override as a fraction. Replaces "
            "the engine's confidence-aware default markup. Bounded to [0, 0.25]."
        ),
    )

    current_year_data: YearDataInput = Field(..., description="Current year financial data")
    historical_years_data: List[YearDataInput] = Field(
        default=[], max_length=10, description="Historical financial data (up to 10 years)"
    )
    forecast_years_data: List[YearDataInput] = Field(
        default=[],
        max_length=15,
        description="Optional forecast financial data for forward-looking DCF scenarios",
    )

    dcf_input_mode: Optional[str] = Field(
        None,
        description="DCF forecast entry mode: 'ebitda' (default) or 'fcff_only' (explicit yearly FCFF)",
    )

    official_financials: Optional[JsonObject] = Field(
        None,
        description="Optional official filing enrichment snapshot from Titan, e.g. Belgian NBB data via Staatsbladmonitor.",
    )

    official_variance_analysis: Optional[JsonObject] = Field(
        None,
        description=(
            "Filing vs user variance: state, explanationRequired, optional explanation, "
            "percent deltas, severity (none/soft/hard vs policy thresholds)."
        ),
    )

    official_verification_badge: Optional[JsonObject] = Field(
        None,
        description="Reserved verification badge metadata for trust-layer surfaces.",
    )

    number_of_employees: Optional[int] = Field(None, ge=0, description="Number of employees")
    number_of_owners: Optional[int] = Field(
        1,
        ge=1,
        le=100,
        description="Number of operational owners actively working in the business (C-level + working shareholders)",
    )
    recurring_revenue_percentage: Decimal = Field(
        Decimal("0.0"),
        ge=Decimal("0.0"),
        le=Decimal("1.0"),
        description="Percentage of revenue that is recurring (Decimal('0.0') to Decimal('1.0'))",
    )
    rev_recurring_pct: Optional[Decimal] = Field(
        None,
        ge=Decimal("0"),
        le=Decimal("100"),
        description=(
            "Adaptive revenue-quality input: recurring revenue percentage. "
            "Accepts either a fraction (0.40) or whole percent (40)."
        ),
    )
    rev_recurring_amount: Optional[Decimal] = Field(
        None,
        ge=Decimal("0"),
        description=(
            "Adaptive revenue-quality input: annual recurring revenue amount "
            "in the request currency."
        ),
    )
    rev_top_client_concentration_pct: Optional[Decimal] = Field(
        None,
        ge=Decimal("0"),
        le=Decimal("100"),
        description=(
            "Adaptive revenue-quality input: top-client concentration percentage. "
            "Accepts either a fraction (0.15) or whole percent (15)."
        ),
    )
    rev_top_client_amount: Optional[Decimal] = Field(
        None,
        ge=Decimal("0"),
        description=(
            "Adaptive revenue-quality input: top-client revenue amount in the request currency."
        ),
    )
    rev_contract_backlog: Optional[Decimal] = Field(
        None,
        ge=Decimal("0"),
        description=(
            "Adaptive revenue-quality input: contracted backlog amount in the request currency."
        ),
    )

    business_type: Optional[str] = Field(
        None,
        max_length=50,
        description="Business ownership type (company, sole_proprietorship, etc)",
    )
    business_type_id: Optional[str] = Field(
        None,
        max_length=100,
        description="Business type ID for database-driven multiples and enhanced intelligence",
    )
    business_type_mix: Optional[List[JsonObject]] = Field(
        None,
        min_length=1,
        max_length=20,
        description=(
            "Titan-normalized weighted business type mix. Each item carries "
            "{business_type_id, business_type_title?, weight}. The legacy "
            "business_type_id remains the primary/highest-weight type."
        ),
    )
    business_type_weights: Optional[JsonObject] = Field(
        None,
        description="Optional compact caller weights keyed by business_type_id; audit-only after Titan normalization.",
    )
    allow_untrusted_multiples_fallback: bool = Field(
        False,
        description=(
            "Explicit opt-in to disclosed fallback multiples when no resolved "
            "Upswitch Index benchmark contract is available for the selected business_type_id."
        ),
    )
    category_id: Optional[str] = Field(
        None,
        max_length=100,
        description="Business type category ID from database (e.g., 'creative-media', 'professional-services')",
    )
    is_sole_trader: Optional[bool] = Field(
        None,
        description="Explicit flag indicating if this is a sole trader business. Auto-detected from business_structure, business_type, or ownership structure if not provided.",
    )
    revenue: Optional[Decimal] = Field(
        None, ge=0, description="Top-level revenue (for backward compatibility)"
    )
    employee_count: Optional[int] = Field(
        None, ge=0, description="Alternative field for number_of_employees"
    )
    business_description: Optional[str] = Field(
        None, max_length=5000, description="Business description"
    )
    business_highlights: Optional[str] = Field(
        None, max_length=2000, description="Key business highlights"
    )
    reason_for_selling: Optional[str] = Field(
        None, max_length=2000, description="Reason for selling"
    )
    city: Optional[str] = Field(None, max_length=100, description="City location")
    postal_code: Optional[str] = Field(None, max_length=20, description="Postal code")
    nace_code: Optional[str] = Field(
        None,
        max_length=20,
        description="Canonical NACE code used for methodology routing and report context",
    )
    nace_description: Optional[str] = Field(
        None,
        max_length=255,
        description="Human-readable NACE activity description",
    )
    activity_code: Optional[str] = Field(
        None,
        max_length=20,
        description="Market-facing activity code (for example Dutch SBI when it differs from NACE)",
    )
    canonical_nace_code: Optional[str] = Field(
        None,
        max_length=20,
        description="Stable canonical NACE code for downstream routing and mapping",
    )
    shares_for_sale: Optional[Decimal] = Field(
        None,
        ge=0,
        le=100,
        description="Percentage of shares for sale (0-100). Partial stakes are supported and scale equity outputs proportionally.",
    )
    owner_salary_addback: Optional[float] = Field(
        None,
        ge=0,
        description="Annual owner compensation (€) to add back for SDE calculation. "
        "When provided, overrides the revenue-based estimate.",
    )
    owner_role: Optional[str] = Field(
        None,
        pattern="^(working|passive)$",
        description=(
            "Seller's role post-close. 'working' = active operator (add-back is "
            "the delta vs. a market-rate replacement salary); 'passive' = "
            "non-operating shareholder (add-back is the full owner compensation "
            "since no replacement is needed)."
        ),
    )
    shareholder_roster: Optional[List[ShareholderRosterEntry]] = Field(
        None,
        description=(
            "Optional shareholder roster. `number_of_owners` remains the count "
            "of working owners only."
        ),
    )
    ownership_summary: Optional[OwnershipSummary] = Field(
        None,
        description="Optional ownership summary derived upstream from shareholder_roster",
    )
    has_audit: Optional[bool] = Field(
        None,
        description="Explicit audited-financials flag for WACC/company-risk pricing",
    )
    audited_financials: Optional[bool] = Field(
        None,
        description="Alias for has_audit used by some upstream callers",
    )

    # === Liquidation advisor inputs (Phase 2-4 + replacement-cost / SOA) ===
    # Single dict-shaped passthrough for the 10th method's advisor-grade
    # inputs.  Keys map 1:1 to `calculate_liquidation_result` kwargs:
    # liability_buckets, paid_up_capital, taxable_reserves,
    # realised_capital_gains, deferred_tax_liabilities, headcount,
    # monthly_rent, runway_months_orderly/forced, wind_down_overrides,
    # distress_wacc_orderly/forced, sensitivity_sample_count, nace_code,
    # multiples_value_override, adjusted_nav_override,
    # identifiable_intangibles_uplift_pct, effective_date, plus the
    # owner_premise_override enum-value string.  None → engine defaults.
    #
    # Mirrors `CalculateRequest.liquidation_inputs` on the stateless
    # schema (`api/schemas/stateless_api.py:358`).  Required here too
    # because Venus's manual flow (`/api/v1/valuation/calculate/stream`)
    # parses against this legacy schema, NOT the stateless one.  Without
    # this field Pydantic v2's default `extra='ignore'` silently drops
    # the dict at the request boundary (audit 2026-05-10).
    #
    # Forwarded to `calculate_all_methods(liquidation_inputs=...)` by
    # `comprehensive_valuation_orchestrator.py` so the engine receives
    # the advisor's headcount / monthly_rent / paid_up_capital /
    # deferred_tax_liabilities / owner_premise_override exactly as the
    # stateless path already does.
    liquidation_inputs: Optional[JsonObject] = Field(
        None,
        description=(
            "Phase 2-4 advisor-grade liquidation inputs (cascade buckets, "
            "tax bridge, wind-down assumptions, sensitivity, premise "
            "override). Keys map 1:1 to calculate_liquidation_result "
            "kwargs. None means engine defaults."
        ),
    )

    # BET-293 — typed holdings consolidation envelope. Pydantic v2 defaults to
    # extra='ignore', so declaring this is what makes the Titan → ValuationIQ
    # live valuation path load-bearing instead of silently stripping the parent /
    # subsidiaries payload at the API boundary.
    holdings_consolidation: Optional[HoldingConsolidationInput] = Field(
        None,
        description=(
            "Parent/subsidiary consolidation payload. When subsidiaries are present, "
            "ValuationIQ rolls up revenue/EBITDA/equity/current-year lines before "
            "running the standard valuation engine and report renderer."
        ),
    )
    valuation_case: Optional[JsonObject] = Field(
        None,
        description=(
            "Existing evidence-first decision envelope. The legacy engine path declares it "
            "so Pydantic cannot discard Titan's governed holdings revision and decisions."
        ),
    )

    @field_validator("shares_for_sale")
    @classmethod
    def validate_shares_for_sale_precision(cls, value: Optional[Decimal]) -> Optional[Decimal]:
        if value is None:
            return value
        if value.as_tuple().exponent < -2:
            raise ValueError("shares_for_sale must have at most two decimal places")
        return value

    @field_validator("country_code", mode="before")
    @classmethod
    def validate_supported_country_code(cls, value: object) -> str:
        return normalize_country_code(value)

    government_bond_yield: Optional[Decimal] = Field(
        None,
        ge=Decimal("0.0"),
        le=Decimal("0.5"),
        description="10-year government bond yield (override)",
    )
    long_term_gdp_growth: Optional[Decimal] = Field(
        None,
        ge=-Decimal("0.1"),
        le=Decimal("0.5"),
        description="Long-term GDP growth rate (override)",
    )
    equity_risk_premium: Optional[Decimal] = Field(
        None,
        ge=Decimal("0.0"),
        le=Decimal("0.2"),
        description="Equity risk premium / market risk premium override",
    )

    use_dcf: bool = Field(True, description="Include DCF valuation")
    use_multiples: bool = Field(True, description="Include market multiples valuation")
    projection_years: int = Field(
        10, ge=5, le=15, description="Number of years for DCF projections"
    )

    comparables: List[ComparableCompany] = Field(
        default=[], max_length=20, description="Optional list of comparable companies"
    )

    business_context: Optional[JsonObject] = Field(
        default=None,
        description="Business context metadata including owner profiling, data quality, and source attribution",
    )

    # Step 4's headcount-corroboration gate reads this. Pydantic v2's default
    # extra='ignore' silently strips undeclared fields, so without this
    # declaration `getattr(request, "headcount_confirmed", None)` could never be
    # True however the caller set it — the gate's second route was dead code and
    # step 4 fell through to the conservative cap unconditionally.
    headcount_confirmed: Optional[bool] = Field(
        default=None,
        description=(
            "True when the employee count was confirmed by a human rather than "
            "prefilled from a registry. Gates the owner-concentration discount: "
            "an unconfirmed registry headcount may only produce the disclosed "
            "conservative cap, never a full structural key-person haircut."
        ),
    )

    locale: Optional[str] = Field(
        default="en",
        pattern="^(nl|en)$",
        description="Report language: 'nl' (Dutch) or 'en' (English). Defaults to 'en' if not provided.",
    )

    selected_method: Optional[str] = Field(
        default=None,
        description="User-selected valuation method (e.g. 'dcf', 'adjusted_nav', 'ebitda_multiple'). "
        "Bypasses engine guardrails for that method (e.g. DCF revenue threshold).",
    )

    user_configured_dcf: Optional[bool] = Field(
        default=None,
        description="True when the user explicitly configured DCF parameters "
        "(WACC, terminal growth, forecast years). Bypasses revenue-based "
        "DCF exclusion thresholds.",
    )

    user_weights: Optional[Dict[str, float]] = Field(
        default=None,
        description="Method-key → weight (0.0-1.0) map for blended valuation. "
        "Weights must sum to 1.0. Example: {'ebitda_multiple': 0.7, 'dcf': 0.3}",
    )
    user_weight_justification: Optional[str] = Field(
        default=None,
        max_length=2000,
        description="Accountant's textual rationale for the chosen weighting",
    )

    # Startup Valuation Engine inputs (venture / pre-revenue path)
    # Required when ``selected_method == "startup_valuation"``.  Mirrors the
    # contract on ``CalculateRequest`` (stateless API) so the legacy
    # ``/api/v1/valuation/calculate`` endpoint can also drive the venture
    # engine (Berkus + Scorecard + VC method) end-to-end.
    startup_inputs: Optional[StartupInputs] = Field(
        default=None,
        description=(
            "Founder-supplied qualitative + traction + cap-table inputs for "
            "the Startup Valuation method.  Required when "
            "selected_method='startup_valuation'."
        ),
    )
    lifecycle_stage_triage: Optional[object] = None
    owner_dependency: Optional[OwnerDependencyFactors] = Field(
        default=None,
        description="12-factor owner dependency assessment for key person risk evaluation",
    )

    # Tax Latencies (belastinglatenties) — equity bridge adjustments
    tax_latencies: Optional[List[TaxLatencyInput]] = Field(
        default=None,
        max_length=50,
        description="Deferred tax assets/liabilities that adjust equity value",
    )

    # Balance Sheet Adjustments — itemized EV-to-equity bridge line items
    balance_sheet_adjustments: Optional[List[BalanceSheetAdjustmentInput]] = Field(
        default=None,
        max_length=50,
        description="Itemized balance sheet adjustments (excess cash, non-operating assets, provisions, etc.)",
    )

    # Real estate carve-out — exclude seller-owned property from the transaction perimeter
    real_estate_treatment: Optional[str] = Field(
        None,
        description=(
            "Transaction perimeter for real estate: none, owned_included, "
            "owned_excluded, leased, or unresolved. Legacy included/carve_out "
            "aliases remain accepted."
        ),
    )
    exclude_real_estate: Optional[bool] = Field(
        False,
        description="Exclude seller-owned real estate from the transaction and adjust EBITDA for post-close rent.",
    )
    real_estate_market_value: Optional[Decimal] = Field(
        None,
        ge=Decimal("0"),
        description="Market value of the real estate when it is included in the transaction.",
    )
    real_estate_book_value: Optional[Decimal] = Field(
        None,
        ge=Decimal("0"),
        description="Book value of the real estate in the operating company.",
    )
    estimated_market_rent: Optional[Decimal] = Field(
        None,
        ge=Decimal("0"),
        description="Estimated annual market rent that the operating company will pay after the carve-out.",
    )

    # Advanced advisor controls (UPS-ADV-300)
    multiple_calibration_adjustment: Optional[Decimal] = Field(
        None,
        ge=Decimal("-10"),
        le=Decimal("10"),
        description=(
            "Advisor-entered specific risk/quality premium in multiple turns. "
            "Example: -1.0 discounts a 5.5x sector multiple to 4.5x."
        ),
    )
    multiple_calibration_note: Optional[str] = Field(
        None,
        max_length=1000,
        description="Required audit-trail note when multiple_calibration_adjustment is non-zero.",
    )
    effective_multiple_override: Optional[Decimal] = Field(
        None,
        gt=Decimal("0"),
        le=Decimal("50"),
        description=(
            "Advisor-entered final effective multiple after blend and discounts. "
            "Requires effective_multiple_override_note and never feeds benchmark indexes."
        ),
    )
    effective_multiple_override_note: Optional[str] = Field(
        None,
        max_length=1000,
        description="Required audit-trail note when effective_multiple_override is set.",
    )
    historical_ebitda_weighting_mode: Optional[str] = Field(
        "standard",
        description="Historical EBITDA basis: 'standard' or 'weighted'.",
    )
    historical_ebitda_weights: Optional[Dict[int, Decimal]] = Field(
        None,
        description=(
            "Advisor-entered historical EBITDA weights keyed by fiscal year. "
            "Values may sum to 1.0 or 100."
        ),
    )
    show_enterprise_to_equity_bridge: Optional[bool] = Field(
        True,
        description="Presentation toggle for showing the EV-to-equity waterfall in UI/PDF.",
    )
    multiple_type_weights: Optional[Dict[str, Decimal]] = Field(
        None,
        description=(
            "Advisor-selected EV/EBITDA, EV/Revenue and P/E blend weights. "
            "Values may be ratios or percentages."
        ),
    )
    risk_analysis_enabled: Optional[bool] = Field(
        True,
        description=(
            "Master toggle for the qualitative risk/discount layer. False keeps "
            "the pre-adjustment comparable multiple as a labeled reference."
        ),
    )
    advisor_discount_weights: Optional[Dict[str, Decimal]] = Field(
        None,
        description=(
            "Advisor-selected per-discount influence multipliers. 0 disables a "
            "discount, 1 keeps the model weight, values above 1 increase influence."
        ),
    )
    discount_floor_factor: Optional[Decimal] = Field(
        None,
        ge=Decimal("0"),
        le=Decimal("1"),
        description="Lower bound for the multiplicative discount stack factor.",
    )
    business_type_segments: Optional[List[JsonObject]] = Field(
        None,
        description=(
            "Candidate SOTP segments. True SOTP requires each confirmed segment "
            "to carry earnings and a basis-aware multiple."
        ),
    )

    # ============================================================================
    # ENRICHED BUSINESS TYPE DATA (from Titan via Railway business_types DB)
    # Titan transports published Upswitch Index benchmark contracts and business-type
    # context. AI collector/proposal output is not authoritative until
    # deterministic gates and operator approval publish it.
    # ============================================================================

    # Classification (database-sourced)
    sector: Optional[str] = Field(
        None, max_length=100, description="Sector classification from business_types DB"
    )
    sub_industry: Optional[str] = Field(
        None, max_length=100, description="Sub-industry classification from business_types DB"
    )
    industry_mapping: Optional[str] = Field(
        None, max_length=100, description="Python industry mapping from business_types DB"
    )

    # Valuation multiples with distributions (from Upswitch Index)
    ev_ebitda_multiple: Optional[JsonObject] = Field(
        None, description="EV/EBITDA multiple distribution: {median, p10, p25, p75, p90}"
    )
    ev_revenue_multiple: Optional[JsonObject] = Field(
        None, description="EV/Revenue multiple distribution: {median, p10, p25, p75, p90}"
    )
    pe_ratio: Optional[JsonObject] = Field(
        None, description="P/E ratio distribution: {median, p10, p25, p75, p90}"
    )

    # BET-218 — multi-owner roster. A list of per-owner dicts, each with a
    # 12-factor `factors` payload plus `role_criticality` and
    # `owner_hours_per_week`. The synthesizer aggregates it into one
    # composite transferability index for the owner-dependency engine.
    # Open list shape so the wire contract is forgiving; Pydantic v2's
    # default extra='ignore' would strip this field if not declared —
    # declaring it keeps the Titan→engine roster contract intact.
    owner_profile_roster: Optional[List[JsonObject]] = Field(
        None,
        description=(
            "Optional BET-218 multi-owner roster: per-owner 12-factor "
            "owner-dependency assessments, aggregated into a composite "
            "transferability index. Omit for single-owner valuations."
        ),
    )

    # Valuation Preferences (from business type analysis)
    valuation_preferences: Optional[JsonObject] = Field(
        None,
        description=(
            "Valuation method preferences: {dcf_preference, "
            "multiples_preference, owner_dependency_impact, "
            "preferred_multiples, primary_model}. NOTE: "
            "`owner_dependency_impact` is v1 SHADOW-ONLY — preserved for "
            "telemetry but not load-bearing for adjustment math. The live "
            "owner-profiling adjustment runs through the v2 "
            "`owner_dependency_factors` payload via `OwnerDependencyProcessor`. "
            "See SPIKE-1 §3.4 / OWNER-PROFILING-1 OP-4."
        ),
    )

    # Industry benchmarks (from Upswitch Index)
    industry_benchmarks: Optional[JsonObject] = Field(
        None,
        description="Industry benchmarks: {typical_ebitda_margin, typical_revenue, typical_employee_count}",
    )

    # Market Context
    market_context: Optional[JsonObject] = Field(
        None,
        description="Market context: {maturity, trend, seasonality_impact, economic_sensitivity}",
    )

    # Data Quality Metadata
    multiples_metadata: Optional[JsonObject] = Field(
        None,
        description="Multiples data quality: {source, sample_size, quality_score, last_updated}",
    )

    # Additional enrichment data
    risk_factors: Optional[List[object]] = Field(None, description="Business type risk factors")
    key_metrics: Optional[Union[JsonObject, List[object]]] = Field(
        None, description="Key metrics for this business type (accepts Dict or List)"
    )

    # Accountant branding (injected by Titan for co-branded reports)
    metadata: Optional[JsonObject] = Field(
        None,
        description="Request metadata including accountant branding: {accountant_firm_name, accountant_logo_url}",
    )

    # Meerwaarde-tax (fiscal_4x) advisor inputs — captured by Venus
    # FiscalInputsSection. Hoisted into report metadata by the aggregator
    # (`_build_fiscal_reference`) and consumed by `fiscal_section.py` to
    # populate the four-anchor "hoogste van" worksheet, the
    # aanschaffingswaarde recommendation, and the tax-impact panel.
    # Open dict so future advisor inputs ride through without a schema
    # bump. Pydantic v2 default extra='ignore' would strip this field if
    # not declared — declaring it ensures the wire contract survives.
    fiscal_inputs: Optional[JsonObject] = Field(
        None,
        description=(
            "Meerwaarde-tax advisor inputs (peildatum, company role, "
            "interne meerwaarde, EBITDA basis, aanschaffingswaarde, four "
            "statutory anchors). Read by the fiscal_reference report "
            "builder; engine ignores."
        ),
    )

    # ============================================================================
    # SME CALIBRATION DATA (database-driven SME multiples from Titan)
    # These are tier-specific multiples for micro/small/medium SMEs
    # Based on: Pepperdine 2024, VFB Belgium 2024, academic calibration factors
    # Priority: 1. This data (from Titan) -> 2. DatabaseDrivenDefaults -> 3. Hardcoded
    # ============================================================================
    sme_calibration: Optional[JsonObject] = Field(
        None,
        description="SME calibration data: {ev_ebitda_micro, ev_ebitda_small, ev_ebitda_medium, "
        "ev_revenue_micro, ev_revenue_small, ev_revenue_medium, "
        "size_premium_micro, size_premium_small, size_premium_medium, "
        "liquidity_discount, calibration_source, calibration_last_updated}",
    )

    # ============================================================================
    # SDE CALIBRATION DATA (database-driven SDE multiples from Titan)
    # Critical for small business valuation (< EUR 2M revenue)
    # Based on: BizBuySell 2024, Pepperdine 2024, IBBA surveys
    # Academic: Trugman (2017), West & Jones (2012)
    # ============================================================================
    sde_calibration: Optional[JsonObject] = Field(
        None,
        description="SDE calibration data: {sde_multiple_micro, sde_multiple_small, sde_multiple_medium, "
        "sde_multiple_p25, sde_multiple_p75, sde_owner_dependency_factor, "
        "sde_recurring_revenue_factor, sde_growth_factor, sde_sample_size, sde_source}",
    )

    # ============================================================================
    # ASSET-BASED CALIBRATION DATA (database-driven asset factors from Titan)
    # For manufacturing, construction, real estate, distressed businesses
    # Based on: Hitchner (2017), industry appraisal data
    # ============================================================================
    asset_based_calibration: Optional[JsonObject] = Field(
        None,
        description="Asset-based calibration data: {asset_equipment_fmv_factor, asset_inventory_fmv_factor, "
        "asset_receivables_factor, liquidation_orderly_factor, liquidation_forced_factor, "
        "asset_methodology_preference}",
    )

    # ============================================================================
    # ECONOMIC CONTEXT (Titan-provided static defaults)
    # Risk-free rate, GDP growth, terminal growth for DCF calculations
    # Source: ECB 10Y bond yields, IMF projections (from Titan config)
    # ============================================================================
    economic_context: Optional[JsonObject] = Field(
        None,
        description="Economic context from Titan: {risk_free_rate, gdp_growth_rate, "
        "terminal_growth_rate, inflation_rate, country_code, source}. "
        "Used for DCF calculations instead of direct OECD/ECB API calls.",
    )

    @field_validator("key_metrics", mode="before")
    @classmethod
    def validate_key_metrics(cls, v: object) -> Optional[JsonObject]:
        return normalize_key_metrics_field(v)

    @field_validator("real_estate_treatment", mode="before")
    @classmethod
    def normalize_real_estate_treatment(cls, v: object) -> Optional[str]:
        return normalize_real_estate_treatment_field(v)

    @field_validator("historical_ebitda_weighting_mode", mode="before")
    @classmethod
    def normalize_historical_ebitda_weighting_mode(cls, v: object) -> str:
        return normalize_historical_ebitda_weighting_mode_field(v)

    @field_validator("historical_ebitda_weights", mode="before")
    @classmethod
    def normalize_historical_ebitda_weights(cls, v: object) -> Optional[Dict[int, Decimal]]:
        return normalize_historical_ebitda_weights_field(v)

    @field_validator("business_model", mode="before")
    @classmethod
    def validate_business_model(cls, v: object) -> BusinessModel:
        return normalize_business_model_field(v)

    @field_validator("current_year_data")
    @classmethod
    def validate_current_year_not_in_future(cls, value: YearDataInput) -> YearDataInput:
        max_confirmable_year = _get_max_confirmable_year_from_facade()
        if value.year > max_confirmable_year:
            raise ValueError(
                f"current_year_data.year ({value.year}) cannot be later than the previous calendar year ({max_confirmable_year})"
            )
        return value

    @field_validator("historical_years_data")
    @classmethod
    def validate_historical_years(cls, v: object) -> object:
        return validate_historical_years_order(v)

    @field_validator("industry")
    @classmethod
    def validate_industry(cls, v: str) -> str:
        """
        Validate and sanitize industry field.

        Args:
            v: Industry value

        Returns:
            Validated and sanitized industry value
        """
        return _validate_industry_from_facade(v)

    @model_validator(mode="after")
    def validate_year_buckets(self):
        return validate_year_buckets_request(self)

    @field_validator("business_context")
    @classmethod
    def validate_percentage_contract(cls, value):
        return validate_context_percentage_units(value)

    @model_validator(mode="after")
    def validate_dcf_is_ready(self) -> "ValuationRequest":
        explicitly_requested = explicitly_requests_dcf(self)
        readiness = resolve_dcf_readiness(
            current_year_data=self.current_year_data,
            historical_rows=self.historical_years_data,
            forecast_rows=self.forecast_years_data,
            dcf_input_mode=self.dcf_input_mode,
        )
        if explicitly_requested:
            require_dcf_readiness(readiness)
        elif self.use_dcf and not readiness.ready:
            # Capability/default flags are not user intent. Adaptive and legacy
            # hybrid requests degrade to their market leg when DCF is not ready.
            self.use_dcf = False
        return self

    @model_validator(mode="after")
    def validate_advisor_controls(self):
        return validate_advisor_controls_request(self)

    @model_validator(mode="after")
    def normalize_business_type_mix_contract(self) -> "ValuationRequest":
        primary, mix, weights = normalize_business_type_mix_fields(
            business_type_id=self.business_type_id,
            business_type_mix=self.business_type_mix,
            business_type_segments=self.business_type_segments,
            business_type_weights=self.business_type_weights,
        )
        if primary:
            self.business_type_id = primary
        if mix is not None:
            self.business_type_mix = mix
        if weights is not None:
            self.business_type_weights = weights
        return self

    @model_validator(mode="after")
    def normalize_enrichment_multiple_distributions(self) -> "ValuationRequest":
        return normalize_enrichment_multiple_distributions_request(self)
