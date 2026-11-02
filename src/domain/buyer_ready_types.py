"""Shared buyer-ready render contract enums and constants."""

from __future__ import annotations

from typing import Literal

BuyerReadyConfidence = Literal["high", "medium", "low"]
"""Per-section confidence ladder (F1 spec §8).

Drives render branching: low → suppress LLM narrative, render placeholder.
"""

BuyerReadyBridgeEvidenceStatus = Literal["documented", "weak_evidence", "unsupported"]
"""Buyer-belief status for one EBITDA bridge adjustment."""

BuyerReadyBridgeBeliefStatus = Literal[
    "buyer_believable",
    "advisor_review",
    "not_buyer_ready",
]
"""Bridge-level distribution gate framed around buyer belief."""

BuyerReadyChecklistStatus = Literal["red", "yellow", "green"]
"""F2 missing-doc checklist status per category."""

BuyerReadyIMSectionKey = Literal[
    "cover",
    "executive_summary",
    "business_overview",
    "financial_summary",
    "ebitda_bridge",
    "customer_mix",
    "team_and_ownership",
    "growth_thesis",
    "deal_terms",
    "transferability_and_risks",
    "wc_peg",
    "tax_latency",
    "appendix_methodology",
    "appendix_missing_docs",
    "disclaimers",
]
"""15 IM sections from F1 spec §6. Lock-in for F3 LLM narrative dispatch."""

EXPECTED_IM_SECTION_ORDER = [
    "cover",
    "executive_summary",
    "business_overview",
    "financial_summary",
    "ebitda_bridge",
    "customer_mix",
    "team_and_ownership",
    "growth_thesis",
    "deal_terms",
    "transferability_and_risks",
    "wc_peg",
    "tax_latency",
    "appendix_methodology",
    "appendix_missing_docs",
    "disclaimers",
]
"""Locked IM section order. Titan must post all 15 sections, in this order."""

BuyerReadyChecklistCategory = Literal[
    "audited_financials",
    "cap_table",
    "top10_customer_contracts",
    "top10_supplier_contracts",
    "employment_contracts",
    "ip_register",
    "property_leases",
    "tax_filings",
    "pending_litigation",
    "environmental_compliance",
    "insurance_certificates",
    "data_protection",
]
"""12 canonical SME share-deal categories from F2 spec."""

TaxLatencyJurisdiction = Literal["BE", "NL"]
"""F5 jurisdiction routing. EU expansion = future enum extension."""

BuyerReadyPricingBasis = Literal[
    "valuation_report",
    "valuation_report_with_advisor_buffer",
    "advisor_override",
    "indicative_listing_range",
]
"""Source basis for the buyer-facing price recommendation."""

BuyerReadyLegalReadinessStatus = Literal["clear", "review", "blocked"]
"""Lawyer-handoff status for one legal-readiness item."""

BuyerReadyReleaseStatus = Literal[
    "teaser_ready",
    "nda_required",
    "lawyer_review_required",
    "blocked",
]
"""Whether the package can be released externally and under which gate."""

BuyerReadyDealStructure = Literal["share_deal", "asset_deal", "mixed", "unknown"]
"""High-level deal-structure assumption. Detailed drafting stays counsel-owned."""

BuyerReadyPackageArtifactType = Literal[
    "valuation_main_report",
    "valuation_pdf",
    "im_cim",
    "dd_checklist",
    "buyer_faq",
    "ebitda_bridge",
    "wc_tax",
    "data_room_manifest",
    "price_recommendation",
    "legal_readiness",
]
"""Canonical artifacts that make up the controlled SME transaction package."""

BUYER_READY_REQUIRED_PACKAGE_ARTIFACT_TYPES: tuple[BuyerReadyPackageArtifactType, ...] = (
    "valuation_main_report",
    "valuation_pdf",
    "im_cim",
    "dd_checklist",
    "buyer_faq",
    "ebitda_bridge",
    "wc_tax",
    "data_room_manifest",
    "price_recommendation",
    "legal_readiness",
)
"""Required D0 manifest artifact set for a complete SME transaction package."""

BuyerReadyPackageArtifactStatus = Literal["ready", "needs_review", "blocked", "missing"]
"""Package artifact status used for buyer release and advisor review gates."""

BuyerReadyPackageAccessGate = Literal["internal", "public_teaser", "after_nda", "lawyer_only"]
"""Disclosure gate for each package artifact."""

BuyerReadyCustomContentProvider = Literal[
    "claude_opus_4_7",
    "claude_sonnet_4_6",
    "structured_only",
    "advisor_supplied",
    "counsel_owned",
]
"""Provider that produced custom prose for a controlled package artifact."""

BuyerReadyCustomContentStatus = Literal[
    "claude_generated",
    "structured_only",
    "advisor_supplied",
    "advisor_review_required",
    "counsel_review_required",
]
"""Document-level status for custom prose versus structured fallback content."""

BuyerReadyAssistantSurface = Literal["venus", "mercury"]
"""Assistant surfaces that can keep package artifacts fillable and accessible."""

BuyerReadyIntegrationInputStatus = Literal["live", "partial", "missing", "not_applicable"]
"""Whether integration-fed inputs behind an artifact are available for the live dossier."""

BuyerReadyLegalChecklistCategory = Literal[
    "confidentiality_nda",
    "corporate_authority",
    "ubo_aml_kyc",
    "annual_accounts",
    "tax_position",
    "employment_ip",
    "material_contracts",
    "privacy_data_room",
    "litigation_claims",
    "asset_share_structure",
    "regulatory_permits",
    "lawyer_handoff",
]
"""Pre-legal M&A readiness categories; no contract drafting or redlining."""

TaxLatencyRuleID = Literal[
    # Belgium (7)
    "be_liquidatiebonus_optimisation",
    "be_dtl_revalued_assets",
    "be_vendor_loans",
    "be_vat_share_vs_asset",
    "be_management_fee_circularity",
    "be_consolidated_goodwill_amortisation",
    "be_carry_forward_losses",
    # Netherlands (3)
    "nl_box2_dga_salary",
    "nl_latent_dtl_goodwill",
    "nl_thirty_percent_ruling_expiry",
]
"""F5 tax-latency rule IDs. Each fires deterministically per balance-sheet
or owner-profile signal; never invented at render time."""


__all__ = [
    "BUYER_READY_REQUIRED_PACKAGE_ARTIFACT_TYPES",
    "BuyerReadyAssistantSurface",
    "BuyerReadyBridgeBeliefStatus",
    "BuyerReadyBridgeEvidenceStatus",
    "BuyerReadyChecklistCategory",
    "BuyerReadyChecklistStatus",
    "BuyerReadyConfidence",
    "BuyerReadyCustomContentProvider",
    "BuyerReadyCustomContentStatus",
    "BuyerReadyDealStructure",
    "BuyerReadyIMSectionKey",
    "BuyerReadyIntegrationInputStatus",
    "BuyerReadyLegalChecklistCategory",
    "BuyerReadyLegalReadinessStatus",
    "BuyerReadyPackageAccessGate",
    "BuyerReadyPackageArtifactStatus",
    "BuyerReadyPackageArtifactType",
    "BuyerReadyPricingBasis",
    "BuyerReadyReleaseStatus",
    "EXPECTED_IM_SECTION_ORDER",
    "TaxLatencyJurisdiction",
    "TaxLatencyRuleID",
]
