"""
Transparency Data Adapter

Converts between backend transparency models and frontend-expected formats.
This adapter bridges the gap between the existing comprehensive transparency
system and the simplified format expected by the frontend.

ARCHITECTURE:
- Backend uses: Dict-based transparency with validation reports
- Frontend expects: List-based transparency with flatter structure
- This adapter provides bidirectional conversion

USAGE:
    backend_transparency = tracker.build()
    frontend_transparency = adapt_transparency_for_frontend(
        backend_transparency,
        confidence_breakdown,
        range_methodology
    )
"""

from typing import Dict, List, Optional, Any
from datetime import datetime

from decimal import Decimal
from src.utils.decimal_helpers import to_decimal, from_decimal
from src.domain.transparency import (
    TransparencyData as BackendTransparencyData,
    DataProvenance,
    CalculationStep as BackendCalculationStep,
)
from src.domain.owner_models.transparency import (
    TransparencyData as FrontendTransparencyData,
    DataSource as FrontendDataSource,
    CalculationStep as FrontendCalculationStep,
    ComparableCompany,
    ConfidenceBreakdown,
    RangeMethodology,
)


def convert_data_provenance_to_data_source(
    field_name: str,
    provenance: DataProvenance
) -> FrontendDataSource:
    """
    Convert backend DataProvenance to frontend DataSource format

    Args:
        field_name: Name of the field
        provenance: Backend DataProvenance object

    Returns:
        FrontendDataSource object
    """
    # Map backend source enum to user-friendly string
    source_mapping = {
        "kbo_registry": "KBO Registry (Belgian Companies)",
        "companies_house": "Companies House (UK)",
        "handelsregister": "Handelsregister (Germany)",
        "oecd_database": "OECD Industry Database",
        "ecb_data": "European Central Bank",
        "fmp_api": "Financial Modeling Prep API",
        "world_bank": "World Bank",
        "user_input": "User Input",
        "user_upload": "User Upload",
        "calculated": "Calculated",
        "estimated": "Estimated",
        "historical": "Historical Data",
        "benchmark": "Industry Benchmark",
    }

    source_name = source_mapping.get(provenance.source.value, provenance.source.value)

    # Determine cache status from quality
    cache_status = None
    if provenance.quality.value == "verified":
        cache_status = "Verified Data"
    elif provenance.quality.value == "validated":
        cache_status = "Cross-Checked"
    elif provenance.quality.value == "estimated":
        cache_status = "System Estimate"
    elif provenance.quality.value == "assumed":
        cache_status = "Assumption"

    return FrontendDataSource(
        name=field_name.replace("_", " ").title(),
        value=provenance.value,
        source=source_name,
        timestamp=provenance.source_date.isoformat() + "T00:00:00Z",
        confidence=to_decimal(provenance.confidence),
        api_url=provenance.source_url,
        cache_status=cache_status
    )


def convert_calculation_step(
    step: BackendCalculationStep,
    step_number: int
) -> FrontendCalculationStep:
    """
    Convert backend CalculationStep to frontend format

    Args:
        step: Backend CalculationStep object
        step_number: Step sequence number

    Returns:
        FrontendCalculationStep object
    """
    return FrontendCalculationStep(
        step_number=step_number,
        description=step.step_name,
        formula=step.formula or "See explanation",
        inputs=step.inputs or {},
        outputs=step.outputs or {},
        explanation=step.explanation or step.step_name
    )


def extract_comparable_companies_from_market_data(
    backend_transparency: BackendTransparencyData
) -> Optional[List[ComparableCompany]]:
    """
    Extract comparable companies from backend market data

    Args:
        backend_transparency: Backend transparency data

    Returns:
        List of ComparableCompany objects or None
    """
    if not backend_transparency.market_data:
        return None

    comparable_dicts = backend_transparency.market_data.comparable_companies
    if not comparable_dicts:
        return None

    comparables = []
    for comp_dict in comparable_dicts[:10]:  # Limit to top 10
        comparables.append(ComparableCompany(
            name=comp_dict.get("name", "Unknown"),
            country=comp_dict.get("country", "Unknown"),
            revenue=comp_dict.get("revenue", 0),
            ebitda_multiple=comp_dict.get("ev_ebitda_multiple"),
            revenue_multiple=comp_dict.get("ev_revenue_multiple"),
            similarity_score=comp_dict.get("similarity_score", 0),
            source=comp_dict.get("source", "Market Data")
        ))

    return comparables if comparables else None


def adapt_transparency_for_frontend(
    backend_transparency: Optional[BackendTransparencyData],
    confidence_breakdown: ConfidenceBreakdown,
    range_methodology: RangeMethodology
) -> Optional[FrontendTransparencyData]:
    """
    Convert backend transparency data to frontend-expected format

    Args:
        backend_transparency: Backend TransparencyData object (may be None)
        confidence_breakdown: Confidence breakdown object
        range_methodology: Range methodology object

    Returns:
        FrontendTransparencyData object or None
    """
    if not backend_transparency:
        # If no backend transparency, return minimal structure
        return FrontendTransparencyData(
            data_sources=[],
            calculation_steps=[],
            comparable_companies=None,
            confidence_breakdown=confidence_breakdown,
            range_methodology=range_methodology
        )

    # Convert data provenance to data sources list
    data_sources: List[FrontendDataSource] = []
    for field_name, provenance in backend_transparency.data_provenance.items():
        data_source = convert_data_provenance_to_data_source(field_name, provenance)
        data_sources.append(data_source)

    # Add market data as data sources
    if backend_transparency.market_data:
        market_data = backend_transparency.market_data

        # Add risk-free rate
        data_sources.append(FrontendDataSource(
            name="Risk-Free Rate",
            value=f"{market_data.risk_free_rate * 100:.2f}%",
            source=market_data.risk_free_rate_source,
            timestamp=market_data.risk_free_rate_date.isoformat() + "T00:00:00Z",
            confidence=Decimal('95.0'),
            cache_status="Market Data"
        ))

        # Add market risk premium
        data_sources.append(FrontendDataSource(
            name="Market Risk Premium",
            value=f"{market_data.market_risk_premium * 100:.2f}%",
            source=market_data.market_risk_premium_source,
            timestamp=datetime.now().isoformat() + "Z",
            confidence=Decimal('90.0'),
            cache_status="Historical Average"
        ))

        # Add industry multiples source
        data_sources.append(FrontendDataSource(
            name="Industry Multiples",
            value=f"{market_data.multiples_sample_size} companies",
            source=market_data.multiples_source,
            timestamp=market_data.multiples_date.isoformat() + "T00:00:00Z",
            confidence=Decimal('92.0'),
            cache_status=f"{market_data.multiples_sample_size} comparables"
        ))

    # Convert calculation steps (flatten from dict of lists to single list)
    calculation_steps: List[FrontendCalculationStep] = []
    step_counter = 1
    for calc_type, steps_list in backend_transparency.calculation_steps.items():
        for step in steps_list:
            frontend_step = convert_calculation_step(step, step_counter)
            calculation_steps.append(frontend_step)
            step_counter += 1

    # Extract comparable companies
    comparable_companies = extract_comparable_companies_from_market_data(backend_transparency)

    return FrontendTransparencyData(
        data_sources=data_sources,
        calculation_steps=calculation_steps,
        comparable_companies=comparable_companies,
        confidence_breakdown=confidence_breakdown,
        range_methodology=range_methodology
    )


def create_minimal_transparency(
    confidence_breakdown: ConfidenceBreakdown,
    range_methodology: RangeMethodology
) -> FrontendTransparencyData:
    """
    Create minimal transparency data when backend tracking isn't available

    This ensures the frontend always gets a transparency object, even if
    detailed tracking wasn't performed.

    Args:
        confidence_breakdown: Confidence breakdown object
        range_methodology: Range methodology object

    Returns:
        Minimal FrontendTransparencyData object
    """
    return FrontendTransparencyData(
        data_sources=[
            FrontendDataSource(
                name="User Input Data",
                value="Financial data provided by user",
                source="User Input",
                timestamp=datetime.now().isoformat() + "Z",
                confidence=Decimal('100.0'),
                cache_status="Direct Input"
            )
        ],
        calculation_steps=[
            FrontendCalculationStep(
                step_number=1,
                description="Valuation Synthesis",
                formula="Final_Valuation = Weight_DCF × DCF_Value + Weight_Multiples × Multiples_Value",
                inputs={},
                outputs={},
                explanation="Combined DCF and Market Multiples methodologies to produce final valuation"
            )
        ],
        comparable_companies=None,
        confidence_breakdown=confidence_breakdown,
        range_methodology=range_methodology
    )

