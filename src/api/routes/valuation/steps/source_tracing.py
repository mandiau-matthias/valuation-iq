"""
Step Source Tracing Module

Provides academic source definitions and data source tracing for all valuation steps.
Ensures every calculation step can show its methodological foundation and data origin.

ALIGNMENT WITH UPSWITCH PRIMITIVES:
- Primitive 2: Algorithmic Defensibility - every adjustment visible and justified
- Primitive 3: Trust Node - accountant-grade citations for professional defensibility

Academic Sources:
- Damodaran (2012): Investment Valuation
- Trugman (2017): Understanding Business Valuation (SME-specific)
- Koller (2020): McKinsey Valuation
- Pratt & Niculita (2008): Valuing a Business
- Hitchner (2017): Financial Valuation
- Pepperdine (2024): Private Capital Markets Report

Data Sources:
- DELPHI_BENCHMARK_CONTRACT: Published Upswitch Index benchmark contract used for both calculation and explanation
- COUNTRY_BASELINE_BENCHMARK_CONTRACT: Disclosed country-baseline benchmark contract used when no local Upswitch Index cell exists
- TITAN_BUSINESS_TYPES_DB: Titan transport for Upswitch Index benchmark contracts and business-type context
- DELPHI_COLLECTORS: Upswitch Index candidate evidence collectors; AI output remains proposal-only until publication gates pass
- PEPPERDINE_2024: SME transaction multiples from Pepperdine annual report
- VFB_BELGIUM_2024: Belgian SME market data from VFB

@module source_tracing
@author UpSwitch CTO Team
@date January 2026
@version 1.0.0
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class AcademicSource:
    """Represents an academic citation."""

    source_id: str
    author: str
    year: int
    title: str
    relevance: str
    publisher: Optional[str] = None
    pages: Optional[str] = None
    confidence_level: str = "HIGH"


# =============================================================================
# ACADEMIC SOURCE DEFINITIONS BY STEP
# =============================================================================

STEP_ACADEMIC_SOURCES: Dict[str, List[Dict[str, Any]]] = {
    # Step 2: Industry Benchmarking
    "step_2_benchmarking": [
        {
            "source_id": "ivs_2025",
            "author": "International Valuation Standards Council",
            "year": 2025,
            "title": "International Valuation Standards",
            "publisher": "IVSC",
            "relevance": "Evidence, valuation uncertainty, and source transparency",
            "confidence_level": "VERY_HIGH",
        },
        {
            "source_id": "trugman_2017",
            "author": "Trugman, G.R.",
            "year": 2017,
            "title": "Understanding Business Valuation",
            "publisher": "AICPA",
            "relevance": "SME-specific multiple selection methodology",
            "confidence_level": "VERY_HIGH",
        },
    ],
    # Step 2.5: SME Multiple Calibration
    "step_2_5_calibration": [
        {
            "source_id": "trugman_2017",
            "author": "Trugman, G.R.",
            "year": 2017,
            "title": "Understanding Business Valuation: A Practical Guide to Valuing Small to Medium-Sized Businesses",
            "publisher": "AICPA",
            "pages": "Chapter 6: SME Size Adjustments",
            "relevance": "SME-specific multiple calibration methodology",
            "confidence_level": "VERY_HIGH",
        },
        {
            "source_id": "hitchner_2017",
            "author": "Hitchner, J.R.",
            "year": 2017,
            "title": "Financial Valuation: Applications and Models",
            "publisher": "Wiley",
            "relevance": "Private company multiple adjustments",
            "confidence_level": "VERY_HIGH",
        },
    ],
    # Step 2.7: SDE Calculation (for small owner-operated businesses)
    "step_2_7_sde": [
        {
            "source_id": "trugman_2017",
            "author": "Trugman, G.R.",
            "year": 2017,
            "title": "Understanding Business Valuation",
            "publisher": "AICPA",
            "pages": "Chapter 7: Seller's Discretionary Earnings",
            "relevance": "SDE methodology for owner-operated businesses",
            "confidence_level": "VERY_HIGH",
        },
        {
            "source_id": "bizbuysell_2024",
            "author": "BizBuySell",
            "year": 2024,
            "title": "Annual Small Business Transaction Survey",
            "relevance": "SDE multiples by industry for micro/small businesses",
            "confidence_level": "HIGH",
        },
        {
            "source_id": "ibba_2024",
            "author": "International Business Brokers Association",
            "year": 2024,
            "title": "Market Pulse Survey Q4",
            "relevance": "SDE multiples and owner compensation benchmarks",
            "confidence_level": "HIGH",
        },
    ],
    # Step 3: Base Enterprise Value
    "step_3_base_ev": [
        {
            "source_id": "koller_2020",
            "author": "Koller, T., Goedhart, M., & Wessels, D.",
            "year": 2020,
            "title": "Valuation: Measuring and Managing the Value of Companies",
            "publisher": "McKinsey & Company / Wiley",
            "pages": "Chapter 10: Market Multiples",
            "relevance": "Enterprise Value calculation using EBITDA multiples",
            "confidence_level": "VERY_HIGH",
        },
        {
            "source_id": "damodaran_2012",
            "author": "Damodaran, A.",
            "year": 2012,
            "title": "Investment Valuation",
            "publisher": "Wiley",
            "pages": "Chapter 8: Relative Valuation",
            "relevance": "EV/EBITDA and EV/Revenue methodology",
            "confidence_level": "VERY_HIGH",
        },
    ],
    # Step 4: Owner Concentration Discount
    "step_4_owner_concentration": [
        {
            "source_id": "pratt_niculita_2008",
            "author": "Pratt, S.P. & Niculita, A.V.",
            "year": 2008,
            "title": "Valuing a Business: The Analysis and Appraisal of Closely Held Companies",
            "publisher": "McGraw-Hill",
            "pages": "Chapter 12: Key Person Discount",
            "relevance": "Owner dependency discount methodology",
            "confidence_level": "VERY_HIGH",
        },
        {
            "source_id": "hitchner_2017",
            "author": "Hitchner, J.R.",
            "year": 2017,
            "title": "Financial Valuation",
            "publisher": "Wiley",
            "pages": "Chapter 8: Key Person Adjustments",
            "relevance": "Key person risk quantification",
            "confidence_level": "VERY_HIGH",
        },
    ],
    # Step 5: Size Discount
    "step_5_size_discount": [
        {
            "source_id": "duff_phelps_2024",
            "author": "Duff & Phelps (Kroll)",
            "year": 2024,
            "title": "Valuation Handbook: Guide to Cost of Capital",
            "relevance": "Size premium/discount methodology",
            "confidence_level": "VERY_HIGH",
        },
        {
            "source_id": "fama_french_1992",
            "author": "Fama, E.F. & French, K.R.",
            "year": 1992,
            "title": "The Cross-Section of Expected Stock Returns",
            "publisher": "Journal of Finance",
            "pages": "Vol. 47, pp. 427-465",
            "relevance": "Size premium empirical foundation",
            "confidence_level": "VERY_HIGH",
        },
    ],
    # Step 6: Liquidity Discount
    "step_6_liquidity_discount": [
        {
            "source_id": "longstaff_1995",
            "author": "Longstaff, F.A.",
            "year": 1995,
            "title": "How Much Can Marketability Affect Security Values?",
            "publisher": "Journal of Finance",
            "pages": "Vol. 50, pp. 1767-1774",
            "relevance": "Liquidity discount methodology",
            "confidence_level": "VERY_HIGH",
        },
        {
            "source_id": "koeplin_2000",
            "author": "Koeplin, J., Sarin, A., & Shapiro, A.C.",
            "year": 2000,
            "title": "The Private Company Discount",
            "publisher": "Journal of Applied Corporate Finance",
            "pages": "Vol. 12(4), pp. 94-101",
            "relevance": "Private company liquidity discount (20-30%)",
            "confidence_level": "VERY_HIGH",
        },
    ],
    # Step 7: EV to Equity Bridge
    "step_7_ev_to_equity": [
        {
            "source_id": "damodaran_2012",
            "author": "Damodaran, A.",
            "year": 2012,
            "title": "Investment Valuation",
            "publisher": "Wiley",
            "pages": "Chapter 9: Enterprise Value to Equity Value",
            "relevance": "EV to Equity bridge methodology",
            "confidence_level": "VERY_HIGH",
        },
    ],
    # Step 8: Ownership Adjustment
    "step_8_ownership": [
        {
            "source_id": "pratt_niculita_2008",
            "author": "Pratt, S.P. & Niculita, A.V.",
            "year": 2008,
            "title": "Valuing a Business",
            "publisher": "McGraw-Hill",
            "pages": "Chapter 13: Minority Interests and Control Premiums",
            "relevance": "Ownership stake adjustment methodology",
            "confidence_level": "VERY_HIGH",
        },
    ],
    # Step 9: Confidence Score
    "step_9_confidence": [
        {
            "source_id": "ivs_2017",
            "author": "International Valuation Standards Council",
            "year": 2017,
            "title": "International Valuation Standards (IVS)",
            "relevance": "Valuation uncertainty and confidence assessment",
            "confidence_level": "VERY_HIGH",
        },
    ],
    # Step 11: Final Synthesis
    "step_11_synthesis": [
        {
            "source_id": "hitchner_2017",
            "author": "Hitchner, J.R.",
            "year": 2017,
            "title": "Financial Valuation",
            "publisher": "Wiley",
            "pages": "Chapter 15: Reconciliation of Value",
            "relevance": "Multi-method valuation synthesis",
            "confidence_level": "VERY_HIGH",
        },
        {
            "source_id": "pratt_niculita_2008",
            "author": "Pratt, S.P. & Niculita, A.V.",
            "year": 2008,
            "title": "Valuing a Business",
            "publisher": "McGraw-Hill",
            "pages": "Chapter 18: Reconciliation and Final Value",
            "relevance": "Final valuation reconciliation methodology",
            "confidence_level": "VERY_HIGH",
        },
    ],
}


# =============================================================================
# DATA SOURCE DEFINITIONS
# =============================================================================

DATA_SOURCES = {
    "DELPHI_BENCHMARK_CONTRACT": {
        "name": "Upswitch Index Benchmark Contract",
        "description": (
            "Published benchmark contract from the Upswitch Index. The same contract supplies "
            "the valuation multiple, provenance, and report explanation."
        ),
        "confidence": "VERY_HIGH",
        "update_frequency": "Published by deterministic gates and operator approval",
    },
    "COUNTRY_BASELINE_BENCHMARK_CONTRACT": {
        "name": "Disclosed Country Baseline Benchmark Contract",
        "description": (
            "Country-level baseline benchmark supplied by Titan when no defendable "
            "local Upswitch Index cell exists for the business type and country. The same "
            "contract supplies the valuation multiple, provenance, and disclosure."
        ),
        "confidence": "LOW",
        "update_frequency": "Versioned baseline; replaced by Upswitch Index contract when available",
    },
    "TITAN_BUSINESS_TYPES_DB": {
        "name": "Titan Business Types Context",
        "description": "Titan transport for Upswitch Index benchmark contracts and business-type context",
        "confidence": "HIGH",
        "update_frequency": "Real-time read-through of published Upswitch Index contracts",
    },
    "DELPHI_COLLECTORS": {
        "name": "Upswitch Index Candidate Evidence Collectors",
        "description": (
            "Proposal-only collection lane. Collector output is not a published "
            "valuation benchmark until deterministic validation and operator "
            "approval publish it into an Upswitch Index benchmark contract."
        ),
        "confidence": "PROPOSAL_ONLY",
        "update_frequency": "Continuous collection; publication requires approval",
    },
    "DISCLOSED_EXTERNAL_MARKET_FALLBACK": {
        "name": "Disclosed External Market Fallback",
        "description": (
            "Explicitly accepted fallback market/default data. This is not treated "
            "as local Upswitch Index evidence and must not be presented as a resolved "
            "benchmark contract."
        ),
        "confidence": "LOW",
        "update_frequency": "Only used with explicit fallback consent",
    },
    "PEPPERDINE_2024": {
        "name": "Pepperdine Private Capital Markets",
        "description": "SME transaction multiples from Pepperdine University annual report",
        "confidence": "VERY_HIGH",
        "update_frequency": "Annual",
    },
    "VFB_BELGIUM_2024": {
        "name": "VFB Belgium SME Report",
        "description": "Belgian SME market multiples from Vlaamse Federatie van Beleggers",
        "confidence": "HIGH",
        "update_frequency": "Annual",
    },
    "BIZBUYSELL_2024": {
        "name": "BizBuySell Transaction Survey",
        "description": "SDE multiples from US small business transactions",
        "confidence": "HIGH",
        "update_frequency": "Quarterly",
    },
}


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def get_step_academic_sources(step_key: str) -> List[Dict[str, Any]]:
    """
    Get academic sources for a specific step.

    Args:
        step_key: Step identifier (e.g., "step_3_base_ev")

    Returns:
        List of academic source dictionaries
    """
    return STEP_ACADEMIC_SOURCES.get(step_key, [])


def get_data_source_info(source_key: str) -> Dict[str, Any]:
    """
    Get data source information.

    Args:
        source_key: Data source identifier (e.g., "TITAN_BUSINESS_TYPES_DB")

    Returns:
        Data source information dictionary
    """
    return DATA_SOURCES.get(
        source_key,
        {
            "name": source_key,
            "description": "Unknown source",
            "confidence": "MEDIUM",
        },
    )


def build_source_metadata(
    step_key: str,
    data_source: str = "TITAN_BUSINESS_TYPES_DB",
    additional_sources: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Build complete source metadata for a step.

    Args:
        step_key: Step identifier
        data_source: Primary data source key
        additional_sources: Additional academic sources to include

    Returns:
        Complete source metadata dictionary for template rendering
    """
    academic_sources = get_step_academic_sources(step_key)

    if additional_sources:
        academic_sources = academic_sources + additional_sources

    data_source_info = get_data_source_info(data_source)

    return {
        "data_source": data_source,
        "data_source_name": data_source_info.get("name", data_source),
        "data_source_description": data_source_info.get("description", ""),
        "source_confidence": data_source_info.get("confidence", "MEDIUM"),
        "academic_sources": academic_sources,
        "has_academic_sources": len(academic_sources) > 0,
        "primary_citation": academic_sources[0] if academic_sources else None,
    }
