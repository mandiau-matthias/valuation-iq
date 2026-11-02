"""Stateless ValuationIQ request schema and compatibility exports."""

from collections.abc import Mapping
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from src.utils.percentage_input_contract import (
    declared_percentage,
    validate_context_percentage_units,
)

from ..dcf_readiness import explicitly_requests_dcf, require_dcf_readiness, resolve_dcf_readiness

from src.api.business_type_mix import normalize_business_type_mix_fields
from src.api.legacy_input_schemas import (
    BalanceSheetAdjustmentInput,
    HoldingConsolidationInput,
    OwnershipSummary,
    ShareholderRosterEntry,
    TaxLatencyInput,
)
from src.api.historical_ebitda_weights import (
    normalize_historical_ebitda_weights as normalize_historical_ebitda_weights_input,
)
from src.api.schemas.stateless_common import (
    BusinessTypeCalibration,
    DisclosedExternalMarketReference,
    ExternalMarketReferenceContract,
    EconomicContext,
    JsonObject,
    NormalizationAdjustment,
    OwnerDependencyInput,
    RealEstateYieldEvidenceContract,
    WaccEvidenceContract,
    YearDataStateless,
)
from src.api.schemas.negative_ebitda_recovery import (
    RecoveryInputs,
    RecoveryVerificationReceipt,
)
from src.api.schemas.valuation_contracts import (
    ValuationCase,
    validate_priced_accounting_evidence_request,
)
from src.api.schemas.stateless_report_schemas import (
    GenerateReportRequest,
    GenerateReportResponse,
    ReportBranding,
)
from src.api.schemas.stateless_response_schemas import (
    Artifacts,
    CalculateResponse,
    ForwardConeAssumptionEvidence,
    ForwardConeMethodContribution,
    ForwardConeMethodExclusion,
    ForwardScenarioDriverDelta,
    ForwardScenarioPath,
    ForwardValueCone,
    ForwardValueConePoint,
    MethodResult,
    TriageFlag,
    ValuationTimelinePoint,
)
from src.config.countries import normalize_country_code
from src.config.country_packs import country_pack
from src.api.schemas.stateless_validation_schemas import (
    ValidateRequest,
    ValidateResponse,
    ValidationWarning,
)
from src.api.schemas.weighted_valuation import WeightedMethodContribution, WeightedValuationResult
from src.domain.method_keys import (
    CANONICAL_METHOD_KEYS,
    NON_COMBINABLE_METHOD_KEYS,
    USER_WEIGHT_METHOD_KEYS,
    MethodKey,
    normalize_method_key,
    normalize_selected_method_key,
)
from src.domain.models import BusinessModel, ConfidenceLevel
from src.domain.owner_models.owner_dependency import OwnerDependencyFactors
from src.domain.startup_valuation import CapTableSummary, LifecycleStageTriage, StartupInputs
from src.utils.fiscal_year import get_max_confirmable_year

# =============================================================================
# CALCULATE ENDPOINT
# =============================================================================


def _has_text(value: str | None) -> bool:
    return bool((value or "").strip())


def _require_startup_inputs(request: "CalculateRequest") -> None:
    if request.selected_method == "startup_valuation" and request.startup_inputs is None:
        raise ValueError(
            "selected_method='startup_valuation' requires the 'startup_inputs' "
            "block (qualitative sliders, traction, cap-table)."
        )


def _require_included_real_estate_values(request: "CalculateRequest") -> None:
    if request.real_estate_treatment not in {"included", "owned_included"}:
        return
    if request.real_estate_market_value is None:
        raise ValueError("real_estate_market_value is required for owned/included real estate")
    if request.real_estate_book_value is None:
        raise ValueError("real_estate_book_value is required for owned/included real estate")


def _require_advisor_override_notes(request: "CalculateRequest") -> None:
    adjustment = request.multiple_calibration_adjustment or Decimal("0")
    if adjustment != Decimal("0") and not _has_text(request.multiple_calibration_note):
        raise ValueError(
            "multiple_calibration_note is required when multiple_calibration_adjustment is non-zero"
        )

    if request.effective_multiple_override is not None and not _has_text(
        request.effective_multiple_override_note
    ):
        raise ValueError(
            "effective_multiple_override_note is required when effective_multiple_override is set"
        )

    if request.business_type_multiple_overrides and not _has_text(
        request.business_type_multiple_override_note
    ):
        raise ValueError(
            "business_type_multiple_override_note is required when "
            "business_type_multiple_overrides is set"
        )


def _historical_ebitda_weights_total_is_valid(total: Decimal) -> bool:
    return abs(total - Decimal("1")) <= Decimal("0.02") or abs(total - Decimal("100")) <= Decimal(
        "2"
    )


def _validate_historical_ebitda_weighting(request: "CalculateRequest") -> None:
    weights = request.historical_ebitda_weights
    if request.historical_ebitda_weighting_mode == "weighted":
        if not weights:
            raise ValueError(
                "historical_ebitda_weights are required when historical_ebitda_weighting_mode='weighted'"
            )
        if not (3 <= len(weights) <= 5):
            raise ValueError("historical_ebitda_weights must contain 3 to 5 fiscal years")

    if not weights:
        return

    total = sum((Decimal(str(weight)) for weight in weights.values()), Decimal("0"))
    if not _historical_ebitda_weights_total_is_valid(total):
        raise ValueError("historical_ebitda_weights must sum to 1.0 or 100")


def _normalize_request_business_type_mix(request: "CalculateRequest") -> None:
    _, mix, _ = normalize_business_type_mix_fields(
        business_type_id=request.business_type_calibration.business_type_id,
        business_type_mix=request.business_type_mix,
        business_type_segments=request.business_type_segments,
        business_type_weights=request.business_type_weights,
    )
    if mix is None:
        return
    request.business_type_mix = mix
    request.business_type_weights = {
        str(segment["business_type_id"]): segment["weight"] for segment in mix
    }


class CalculateRequest(BaseModel):
    """
    Stateless calculation request - receives ALL data from Titan.

    BRAIN & MUSCLE: Titan collects all data and sends it in one request.
    ValuationIQ performs the calculation without accessing any external state.
    """

    # === Request identification ===
    valuation_id: str = Field(
        ...,
        pattern=r"^val_\d+_[A-Za-z0-9_-]+(_[A-Za-z0-9_-]+)?$",
        description="Unique valuation ID from Titan (supports hex and base64url session keys)",
    )
    session_id: Optional[str] = Field(None, description="Session ID for tracking")
    valuation_case: Optional[ValuationCase] = Field(
        None,
        description=(
            "Versioned evidence/decision envelope. Calculation inputs remain explicit on "
            "this request while legacy clients migrate to the canonical case contract."
        ),
    )

    # === Company Information ===
    company_name: str = Field(..., min_length=1, max_length=200)
    country_code: str = Field(..., pattern="^[A-Z]{2}$")
    currency: Optional[str] = Field(
        None,
        pattern=r"^[A-Z]{3}$",
        description=(
            "ISO-4217 currency of every unconverted monetary input. None means currency "
            "is unresolved; ValuationIQ must not relabel the result as EUR."
        ),
    )
    registry_country: Optional[str] = Field(
        None,
        pattern="^[A-Z]{2}$",
        description="Country of incorporation, independent from the operating market",
    )
    registration_number: Optional[str] = Field(
        None, max_length=50, description="Generic company registration number (KBO/KVK)"
    )
    kbo_number: Optional[str] = Field(None, max_length=50, description="Belgian KBO/BCE number")
    kvk_number: Optional[str] = Field(None, max_length=50, description="Dutch KVK number")
    vat_number: Optional[str] = Field(None, max_length=50, description="VAT number")
    legal_form: Optional[str] = Field(None, max_length=100, description="Legal form")
    postal_code: Optional[str] = Field(None, max_length=20, description="Postal code")
    city: Optional[str] = Field(None, max_length=100, description="City location")
    incorporated_on: Optional[str] = Field(
        None,
        max_length=20,
        description="Incorporation date (ISO-8601 where available), sealed into the company profile.",
    )
    industry: str = Field(..., min_length=1, max_length=100)
    business_model: str = Field(..., description="Business model type")
    founding_year: int = Field(..., ge=1900, le=2100)
    nace_code: Optional[str] = Field(
        None,
        max_length=20,
        description="Canonical NACE code used for holding-company and report routing",
    )
    nace_description: Optional[str] = Field(
        None,
        max_length=255,
        description="Human-readable NACE activity description",
    )
    activity_code: Optional[str] = Field(
        None,
        max_length=20,
        description="Market-facing activity code when it differs from canonical NACE",
    )
    canonical_nace_code: Optional[str] = Field(
        None,
        max_length=20,
        description="Stable canonical NACE code for downstream routing",
    )
    business_description: Optional[str] = Field(None, max_length=5000)
    business_highlights: Optional[str] = Field(None, max_length=5000)
    reason_for_selling: Optional[str] = Field(None, max_length=2000)

    # === Financial Data (already normalized by Titan) ===
    current_year: YearDataStateless = Field(..., description="Current year financial data")
    historical_years: List[YearDataStateless] = Field(
        default=[],
        max_length=14,
        description=(
            "Historical and forecast timeline rows (oldest to newest): up to "
            "nine historical filed observations plus five governed forecast years; "
            "the separate current_year makes ten actual curve points"
        ),
    )

    # === Normalization decisions (ValuationIQ remains calculation authority) ===
    normalizations: List[NormalizationAdjustment] = Field(
        default=[],
        description=(
            "Evidence-linked normalization decisions transported by Titan. "
            "ValuationIQ determines priced versus proposed treatment."
        ),
    )
    recovery_inputs: Optional[RecoveryInputs] = Field(
        None,
        description=(
            "Versioned downside/base/upside recovery schedules for a negative-EBITDA "
            "assessment. Authenticated receipts are accepted only when committed by "
            "the signed valuation_case.v2."
        ),
    )

    # === Business Type Calibration (from Titan's DB) ===
    business_type_calibration: BusinessTypeCalibration = Field(
        ..., description="Business type multiples and benchmarks from database"
    )
    business_type_mix: Optional[List[Dict[str, object]]] = Field(
        None,
        min_length=1,
        max_length=20,
        description=(
            "Titan-normalized weighted business type mix. The calibration and "
            "business_type_id remain the weighted primary/benchmark envelope."
        ),
    )
    business_type_weights: Optional[JsonObject] = Field(
        None,
        description=(
            "Compact business type weights keyed by business_type_id. Accepted "
            "for parity with the legacy API and normalized into business_type_mix."
        ),
    )
    sme_calibration: Optional[JsonObject] = Field(
        None,
        description=(
            "Optional tier calibration (size premiums, EV/EBITDA by tier) mirroring "
            "sessioned Titan `sme_calibration`. When set, DCF WACC uses these before the "
            "academic size-premium curve."
        ),
    )

    # === Economic Context (from Titan) ===
    economic_context: EconomicContext = Field(..., description="Economic data for DCF calculations")

    # === Owner Dependency (from Titan's chat) ===
    owner_dependency: Optional[OwnerDependencyInput] = Field(
        None, description="Owner dependency assessment"
    )
    owner_dependency_factors: Optional[OwnerDependencyFactors] = Field(
        None,
        description=(
            "Canonical 12-factor transferability assessment. When present, the "
            "owner-dependency engine applies one disclosed equity-side adjustment."
        ),
    )
    business_context: Optional[JsonObject] = Field(
        None,
        description="Shared override/context payload for DCF inputs such as concentration and benchmark overrides",
    )
    metadata: Optional[JsonObject] = Field(
        None,
        description="Request metadata, including explicit fallback consent and report context.",
    )
    official_financials: Optional[JsonObject] = Field(
        None,
        description=(
            "Immutable official-filing evidence and source provenance supplied by "
            "Hermes/Titan. This evidence informs confidence and audit lineage; it "
            "is not itself a valuation judgment."
        ),
    )
    benchmark_contract: Optional[JsonObject] = Field(
        None,
        description="Request-level resolved benchmark contract for stateless callers.",
    )
    multiples_metadata: Optional[JsonObject] = Field(
        None,
        description="Multiples provenance block; may contain benchmark_contract.",
    )
    allow_untrusted_multiples_fallback: bool = Field(
        False,
        description=(
            "Explicit opt-in to disclosed fallback multiples when no resolved Upswitch "
            "Index benchmark contract is available."
        ),
    )
    untrusted_multiples_fallback_reason: Optional[str] = Field(
        None,
        max_length=2000,
        description=(
            "Required written advisor rationale for the disclosed external market "
            "fallback. The rationale is audit evidence, not benchmark provenance."
        ),
    )
    disclosed_external_market_reference: Optional[DisclosedExternalMarketReference] = Field(
        None,
        description=(
            "Advisor-defined external multiple reference range used only after explicit "
            "fallback consent. This is not an Upswitch Index contract or empirical "
            "percentile distribution."
        ),
    )
    external_market_reference_contract: Optional[ExternalMarketReferenceContract] = Field(
        None,
        description=(
            "Advisor-reviewed, hash-sealed dossier evidence for a non-statistical "
            "external EV/EBITDA reference. This is not an Upswitch Index contract "
            "and does not authorize empirical percentile claims."
        ),
    )
    wacc_evidence_contract: Optional[WaccEvidenceContract] = Field(
        None,
        description=(
            "Titan-signed direct sector WACC evidence. A direct rate already includes "
            "the source methodology's size premium and cannot be combined with a "
            "component-level size-premium override."
        ),
    )
    real_estate_yield_evidence_contract: Optional[RealEstateYieldEvidenceContract] = Field(
        None,
        description=(
            "Titan-reviewed property title, annual NOI, occupancy, property debt and "
            "metric-matched cap-rate evidence for canonical income capitalisation. "
            "Priced only when committed by the signed valuation_case.v2."
        ),
    )
    advisor_qualifications: List[str] = Field(
        default_factory=list,
        max_length=10,
        description=(
            "Non-economic, advisor-authored transaction qualifications sealed with the "
            "calculation run. They disclose scope limitations and risks; they cannot "
            "alter values, multiples, method weights, or benchmark provenance."
        ),
    )
    has_audit: Optional[bool] = Field(
        None,
        description="Explicit audited-financials flag for WACC/company-risk pricing",
    )
    audited_financials: Optional[bool] = Field(
        None,
        description="Alias for has_audit used by some upstream callers",
    )
    is_audited: Optional[bool] = Field(
        None,
        description="Legacy alias for has_audit used by some upstream callers",
    )

    # === Liquidation advisor inputs (Phase 2-4 + replacement-cost / SOA) ===
    # Single dict-shaped passthrough for the 10th method's advisor-grade
    # inputs. Keys map 1:1 to `calculate_liquidation_result` kwargs:
    # liability_buckets, paid_up_capital, taxable_reserves,
    # realised_capital_gains, deferred_tax_liabilities, headcount,
    # monthly_rent, runway_months_orderly/forced, wind_down_overrides,
    # distress_wacc_orderly/forced, sensitivity_sample_count, nace_code,
    # multiples_value_override, adjusted_nav_override,
    # identifiable_intangibles_uplift_pct, effective_date, plus the
    # owner_premise_override enum-value string. None → engine defaults.
    # Validated downstream at the wrapper boundary; keeping it open
    # here means future kwargs ride through without a schema change.
    liquidation_inputs: Optional[JsonObject] = Field(
        None,
        description=(
            "Phase 2-4 advisor-grade liquidation inputs (cascade buckets, "
            "tax bridge, wind-down assumptions, sensitivity, premise "
            "override). Keys map 1:1 to calculate_liquidation_result "
            "kwargs. None means engine defaults."
        ),
    )

    # Meerwaarde-tax (fiscal_4x) advisor inputs — captured by Venus
    # FiscalInputsSection. Hoisted into report metadata by the aggregator
    # (`_build_fiscal_reference`) and consumed by `fiscal_section.py` to
    # populate the four-anchor "hoogste van" worksheet, the
    # aanschaffingswaarde recommendation, and the tax-impact panel.
    # Keys (all optional):
    #   - acquisition_cost: float (advisor pin; falls back to max-of-4)
    #   - company_role: 'werkmaatschappij' | 'holding' | 'mixed'
    #   - internal_transfer: bool (drives 33% rate banner)
    #   - ebitda_basis: 'statutair' | 'genormaliseerd'
    #   - reference_date: ISO YYYY-MM-DD (peildatum override)
    #   - anchor_2_value / anchor_3_value / anchor_4_value: float
    #   - anchors_acknowledged: bool
    # Validated downstream at the report boundary; keeping it open here
    # means future advisor inputs ride through without a schema change.
    fiscal_inputs: Optional[JsonObject] = Field(
        None,
        description=(
            "Meerwaarde-tax advisor inputs (peildatum, company role, "
            "interne meerwaarde, EBITDA basis, aanschaffingswaarde, four "
            "statutory anchors). Keys are read by the fiscal_reference "
            "report builder. None means the report uses engine-derived "
            "defaults (forfait formula only, no anchor 2/3/4 entries)."
        ),
    )

    tax_latencies: Optional[List[TaxLatencyInput]] = Field(
        None,
        max_length=50,
        description="Deferred-tax assets/liabilities applied once in the EV-to-equity bridge.",
    )
    balance_sheet_adjustments: Optional[List[BalanceSheetAdjustmentInput]] = Field(
        None,
        max_length=50,
        description="Itemized, signed-by-type EV-to-equity bridge adjustments.",
    )
    restricted_cash: Optional[Decimal] = Field(
        None,
        ge=Decimal("0"),
        description="Cash unavailable to a buyer and excluded once from the equity bridge.",
    )
    lease_liabilities: Optional[Decimal] = Field(
        None,
        ge=Decimal("0"),
        description="Lease liabilities outside reported financial debt, deducted once.",
    )
    debt_like_items: Optional[Decimal] = Field(
        None,
        ge=Decimal("0"),
        description="Other completion-account debt-like liabilities, deducted once.",
    )
    normalized_nwc_target: Optional[Decimal] = Field(
        None,
        ge=Decimal("0"),
        description="Advisor-supported absolute normalized NWC target; null remains unresolved.",
    )
    completion_account_inputs_provided: bool = Field(
        False,
        exclude=True,
        description="Internal presence sentinel; not part of the public response wire.",
    )
    holdings_consolidation: Optional[HoldingConsolidationInput] = Field(
        None,
        description="Parent/subsidiary structure, ownership and intercompany eliminations.",
    )
    shareholder_roster: Optional[List[ShareholderRosterEntry]] = Field(
        None,
        max_length=100,
        description="Evidence-backed shareholder roster; not a substitute for shares_for_sale.",
    )
    ownership_summary: Optional[OwnershipSummary] = Field(
        None,
        description="Derived ownership totals used for transferability and report provenance.",
    )

    # === Calculation Options ===
    methodology: Literal["HYBRID", "DCF", "MULTIPLES", "ASSET_BASED"] = Field(
        default="HYBRID", description="Valuation methodology: HYBRID, DCF, MULTIPLES, ASSET_BASED"
    )
    include_dcf: bool = Field(True, description="Include DCF valuation")
    include_multiples: bool = Field(True, description="Include multiples valuation")
    projection_years: int = Field(5, ge=3, le=15, description="DCF projection years")
    dcf_input_mode: Optional[Literal["ebitda", "fcff_only"]] = Field(
        None,
        description=(
            "DCF forecast entry mode. 'fcff_only' values explicit free_cash_flow rows "
            "even when current EBITDA is zero or negative."
        ),
    )

    # Pass-5: advisor-configured asking-price buffer override (Mercury → Titan
    # → ValuationIQ). Fraction in [0, 0.25] — replaces confidence-aware default.
    asking_price_buffer_pct: Optional[Decimal] = Field(
        None,
        ge=Decimal("0.0"),
        le=Decimal("0.25"),
        description=(
            "Firm-level asking-price buffer override as a fraction. "
            "Bounded to [0, 0.25]; None falls back to the confidence default."
        ),
    )

    # Advanced advisor controls (UPS-ADV-300)
    real_estate_treatment: Optional[
        Literal[
            "none",
            "carve_out",
            "included",
            "owned_included",
            "owned_excluded",
            "leased",
            "unresolved",
        ]
    ] = Field(
        None,
        description=(
            "Transaction perimeter for real estate. included/carve_out remain wire-compatible "
            "aliases for owned_included/owned_excluded."
        ),
    )
    real_estate_market_value: Optional[Decimal] = Field(
        None,
        ge=Decimal("0"),
        description="Market value of real estate when it is included in the transaction.",
    )
    real_estate_book_value: Optional[Decimal] = Field(
        None,
        ge=Decimal("0"),
        description="Book value of real estate when it is included in the transaction.",
    )
    estimated_market_rent: Optional[Decimal] = Field(
        None,
        ge=Decimal("0"),
        description="Annual market rent for company-owned included or excluded premises.",
    )
    multiple_calibration_adjustment: Optional[Decimal] = Field(
        None,
        ge=Decimal("-10"),
        le=Decimal("10"),
        description="Advisor-entered specific risk/quality premium in multiple turns.",
    )
    multiple_calibration_note: Optional[str] = Field(
        None,
        max_length=1000,
        description="Required audit-trail note when multiple_calibration_adjustment is non-zero.",
    )
    advisor_id: Optional[str] = Field(
        None,
        max_length=128,
        description="Advisor identity recorded on the override audit trail (the 'who').",
    )
    override_out_of_band_confirmed: bool = Field(
        False,
        description=(
            "Explicit confirmation that an out-of-band override (far from the model, "
            "within the absolute sane range) is intentional. Required by governance "
            "before an out-of-band multiple is accepted (BET-524)."
        ),
    )
    business_type_multiple_overrides: Optional[Dict[str, Decimal]] = Field(
        None,
        description=(
            "Per-business-type INPUT multiple overrides keyed by business_type_id "
            "(advisor: 'zelf multiple kiezen per NACE-code'). Overrides the model "
            "median for that type before discounts; the model baseline is preserved "
            "and shown, and overrides never feed benchmark indexes. Requires "
            "business_type_multiple_override_note."
        ),
    )
    business_type_multiple_override_note: Optional[str] = Field(
        None,
        max_length=1000,
        description="Required audit-trail rationale when business_type_multiple_overrides is set.",
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
    historical_ebitda_weighting_mode: Optional[Literal["standard", "weighted", "current_year"]] = (
        Field(
            "standard",
            description=(
                "EBITDA basis policy: standard recency weighting, explicit advisor weights, "
                "or the current fiscal year's reported/accepted-normalized EBITDA only."
            ),
        )
    )
    historical_ebitda_weights: Optional[Dict[int, Decimal]] = Field(
        None,
        description="Advisor-entered EBITDA weights keyed by fiscal year; values may sum to 1.0 or 100.",
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

    use_monte_carlo: bool = Field(
        False,
        description=(
            "Reserved canonical uncertainty control. The deterministic stateless "
            "kernel currently rejects True rather than silently claiming that a "
            "Monte Carlo simulation was performed."
        ),
    )

    # === Additional Context ===
    number_of_employees: Optional[int] = Field(None, ge=0)
    number_of_owners: int = Field(1, ge=1, le=100)
    recurring_revenue_percentage: Decimal = Field(
        Decimal("0.0"), ge=Decimal("0.0"), le=Decimal("1.0")
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
    shares_for_sale: Optional[Decimal] = Field(
        None,
        ge=Decimal("0"),
        le=Decimal("100"),
        description="Percentage of shares for sale (0-100). Partial stakes are supported and scale equity outputs proportionally.",
    )
    owner_salary_addback: Optional[float] = Field(
        None,
        ge=0,
        description=(
            "Legacy scenario-only owner compensation scalar. A priced SDE requires an "
            "evidence-linked, reviewed normalization decision in the canonical ledger."
        ),
    )
    owner_role: Optional[str] = Field(
        None,
        pattern="^(working|passive)$",
        description=(
            "Seller's role post-close. 'working' = active operator; "
            "'passive' = non-operating shareholder (full compensation add-back)."
        ),
    )

    # === User-Configured Blended Valuation (Waarderingssynthese) ===
    user_weights: Optional[Dict[str, float]] = Field(
        None,
        description="Method-key → weight (0.0-1.0) map for blended valuation. "
        "Weights must sum to 1.0. Example: {'ebitda_multiple': 0.7, 'dcf': 0.3}",
    )
    user_weight_justification: Optional[str] = Field(
        None,
        max_length=2000,
        description="Accountant's textual rationale for the chosen weighting (printed in PDF synthesis page)",
    )
    strict_user_weights: bool = Field(
        False,
        description=(
            "When true, any unavailable positively weighted method is a calculation "
            "error; weights are never silently renormalized. Default false preserves "
            "legacy advisor-preview behavior."
        ),
    )

    # === Selected Method (canonical key) ===
    selected_method: Optional[str] = Field(
        None,
        description=(
            "Canonical method key the caller wants surfaced as the headline. "
            "When set to 'startup_valuation', the engine runs the venture path "
            "(Berkus + Scorecard + VC) and ignores historical-financial methods."
        ),
    )
    user_configured_dcf: Optional[bool] = Field(
        None,
        description=(
            "True when an advisor explicitly configured DCF inputs. This is durable "
            "DCF intent; include_dcf by itself remains only a capability flag."
        ),
    )

    # === Startup Valuation Inputs (venture / pre-revenue path) ===
    startup_inputs: Optional[StartupInputs] = Field(
        None,
        description=(
            "Founder-supplied qualitative + traction + cap-table inputs for the "
            "Startup Valuation method. Required when selected_method='startup_valuation'."
        ),
    )
    cap_table: Optional[CapTableSummary] = Field(
        None,
        description="Non-startup or shared cap-table summary used by eligible methods.",
    )
    investment_amount_sought: Optional[Decimal] = Field(
        None,
        ge=Decimal("0"),
        description="Primary capital sought, kept separate from secondary equity value.",
    )
    lifecycle_stage_triage: Optional[LifecycleStageTriage] = Field(
        None,
        description=(
            "Company-stage intelligence received beside business type. Startup-shaped "
            "or low-confidence stage candidates can block mature SME methods until "
            "founder clarification is collected."
        ),
    )

    # === Per-year valuation timeline (the value-over-years curve) ===
    include_valuation_timeline: bool = Field(
        default=False,
        description=(
            "When True, the engine additionally values EACH fiscal year present in the "
            "input (historical actuals + current + forecast) on the current market lens "
            "and returns them as `valuation_timeline`. Each sub-valuation reuses the full "
            "adaptive engine; the latest-actual-year point reconciles to the headline."
        ),
    )
    headline_value_basis: Literal["equity_value", "enterprise_value"] = Field(
        default="equity_value",
        description=(
            "Primary value basis for the report and private timeline. Enterprise-value "
            "headlines keep the EV-to-equity bridge illustrative."
        ),
    )

    @model_validator(mode="before")
    @classmethod
    def verify_signed_case_external_commitments(cls, value: object) -> object:
        """Bind a v2 case to the exact external selectors received on the wire."""

        if not isinstance(value, Mapping):
            return value
        value = dict(value)
        value["completion_account_inputs_provided"] = any(
            field in value
            for field in (
                "restricted_cash",
                "lease_liabilities",
                "debt_like_items",
                "normalized_nwc_target",
            )
        )
        raw_case = value.get("valuation_case")
        if isinstance(raw_case, BaseModel):
            raw_case = raw_case.model_dump(mode="json")
        external_market_reference_contract = value.get("external_market_reference_contract")
        wacc_evidence_contract = value.get("wacc_evidence_contract")
        real_estate_yield_evidence_contract = value.get("real_estate_yield_evidence_contract")
        if (
            external_market_reference_contract is not None
            and value.get("benchmark_contract") is not None
        ):
            raise ValueError(
                "external_market_reference_contract cannot be combined with " "benchmark_contract"
            )
        if not isinstance(raw_case, Mapping) or raw_case.get("schema_version") != (
            "valuation_case.v2"
        ):
            if external_market_reference_contract is not None:
                raise ValueError(
                    "external_market_reference_contract requires a signed valuation_case.v2"
                )
            if wacc_evidence_contract is not None:
                raise ValueError("wacc_evidence_contract requires a signed valuation_case.v2")
            if real_estate_yield_evidence_contract is not None:
                raise ValueError(
                    "real_estate_yield_evidence_contract requires a signed valuation_case.v2"
                )
            return value

        country_code = str(value.get("country_code") or "").strip().upper()
        configured_pack = country_pack(country_code)
        raw_currency = value.get("currency")
        currency = (
            str(raw_currency).strip().upper()
            if raw_currency is not None and str(raw_currency).strip()
            else configured_pack.currency if configured_pack is not None else None
        )
        from .valuation_case_security import verify_valuation_case_external_commitments

        verify_valuation_case_external_commitments(
            raw_case,
            benchmark_contract=value.get("benchmark_contract"),
            economic_context=value.get("economic_context"),
            country_pack_selector={
                "schema_version": "country_pack_selector.v1",
                "country_code": country_code,
                "currency": currency,
            },
            external_market_reference_contract=external_market_reference_contract,
            wacc_evidence_contract=wacc_evidence_contract,
            real_estate_yield_evidence_contract=real_estate_yield_evidence_contract,
        )
        return value

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
        code = normalize_country_code(value)
        if country_pack(code) is None:
            raise ValueError(f"no CountryPack configured for {code!r}")
        return code

    @field_validator("current_year")
    @classmethod
    def validate_current_year_not_in_future(cls, value: YearDataStateless) -> YearDataStateless:
        max_confirmable_year = get_max_confirmable_year()
        if value.year > max_confirmable_year:
            raise ValueError(
                f"current_year.year ({value.year}) cannot be later than the previous calendar year ({max_confirmable_year})"
            )
        return value

    @field_validator("user_weights")
    @classmethod
    def validate_user_weights(cls, value: Optional[Dict[str, float]]) -> Optional[Dict[str, float]]:
        if value is None:
            return value
        raw_keys = set(value.keys())
        bad_keys = raw_keys - USER_WEIGHT_METHOD_KEYS
        if bad_keys:
            raise ValueError(f"Unknown method key(s): {', '.join(sorted(bad_keys))}")

        normalized_weights: Dict[str, float] = {}
        raw_by_normalized: Dict[str, str] = {}
        for raw_key, weight in value.items():
            normalized_key = normalize_method_key(raw_key)
            if normalized_key not in CANONICAL_METHOD_KEYS:
                raise ValueError(f"Unknown method key(s): {raw_key}")
            previous_raw = raw_by_normalized.get(normalized_key)
            if previous_raw is not None:
                raise ValueError(f"'{previous_raw}' and '{raw_key}' are aliases — provide only one")
            raw_by_normalized[normalized_key] = raw_key
            normalized_weights[normalized_key] = weight

        non_combinable_present = NON_COMBINABLE_METHOD_KEYS & set(normalized_weights.keys())
        if non_combinable_present and len(value) > 1:
            raise ValueError(
                f"Method(s) {sorted(non_combinable_present)} run standalone and "
                "cannot be blended with other methods via user_weights."
            )
        for key, weight in normalized_weights.items():
            if not (0.0 <= weight <= 1.0):
                raise ValueError(f"Weight for '{key}' must be between 0.0 and 1.0, got {weight}")
        weight_sum = sum(normalized_weights.values())
        if abs(weight_sum - 1.0) > 0.02:
            raise ValueError(f"Weights must sum to 1.0 (±0.02 tolerance), got {weight_sum:.4f}")
        return normalized_weights

    @field_validator("selected_method", mode="before")
    @classmethod
    def normalize_selected_method(cls, value: object) -> Optional[str]:
        if value is None or (isinstance(value, str) and not value.strip()):
            return None
        normalized = normalize_selected_method_key(value)
        if normalized not in CANONICAL_METHOD_KEYS:
            supported = ", ".join(CANONICAL_METHOD_KEYS)
            raise ValueError(
                f"Unsupported selected_method '{value}'. Supported canonical methods: {supported}"
            )
        return normalized

    @field_validator("historical_ebitda_weights", mode="before")
    @classmethod
    def normalize_historical_ebitda_weights(cls, value: object) -> Optional[Dict[int, Decimal]]:
        return normalize_historical_ebitda_weights_input(value)

    @field_validator("advisor_qualifications")
    @classmethod
    def validate_advisor_qualifications(cls, value: List[str]) -> List[str]:
        normalized: list[str] = []
        for qualification in value:
            text = str(qualification).strip()
            if not text:
                raise ValueError("advisor_qualifications cannot contain blank entries")
            if len(text) > 1_000:
                raise ValueError("advisor_qualifications entries must be at most 1000 characters")
            if text not in normalized:
                normalized.append(text)
        return normalized

    @field_validator(
        "multiple_type_weights",
        "advisor_discount_weights",
        "business_type_multiple_overrides",
        mode="before",
    )
    @classmethod
    def normalize_advisor_weight_map(cls, value: object) -> Optional[Dict[str, Decimal]]:
        if value is None or value == "" or value == []:
            return None
        if not isinstance(value, dict):
            raise ValueError("advisor weight inputs must be a key-to-weight map")
        normalized: Dict[str, Decimal] = {}
        for key, weight in value.items():
            weight_dec = Decimal(str(weight))
            if weight_dec < 0:
                raise ValueError("advisor weights cannot contain negative values")
            normalized[str(key)] = weight_dec
        return normalized or None

    @model_validator(mode="after")
    def validate_startup_method_inputs(self) -> "CalculateRequest":
        """When selected_method='startup_valuation', startup_inputs is required."""
        if self.use_monte_carlo:
            raise ValueError(
                "use_monte_carlo=true is not supported by the deterministic canonical "
                "kernel; submit false until a seeded, governed simulation policy is certified"
            )
        configured_pack = country_pack(self.country_code)
        if configured_pack is None:
            raise ValueError(f"no CountryPack configured for {self.country_code!r}")
        explicitly_requested_methods = set(self.user_weights or {})
        if self.selected_method is not None:
            explicitly_requested_methods.add(self.selected_method)
        unsupported_methods = explicitly_requested_methods - set(configured_pack.supported_methods)
        if unsupported_methods:
            raise ValueError(
                f"valuation method(s) {sorted(unsupported_methods)} are not supported by "
                f"CountryPack {configured_pack.pack_version}"
            )
        if self.currency is None:
            raise ValueError("canonical valuation requires an explicit ISO-4217 currency")
        if self.currency != configured_pack.currency:
            raise ValueError(
                "request currency does not match CountryPack currency; "
                "an explicit source-dated FX conversion contract is required"
            )
        yield_contract = self.real_estate_yield_evidence_contract
        if self.selected_method == "real_estate_yield" and yield_contract is None:
            raise ValueError(
                "selected_method='real_estate_yield' requires a signed, governed "
                "real_estate_yield_evidence_contract"
            )
        if yield_contract is not None:
            if self.selected_method != "real_estate_yield":
                raise ValueError(
                    "real_estate_yield_evidence_contract is priced only by the explicitly "
                    "selected standalone real_estate_yield method"
                )
            if self.valuation_case is None or self.valuation_case.schema_version != (
                "valuation_case.v2"
            ):
                raise ValueError(
                    "canonical real-estate yield requires signed valuation_case.v2 authority"
                )
            if yield_contract.company_id != self.valuation_case.company_id:
                raise ValueError("property evidence company_id must match valuation case")
            if yield_contract.evidence_revision_id != self.valuation_case.evidence_revision_id:
                raise ValueError("property evidence revision must match the current valuation case")
            if yield_contract.country_code != self.country_code:
                raise ValueError("property evidence country must match the request CountryPack")
            if yield_contract.currency != self.currency:
                raise ValueError("property evidence currency must match request currency")
            if yield_contract.valuation_date > date.today():
                raise ValueError("property evidence valuation date cannot be in the future")
            if (
                yield_contract.valuation_date - yield_contract.yield_observed_on
            ).days > configured_pack.benchmark_freshness_days:
                raise ValueError(
                    "property yield snapshot exceeds the CountryPack benchmark freshness limit"
                )
        if self.business_type_calibration.calibration_quality_score is not None:
            # A free-standing score could otherwise change the DCF/market mix
            # without the benchmark evidence that allegedly supports it.
            from src.services.reports.stateless_benchmark_policy import (
                as_mapping,
                benchmark_contract_is_resolved,
                missing_required_benchmark_provenance,
            )

            quality_contract = as_mapping(
                self.benchmark_contract or self.business_type_calibration.benchmark_contract
            )
            if not (
                quality_contract
                and benchmark_contract_is_resolved(quality_contract)
                and not missing_required_benchmark_provenance(quality_contract)
            ):
                raise ValueError(
                    "calibration_quality_score requires the same request to carry a "
                    "resolved benchmark contract with complete provenance"
                )
        if normalize_country_code(self.economic_context.country_code) != self.country_code:
            raise ValueError("economic_context.country_code must match request country_code")
        if self.methodology == "DCF" and not self.include_dcf:
            raise ValueError("methodology='DCF' requires include_dcf=true")
        if self.methodology == "MULTIPLES" and not self.include_multiples:
            raise ValueError("methodology='MULTIPLES' requires include_multiples=true")
        if (
            self.methodology == "HYBRID"
            and not self.include_dcf
            and not self.include_multiples
            and self.selected_method not in {"startup_valuation", "real_estate_yield"}
        ):
            raise ValueError("HYBRID requires at least one of include_dcf/include_multiples")
        _require_startup_inputs(self)
        _require_included_real_estate_values(self)
        _require_advisor_override_notes(self)
        _validate_historical_ebitda_weighting(self)
        _normalize_request_business_type_mix(self)
        priced_states = {"accepted", "approved", "applied", "confirmed", "verified", "edited"}
        for adjustment in self.normalizations:
            if (
                str(adjustment.status).strip().lower() in priced_states
                and adjustment.currency is not None
                and adjustment.currency != self.currency
            ):
                raise ValueError(
                    "accepted normalization currency must match request currency; "
                    "submit an explicit converted amount and matching currency"
                )
        if self.valuation_case is not None:
            for decision in self.valuation_case.authoritative_input_decisions:
                if (
                    decision.state in {"accepted", "edited"}
                    and decision.currency is not None
                    and decision.currency != self.currency
                ):
                    raise ValueError(
                        "accepted valuation decision currency must match request currency; "
                        "submit an explicit converted amount and matching currency"
                    )
        if self.recovery_inputs is not None:
            case = self.valuation_case
            if case is None or case.schema_version != "valuation_case.v2":
                raise ValueError("recovery inputs require a signed valuation_case.v2")
            if case.recovery_inputs_snapshot is None:
                raise ValueError("signed valuation_case.v2 must commit the recovery input snapshot")
            from .valuation_case_security import valuation_case_sha256

            recovery_payload = self.recovery_inputs.model_dump(mode="json")
            committed_recovery_payload = RecoveryInputs.model_validate(
                case.recovery_inputs_snapshot
            ).model_dump(mode="json")
            if valuation_case_sha256(recovery_payload) != valuation_case_sha256(
                committed_recovery_payload
            ):
                raise ValueError("recovery inputs do not match the signed valuation-case snapshot")
            if self.recovery_inputs.verification_receipt is not None:
                receipt_payload = self.recovery_inputs.verification_receipt.model_dump(mode="json")
                committed_receipt_payload = (
                    RecoveryVerificationReceipt.model_validate(
                        case.recovery_verification_receipt
                    ).model_dump(mode="json")
                    if case.recovery_verification_receipt is not None
                    else None
                )
                if committed_receipt_payload is None or valuation_case_sha256(
                    receipt_payload
                ) != valuation_case_sha256(committed_receipt_payload):
                    raise ValueError(
                        "recovery verification receipt does not match the signed valuation case"
                    )
        validate_priced_accounting_evidence_request(self)
        if self.allow_untrusted_multiples_fallback and not _has_text(
            self.untrusted_multiples_fallback_reason
        ):
            raise ValueError(
                "untrusted_multiples_fallback_reason is required when "
                "allow_untrusted_multiples_fallback=true"
            )
        if self.disclosed_external_market_reference is not None:
            if not self.allow_untrusted_multiples_fallback:
                raise ValueError(
                    "disclosed_external_market_reference requires "
                    "allow_untrusted_multiples_fallback=true"
                )
            if self.business_type_calibration.calibration_source != (
                "DISCLOSED_EXTERNAL_MARKET_FALLBACK"
            ):
                raise ValueError(
                    "disclosed_external_market_reference is only valid for "
                    "DISCLOSED_EXTERNAL_MARKET_FALLBACK calibration"
                )
            if (
                self.business_type_calibration.ev_ebitda_p10 is not None
                or self.business_type_calibration.ev_ebitda_p25 is not None
                or self.business_type_calibration.ev_ebitda_p75 is not None
                or self.business_type_calibration.ev_ebitda_p90 is not None
            ):
                raise ValueError(
                    "disclosed_external_market_reference cannot be combined with "
                    "claimed empirical EV/EBITDA percentiles"
                )
            if (
                self.business_type_calibration.ev_ebitda_median
                != self.disclosed_external_market_reference.applied_multiple
            ):
                raise ValueError(
                    "business_type_calibration.ev_ebitda_median must equal the "
                    "disclosed external reference applied_multiple"
                )
        if self.external_market_reference_contract is not None:
            contract = self.external_market_reference_contract
            if self.allow_untrusted_multiples_fallback:
                raise ValueError(
                    "external_market_reference_contract cannot be combined with "
                    "allow_untrusted_multiples_fallback=true"
                )
            if self.disclosed_external_market_reference is not None:
                raise ValueError(
                    "external_market_reference_contract cannot be combined with "
                    "disclosed_external_market_reference"
                )
            if self.business_type_calibration.calibration_source != (
                "GOVERNED_EXTERNAL_MARKET_REFERENCE"
            ):
                raise ValueError(
                    "external_market_reference_contract requires "
                    "GOVERNED_EXTERNAL_MARKET_REFERENCE calibration"
                )
            if contract.country_code != self.country_code:
                raise ValueError("external market reference country_code must match request")
            if contract.business_type_id != self.business_type_calibration.business_type_id:
                raise ValueError(
                    "external market reference business_type_id must match calibration"
                )
            if any(
                value is not None
                for value in (
                    self.business_type_calibration.ev_ebitda_p10,
                    self.business_type_calibration.ev_ebitda_p25,
                    self.business_type_calibration.ev_ebitda_p75,
                    self.business_type_calibration.ev_ebitda_p90,
                    self.business_type_calibration.sample_size,
                )
            ):
                raise ValueError(
                    "external_market_reference_contract cannot claim empirical "
                    "percentiles or sample size"
                )
            if self.business_type_calibration.ev_ebitda_median != contract.applied_multiple:
                raise ValueError(
                    "business_type_calibration.ev_ebitda_median must equal the "
                    "external market reference applied_multiple"
                )
        if self.wacc_evidence_contract is not None:
            contract = self.wacc_evidence_contract
            context = self.business_context if isinstance(self.business_context, dict) else {}
            raw_wacc = context.get("dcf_wacc_pct")
            if raw_wacc is None:
                raise ValueError("wacc_evidence_contract requires business_context.dcf_wacc_pct")
            declared_wacc = declared_percentage(context, "dcf_wacc_pct")
            if declared_wacc is not None:
                supplied_wacc_pct = declared_wacc * 100
            else:
                try:
                    supplied_wacc = Decimal(str(raw_wacc).strip().rstrip("%"))
                except (InvalidOperation, ValueError, TypeError) as exc:
                    raise ValueError("business_context.dcf_wacc_pct must be numeric") from exc
                supplied_wacc_pct = (
                    supplied_wacc * Decimal("100")
                    if abs(supplied_wacc) <= Decimal("1")
                    else supplied_wacc
                )
            if supplied_wacc_pct != contract.value_pct:
                raise ValueError(
                    "business_context.dcf_wacc_pct must equal " "wacc_evidence_contract.value_pct"
                )
            if context.get("dcf_size_premium_pct") is not None:
                raise ValueError(
                    "direct sector WACC already includes size premium; "
                    "dcf_size_premium_pct would double count it"
                )
        if (
            self.restricted_cash is not None
            and self.current_year.cash is not None
            and self.restricted_cash > self.current_year.cash
        ):
            raise ValueError("restricted_cash cannot exceed reported current-year cash")
        return self

    @field_validator("business_context")
    @classmethod
    def validate_percentage_contract(cls, value):
        return validate_context_percentage_units(value)

    @model_validator(mode="after")
    def validate_distinct_actual_periods(self) -> "CalculateRequest":
        """Conflicting revisions need explicit resolution, never last-row wins."""
        observations: dict[int, YearDataStateless] = {}
        for row in [*self.historical_years, self.current_year]:
            if row.is_forecast:
                continue
            existing = observations.get(row.year)
            if existing is not None and existing.model_dump() != row.model_dump():
                raise ValueError(
                    f"conflicting actual financial observations for fiscal year {row.year}"
                )
            observations[row.year] = row
        return self

    @model_validator(mode="after")
    def validate_dcf_is_ready(self) -> "CalculateRequest":
        historical_rows = [row for row in self.historical_years if not row.is_forecast]
        forecast_rows = [row for row in self.historical_years if row.is_forecast]
        explicitly_requested = explicitly_requests_dcf(self)
        readiness = resolve_dcf_readiness(
            current_year_data=self.current_year,
            historical_rows=historical_rows,
            forecast_rows=forecast_rows,
            dcf_input_mode=self.dcf_input_mode,
        )
        if explicitly_requested:
            require_dcf_readiness(readiness)
        elif self.include_dcf and not readiness.ready:
            self.include_dcf = False
        return self
