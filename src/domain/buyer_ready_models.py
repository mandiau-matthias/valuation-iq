"""Buyer-Ready Package render-input models (BET-241 / F1).

These models describe the **render-time payload** that Titan posts to
ValuationIQ when invoking the buyer-ready package renderer. They mirror
the locked output schema from the F1 spec at
`docs/product/features/active-development/buyer-ready-package.md` §9.

Why Pydantic and not a plain dict:
    - Wire-shape drift between Titan and ValuationIQ is a real risk;
      Pydantic enforces it at parse time.
    - The renderer can branch on typed fields (`confidence`, `status`,
      `state`) without `dict.get()` ceremony.
    - JSON-schema generation gives us a defensible contract artefact
      for the F2-F6 implementation tickets.

Architectural pin (BET-247 directive, 2026-05-16):
    The buyer-ready package is the first concrete instance of the
    "Readiness Case" atomic object. This module describes ONLY the
    render-time wire shape — the durable workflow entity (Prisma
    model, state machine, task assignments) is sprint+2 work owned
    by Titan, NOT this module.

Reuse manifest (F1 spec §12):
    Every numeric field carries a `provenance` ID pointing back to the
    upstream primitive that produced it. F2-F6 PR review enforces that
    no field is invented at render time; every value traces to
    TitanYearData / OwnerProfile / SellabilityScore / ValuationReport /
    Delphi.
"""

from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .buyer_ready_types import (
    EXPECTED_IM_SECTION_ORDER,
    BuyerReadyAssistantSurface,
    BuyerReadyBridgeBeliefStatus,
    BuyerReadyBridgeEvidenceStatus,
    BuyerReadyChecklistCategory,
    BuyerReadyChecklistStatus,
    BuyerReadyConfidence,
    BuyerReadyCustomContentProvider,
    BuyerReadyCustomContentStatus,
    BuyerReadyDealStructure,
    BuyerReadyIMSectionKey,
    BuyerReadyIntegrationInputStatus,
    BuyerReadyLegalChecklistCategory,
    BuyerReadyLegalReadinessStatus,
    BuyerReadyPackageAccessGate,
    BuyerReadyPackageArtifactStatus,
    BuyerReadyPackageArtifactType,
    BuyerReadyPricingBasis,
    BuyerReadyReleaseStatus,
    TaxLatencyJurisdiction,
    TaxLatencyRuleID,
)
from .buyer_ready_validation import (
    bridge_buyer_belief_status,
    bridge_confidence_reason,
    bridge_step_warning,
    classify_bridge_step_evidence,
    confidence_floor,
    validate_legal_readiness_counts,
    validate_package_artifact_controlled_source_refs,
    validate_package_manifest_count_and_pdf_status,
    validate_package_manifest_payload_consistency,
)

# ---------------------------------------------------------------------
# Provenance + brand
# ---------------------------------------------------------------------


class BuyerReadyBaseModel(BaseModel):
    """Strict base model for the Titan -> ValuationIQ render contract."""

    model_config = ConfigDict(extra="forbid")


class ProvenanceRef(BuyerReadyBaseModel):
    """Points a rendered value back to its upstream primitive.

    Reuse-manifest enforcement: every numeric field on every render
    payload carries one of these. F2-F6 PR review rejects any field
    without one.
    """

    source: Literal[
        "titan_year_data",
        "owner_profile",
        "sellability_score",
        "valuation_report",
        "delphi_benchmark",
        "listing_data",
        "advisor_input",
        "ledger_signal",
        "computed",
    ]
    source_id: Optional[str] = None
    computed_at: Optional[str] = None  # ISO-8601


class AdvisorBrandRender(BuyerReadyBaseModel):
    """White-label inputs from advisor (F3 co-brand layer)."""

    firm_name: str
    logo_url: Optional[str] = None
    primary_hex: str = Field(..., pattern=r"^#[0-9A-Fa-f]{6}$")
    secondary_hex: Optional[str] = Field(None, pattern=r"^#[0-9A-Fa-f]{6}$")
    footer_text: Optional[str] = None


# ---------------------------------------------------------------------
# IM section payloads (F3)
# ---------------------------------------------------------------------


class CoverRender(BuyerReadyBaseModel):
    """IM cover page."""

    anonymised_title: str
    sector_label: str
    region_label: str
    country_code: Literal["BE", "NL"]
    asking_price_band: Optional[str] = None  # e.g. "€2M–€5M"
    sellability_score: Optional[int] = Field(None, ge=0, le=100)
    sellability_band_label: Optional[str] = None
    generated_at: str  # ISO-8601


class PriceRecommendationRender(BuyerReadyBaseModel):
    """Valuation-to-price bridge for the package cover and deal terms.

    This is not a signed transaction price. It pins the equity-value midpoint,
    valuation range, and optional advisor asking-price target to the valuation
    report provenance so the IM cannot drift from the main report.
    """

    currency: str = Field("EUR", min_length=3, max_length=3)
    equity_value_low_eur: int = Field(..., ge=0)
    equity_value_mid_eur: int = Field(..., ge=0)
    equity_value_high_eur: int = Field(..., ge=0)
    recommended_asking_price_eur: Optional[int] = Field(None, ge=0)
    display_band: Optional[str] = None
    basis: BuyerReadyPricingBasis
    confidence: BuyerReadyConfidence
    price_basis_note: str
    provenance: List[ProvenanceRef] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_value_band(self) -> "PriceRecommendationRender":
        if self.equity_value_low_eur > self.equity_value_mid_eur:
            raise ValueError("pricing.equity_value_low_eur must be <= equity_value_mid_eur")
        if self.equity_value_mid_eur > self.equity_value_high_eur:
            raise ValueError("pricing.equity_value_mid_eur must be <= equity_value_high_eur")
        if self.recommended_asking_price_eur is not None and (
            self.recommended_asking_price_eur < self.equity_value_low_eur
            or self.recommended_asking_price_eur > self.equity_value_high_eur
        ):
            raise ValueError(
                "pricing.recommended_asking_price_eur must sit within equity value range"
            )
        if self.basis in {
            "valuation_report",
            "valuation_report_with_advisor_buffer",
        } and not any(ref.source == "valuation_report" for ref in self.provenance):
            raise ValueError(
                "pricing provenance must include valuation_report for valuation-report basis"
            )
        return self


class ExecutiveSummaryRender(BuyerReadyBaseModel):
    """1-page executive summary (F3 LLM narrative target)."""

    one_paragraph_pitch: str
    headline_financials: str  # "€2.1M revenue, €420k normalised EBITDA, 20% margin"
    transaction_rationale: str
    key_strengths: List[str]  # 3-5 items
    summary_risks: List[str]  # 3-5 items
    confidence: BuyerReadyConfidence
    provenance: List[ProvenanceRef] = Field(default_factory=list)


class IMSectionRender(BuyerReadyBaseModel):
    """Generic IM section payload. F3 fills one per section_key.

    The LLM narrative goes in `narrative_paragraphs`; structured data
    referenced by the narrative goes in `key_figures` (rendered as a
    side-panel or callout). Confidence drives whether the narrative
    renders or a placeholder shows.
    """

    section_key: BuyerReadyIMSectionKey
    heading: str
    narrative_paragraphs: List[str] = Field(default_factory=list)
    key_figures: List["KeyFigureRender"] = Field(default_factory=list)
    confidence: BuyerReadyConfidence
    provenance: List[ProvenanceRef] = Field(default_factory=list)


class KeyFigureRender(BuyerReadyBaseModel):
    """One labelled value inside an IM section."""

    label: str
    value: str  # already-formatted, locale-aware
    note: Optional[str] = None  # tooltip / footnote
    provenance: ProvenanceRef


# ---------------------------------------------------------------------
# D2 — Buyer FAQ
# ---------------------------------------------------------------------


class BuyerFAQItemRender(BuyerReadyBaseModel):
    """One question + answer in the buyer FAQ doc."""

    question: str
    answer: str
    answer_source: Literal["owner_prompt", "autofilled", "placeholder"]


class BuyerFAQRender(BuyerReadyBaseModel):
    """F4 deliverable."""

    autofilled_items: List[BuyerFAQItemRender]  # autofill from shipped primitives
    owner_prompt_items: List[BuyerFAQItemRender]  # 8 owner-answered prompts
    completion_pct: int = Field(..., ge=0, le=100)

    @model_validator(mode="after")
    def validate_item_counts_and_completion(self) -> "BuyerFAQRender":
        if len(self.autofilled_items) != 7:
            raise ValueError("buyer_faq.autofilled_items must contain exactly 7 items")
        if len(self.owner_prompt_items) != 8:
            raise ValueError("buyer_faq.owner_prompt_items must contain exactly 8 items")

        all_items = [*self.autofilled_items, *self.owner_prompt_items]
        answered_count = sum(1 for item in all_items if item.answer_source != "placeholder")
        expected_completion = round((answered_count / len(all_items)) * 100)
        if self.completion_pct != expected_completion:
            raise ValueError("buyer_faq.completion_pct must match non-placeholder answer count")
        return self


# ---------------------------------------------------------------------
# D3 — Missing-doc checklist
# ---------------------------------------------------------------------


class MissingDocChecklistItemRender(BuyerReadyBaseModel):
    """One category R/Y/G line."""

    category: BuyerReadyChecklistCategory
    status: BuyerReadyChecklistStatus
    reason: str  # plain-language explanation for the chosen status
    advisor_override: bool = False
    last_updated: str  # ISO-8601


class MissingDocChecklistRender(BuyerReadyBaseModel):
    """F2 deliverable."""

    items: List[MissingDocChecklistItemRender]
    overall_status: BuyerReadyChecklistStatus
    green_count: int
    yellow_count: int
    red_count: int

    @model_validator(mode="after")
    def validate_status_counts(self) -> "MissingDocChecklistRender":
        expected = {
            "green": sum(1 for item in self.items if item.status == "green"),
            "yellow": sum(1 for item in self.items if item.status == "yellow"),
            "red": sum(1 for item in self.items if item.status == "red"),
        }
        if self.green_count != expected["green"]:
            raise ValueError("missing_doc_checklist.green_count does not match green items")
        if self.yellow_count != expected["yellow"]:
            raise ValueError("missing_doc_checklist.yellow_count does not match yellow items")
        if self.red_count != expected["red"]:
            raise ValueError("missing_doc_checklist.red_count does not match red items")
        return self


# ---------------------------------------------------------------------
# D4 — Normalised EBITDA bridge
# ---------------------------------------------------------------------


class EBITDABridgeEvidenceRender(BuyerReadyBaseModel):
    """Citation-ready source backing one bridge step.

    Hermes classifies the evidence, Titan resolves document/source IDs, and
    ValuationIQ renders buyer-belief checks without re-computing valuation math.
    """

    document_id: Optional[str] = None
    source_category: str
    source_ref: Optional[str] = None
    line_item: Optional[str] = None
    source_fact: str
    confidence: float = Field(..., ge=0, le=1)
    amount_eur: Optional[int] = None


class EBITDABridgeStepRender(BuyerReadyBaseModel):
    """One waterfall step in the bridge.

    Each step carries its own confidence + provenance (F1 spec §8 ladder).
    Total chain confidence = floor() of step confidences.
    """

    label: str
    delta_eur: int  # signed; positive = add-back, negative = haircut
    step_confidence: BuyerReadyConfidence
    rationale: str  # one-liner explanation
    provenance: ProvenanceRef
    evidence_refs: List[EBITDABridgeEvidenceRender] = Field(default_factory=list)
    confidence_reason: Optional[str] = None
    evidence_status: BuyerReadyBridgeEvidenceStatus = "unsupported"
    buyer_belief_status: BuyerReadyBridgeBeliefStatus = "not_buyer_ready"
    buyer_belief_warning: Optional[str] = None

    @model_validator(mode="after")
    def derive_buyer_belief_status(self) -> "EBITDABridgeStepRender":
        status = classify_bridge_step_evidence(
            delta_eur=self.delta_eur,
            step_confidence=self.step_confidence,
            evidence_refs=self.evidence_refs,
        )
        self.evidence_status = status
        self.buyer_belief_status = (
            "buyer_believable"
            if status == "documented"
            else "advisor_review" if status == "weak_evidence" else "not_buyer_ready"
        )
        if not self.confidence_reason:
            self.confidence_reason = bridge_confidence_reason(status, self.evidence_refs)
        self.buyer_belief_warning = bridge_step_warning(status, delta_eur=self.delta_eur)
        return self


class EBITDABridgeRender(BuyerReadyBaseModel):
    """F3 sub-deliverable, reuses ebitda_normalization.html math.

    The chain reads: reported_ebitda → step1 → step2 → ... → normalised.
    Aggregate confidence is the min across step_confidences.
    """

    reported_ebitda_eur: int
    steps: List[EBITDABridgeStepRender]
    normalised_ebitda_eur: int
    aggregate_confidence: BuyerReadyConfidence
    buyer_belief_status: BuyerReadyBridgeBeliefStatus = "buyer_believable"
    weak_evidence_step_count: int = 0
    unsupported_step_count: int = 0
    buyer_belief_summary: Optional[str] = None

    @model_validator(mode="after")
    def derive_bridge_buyer_belief_status(self) -> "EBITDABridgeRender":
        derived_confidence = confidence_floor([step.step_confidence for step in self.steps])
        self.aggregate_confidence = derived_confidence
        self.weak_evidence_step_count = sum(
            1 for step in self.steps if step.evidence_status == "weak_evidence"
        )
        self.unsupported_step_count = sum(
            1 for step in self.steps if step.evidence_status == "unsupported"
        )
        self.buyer_belief_status = bridge_buyer_belief_status(
            unsupported_step_count=self.unsupported_step_count,
            weak_evidence_step_count=self.weak_evidence_step_count,
            derived_confidence=derived_confidence,
        )
        if self.buyer_belief_status == "not_buyer_ready":
            self.buyer_belief_summary = (
                f"{self.unsupported_step_count} bridge step"
                f"{'s' if self.unsupported_step_count != 1 else ''} lack buyer-verifiable "
                "evidence."
            )
        elif self.buyer_belief_status == "advisor_review":
            self.buyer_belief_summary = (
                f"{self.weak_evidence_step_count} bridge step"
                f"{'s' if self.weak_evidence_step_count != 1 else ''} need stronger "
                "evidence before buyer release."
            )
        else:
            self.buyer_belief_summary = (
                "All normalisation steps have citation-ready buyer-verifiable evidence."
            )
        return self


# ---------------------------------------------------------------------
# D5 — Working-capital peg
# ---------------------------------------------------------------------


class WCPegMonthlyPointRender(BuyerReadyBaseModel):
    """One monthly point on the WC seasonality chart."""

    month: str  # "2025-01"
    nwc_eur: int


class WCPegRender(BuyerReadyBaseModel):
    """F5 Part A deliverable."""

    target_eur: int
    band_low_eur: int  # target × 0.9
    band_high_eur: int  # target × 1.1
    one_liner: str  # narrative explanation
    monthly_series: List[WCPegMonthlyPointRender]
    derived_from: Literal["monthly_ledger_signals", "annual_fallback"]
    confidence: BuyerReadyConfidence
    advisor_override_value: Optional[int] = None
    advisor_override_reason: Optional[str] = None
    provenance: ProvenanceRef


# ---------------------------------------------------------------------
# D5 — Tax-latency flagger
# ---------------------------------------------------------------------


class TaxLatencyFlagRender(BuyerReadyBaseModel):
    """One triggered tax-latency rule."""

    rule_id: TaxLatencyRuleID
    jurisdiction: TaxLatencyJurisdiction
    label: str
    rationale: str  # what triggered it
    estimated_impact_eur: Optional[int] = None  # signed; None when not estimable
    severity: Literal["info", "warning", "critical"]
    provenance: ProvenanceRef


class TaxLatencyRender(BuyerReadyBaseModel):
    """F5 Part B deliverable."""

    jurisdiction: TaxLatencyJurisdiction
    flags: List[TaxLatencyFlagRender]
    flag_count: int

    @model_validator(mode="after")
    def validate_flag_count_and_jurisdiction(self) -> "TaxLatencyRender":
        if self.flag_count != len(self.flags):
            raise ValueError("tax_latency.flag_count must match flags length")
        if any(flag.jurisdiction != self.jurisdiction for flag in self.flags):
            raise ValueError("tax_latency flag jurisdiction must match package jurisdiction")
        return self


# ---------------------------------------------------------------------
# Legal readiness handoff (pre-Legora, pre-counsel drafting)
# ---------------------------------------------------------------------


class LegalReadinessItemRender(BuyerReadyBaseModel):
    """One legal-readiness line for counsel / advisor handoff.

    The renderer may summarize readiness, but it does not draft, redline, or
    compare NDAs, LOIs, SPAs, SHAs, or closing obligations.
    """

    category: BuyerReadyLegalChecklistCategory
    status: BuyerReadyLegalReadinessStatus
    title: str
    reason: str
    owner: Literal["advisor", "seller", "buyer", "lawyer", "accountant"]
    required_before: Literal["teaser_release", "nda_release", "loi", "spa", "closing"]
    evidence_ref: Optional[str] = None


class LegalReadinessRender(BuyerReadyBaseModel):
    """Lawyer-handoff guardrail for the transaction-ready package.

    This is the line between Upswitch and Harvey/Legora territory: we prepare
    the facts, gates, and issue list; counsel owns legal advice and drafting.
    """

    jurisdiction: TaxLatencyJurisdiction
    deal_structure: BuyerReadyDealStructure
    buyer_release_status: BuyerReadyReleaseStatus
    counsel_review_required: bool = True
    items: List[LegalReadinessItemRender]
    clear_count: int
    review_count: int
    blocked_count: int
    confidentiality_gate: str = (
        "Release buyer-identifying, customer, employee, contract, and personal "
        "data only through the NDA-gated data room."
    )
    legal_disclaimer: str = (
        "Prepared as a transaction-readiness aid for advisors and qualified "
        "buyers. It is not legal advice, not a securities offering document, "
        "and not a substitute for review by transaction counsel."
    )

    @model_validator(mode="after")
    def validate_legal_readiness_counts(self) -> "LegalReadinessRender":
        validate_legal_readiness_counts(self)
        return self


# ---------------------------------------------------------------------
# Buyer package manifest / controlled transaction envelope
# ---------------------------------------------------------------------


class BuyerPackageArtifactRender(BuyerReadyBaseModel):
    """One controlled artifact in the SME buyer-ready transaction package."""

    artifact_type: BuyerReadyPackageArtifactType
    title: str
    status: BuyerReadyPackageArtifactStatus
    access_gate: BuyerReadyPackageAccessGate
    owner: Literal["titan", "valuationiq", "advisor", "seller", "lawyer", "buyer"]
    reason: str
    source_ref: Optional[str] = None
    issued_at: Optional[str] = None
    expires_at: Optional[str] = None
    custom_content_provider: Optional[BuyerReadyCustomContentProvider] = None
    custom_content_status: Optional[BuyerReadyCustomContentStatus] = None
    assistant_surfaces: List[BuyerReadyAssistantSurface] = Field(default_factory=list)
    integration_input_status: Optional[BuyerReadyIntegrationInputStatus] = None
    open_input_count: Optional[int] = Field(default=None, ge=0)
    assistant_next_action: Optional[str] = None

    @model_validator(mode="after")
    def validate_controlled_source_refs(self) -> "BuyerPackageArtifactRender":
        validate_package_artifact_controlled_source_refs(self)
        return self


class BuyerPackageManifestRender(BuyerReadyBaseModel):
    """Index tying the IM, DD checklist, valuation report/PDF, and release gates together."""

    package_status: BuyerReadyPackageArtifactStatus
    release_status: BuyerReadyReleaseStatus
    included_artifact_count: int
    valuation_report_id: Optional[str] = None
    valuation_pdf_status: BuyerReadyPackageArtifactStatus = "missing"
    artifacts: List[BuyerPackageArtifactRender]

    @model_validator(mode="after")
    def validate_manifest_count_and_pdf_status(self) -> "BuyerPackageManifestRender":
        validate_package_manifest_count_and_pdf_status(self)
        return self


# ---------------------------------------------------------------------
# D6 — Data-room manifest (rendered into IM appendix)
# ---------------------------------------------------------------------


class DataRoomDocSummaryRender(BuyerReadyBaseModel):
    """One document line in the manifest."""

    filename: str
    category: BuyerReadyChecklistCategory
    version: int
    uploaded_at: str  # ISO-8601
    access_gate: Literal["public_teaser", "after_nda"]


class DataRoomManifestRender(BuyerReadyBaseModel):
    """F6 summary projection for the IM appendix (the vault UI lives in Mercury)."""

    doc_count: int
    nda_signed_buyer_count: int
    docs_by_category: List[DataRoomDocSummaryRender]

    @model_validator(mode="after")
    def validate_doc_count(self) -> "DataRoomManifestRender":
        if self.doc_count != len(self.docs_by_category):
            raise ValueError("data_room_manifest.doc_count must match docs_by_category length")
        return self


# ---------------------------------------------------------------------
# Engine signals (footer + audit)
# ---------------------------------------------------------------------


class BuyerReadyEngineSignalsRender(BuyerReadyBaseModel):
    """Engineering metadata for the package footer + audit log."""

    package_version: str = "1.0"
    titan_year_data_id: Optional[str] = None
    owner_profile_id: Optional[str] = None
    latest_sellability_id: Optional[str] = None
    latest_valuation_report_id: Optional[str] = None
    llm_provider: Optional[Literal["claude_opus_4_7", "claude_sonnet_4_6"]] = None
    llm_sections_with_narrative: int = Field(0, ge=0, le=3)
    llm_sections_placeholder: int = Field(0, ge=0, le=3)  # confidence < 'medium' → placeholder
    delphi_benchmark_id: Optional[str] = None

    @model_validator(mode="after")
    def validate_llm_section_counts(self) -> "BuyerReadyEngineSignalsRender":
        if self.llm_sections_with_narrative + self.llm_sections_placeholder > 3:
            raise ValueError("LLM section counts cannot exceed the 3 LLM-target IM sections")
        return self


# ---------------------------------------------------------------------
# Deal-readiness advisory (BET-231/232/233, surfaced via BET-378)
# ---------------------------------------------------------------------


class DealReadinessRevenueQualityRender(BuyerReadyBaseModel):
    """Revenue-quality snapshot — data-derived, advisory only."""

    classification: str
    quality_score: Optional[float] = None
    band: str
    cagr_pct: Optional[float] = None
    growth_volatility_pct: Optional[float] = None
    max_drawdown_pct: Optional[float] = None


class DealReadinessValuationDiscountRender(BuyerReadyBaseModel):
    """Indicative concentration discount band (advisory; ValuationIQ owns price)."""

    low_pct: float
    high_pct: float


class DealReadinessCustomerConcentrationRender(BuyerReadyBaseModel):
    """Top-customer concentration snapshot."""

    band: str
    rag: str
    top3_customer_revenue_pct: Optional[float] = None
    indicative_valuation_discount: Optional[DealReadinessValuationDiscountRender] = None
    source: str


class DealReadinessRecommendationRender(BuyerReadyBaseModel):
    """One advisory deal-structuring recommendation."""

    id: str
    category: str
    title: str
    rationale: str
    priority: str
    drivers: List[str]


class DealReadinessDealStructureRender(BuyerReadyBaseModel):
    """Deal-structure readiness (key-person risk + recommendations)."""

    key_person_risk: str
    summary: str
    recommendations: List[DealReadinessRecommendationRender]


class DealReadinessRender(BuyerReadyBaseModel):
    """Data-derived deal-readiness advisory.

    Snake-cased projection of Titan's ``BuyerReadinessPackage.dealReadiness``
    (BET-231/232/233 → BET-378). Advisory only — ValuationIQ still owns the
    price; the renderer summarises the signals and never invents one. Mirrors
    the Titan contract exactly so wire drift fails fast at parse time.
    """

    transaction_risk_band: Optional[Literal["low", "moderate", "elevated", "high"]] = None
    revenue_quality: Optional[DealReadinessRevenueQualityRender] = None
    customer_concentration: Optional[DealReadinessCustomerConcentrationRender] = None
    deal_structure: Optional[DealReadinessDealStructureRender] = None
    recommendation_count: int

    @model_validator(mode="after")
    def validate_recommendation_count(self) -> "DealReadinessRender":
        surfaced = len(self.deal_structure.recommendations) if self.deal_structure else 0
        if self.recommendation_count < surfaced:
            raise ValueError(
                "deal_readiness.recommendation_count cannot be less than surfaced recommendations"
            )
        return self


# ---------------------------------------------------------------------
# Top-level package payload
# ---------------------------------------------------------------------


class BuyerReadyPackageRender(BuyerReadyBaseModel):
    """The full render-time payload Titan posts to ValuationIQ.

    Drift between Titan and ValuationIQ is a contract violation caught
    here at parse time. Renderer never invents a field; renderer fails
    fast if the payload is malformed.
    """

    package_id: str
    entity_id: str
    generated_at: str  # ISO-8601
    advisor_brand: Optional[AdvisorBrandRender] = None
    cover: CoverRender
    pricing: Optional[PriceRecommendationRender] = None
    buyer_package_manifest: Optional[BuyerPackageManifestRender] = None
    executive_summary: ExecutiveSummaryRender
    im_sections: List[IMSectionRender]
    buyer_faq: BuyerFAQRender
    missing_doc_checklist: MissingDocChecklistRender
    ebitda_bridge: EBITDABridgeRender
    wc_peg: Optional[WCPegRender] = None
    tax_latency: TaxLatencyRender
    legal_readiness: Optional[LegalReadinessRender] = None
    data_room_manifest: Optional[DataRoomManifestRender] = None
    deal_readiness: Optional[DealReadinessRender] = None
    engine_signals: BuyerReadyEngineSignalsRender

    @model_validator(mode="after")
    def validate_im_section_order(self) -> "BuyerReadyPackageRender":
        section_keys = [section.section_key for section in self.im_sections]
        if section_keys != EXPECTED_IM_SECTION_ORDER:
            raise ValueError("im_sections must contain the locked 15-section IM order")
        return self

    @model_validator(mode="after")
    def validate_manifest_payload_consistency(self) -> "BuyerReadyPackageRender":
        validate_package_manifest_payload_consistency(self)
        return self


# Resolve forward references for IMSectionRender → KeyFigureRender
IMSectionRender.model_rebuild()


__all__ = [
    "AdvisorBrandRender",
    "BuyerFAQItemRender",
    "BuyerFAQRender",
    "BuyerReadyAssistantSurface",
    "BuyerReadyChecklistCategory",
    "BuyerReadyChecklistStatus",
    "BuyerReadyConfidence",
    "BuyerReadyCustomContentProvider",
    "BuyerReadyCustomContentStatus",
    "BuyerReadyDealStructure",
    "BuyerReadyEngineSignalsRender",
    "BuyerReadyIMSectionKey",
    "BuyerReadyIntegrationInputStatus",
    "BuyerReadyLegalChecklistCategory",
    "BuyerReadyLegalReadinessStatus",
    "BuyerReadyPackageAccessGate",
    "BuyerReadyPackageArtifactStatus",
    "BuyerReadyPackageArtifactType",
    "BuyerReadyPackageRender",
    "BuyerReadyPricingBasis",
    "BuyerReadyReleaseStatus",
    "BuyerPackageArtifactRender",
    "BuyerPackageManifestRender",
    "CoverRender",
    "DataRoomDocSummaryRender",
    "DataRoomManifestRender",
    "EBITDABridgeEvidenceRender",
    "EBITDABridgeRender",
    "EBITDABridgeStepRender",
    "ExecutiveSummaryRender",
    "IMSectionRender",
    "KeyFigureRender",
    "LegalReadinessItemRender",
    "LegalReadinessRender",
    "MissingDocChecklistItemRender",
    "MissingDocChecklistRender",
    "PriceRecommendationRender",
    "ProvenanceRef",
    "TaxLatencyFlagRender",
    "TaxLatencyJurisdiction",
    "TaxLatencyRender",
    "TaxLatencyRuleID",
    "WCPegMonthlyPointRender",
    "WCPegRender",
]
