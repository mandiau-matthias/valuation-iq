"""
Step 2.7 Result Builder

Builds result dictionaries for SDE (Seller's Discretionary Earnings) calculation step.

SOURCE TRACING:
- Data Source: TITAN_BUSINESS_TYPES_DB + DELPHI SDE Collector
- Academic Foundation: Trugman (2017), BizBuySell (2024), IBBA (2024), Pepperdine (2024)
- Methodology: SDE × Industry-specific multiple for owner-operated businesses

ALIGNMENT WITH UPSWITCH PRIMITIVES:
- Primitive 2: Algorithmic Defensibility - SDE formula and sources fully traceable
- Primitive 3: Trust Node - accountant-grade citations for small business valuation
"""

from typing import Any, Dict, Optional
from src.utils.logging import get_logger

from ...source_tracing import build_source_metadata, get_step_academic_sources

logger = get_logger(__name__)


class Step27ResultBuilder:
    """Builds result and metadata dictionaries for Step 2.7."""

    def __init__(self, step_name: str):
        """Initialize result builder."""
        self.step_name = step_name
        self.step_number = 2.7

    def build_result_dict(
        self,
        sde: float,
        sde_multiple: float,
        sde_valuation: float,
        sde_valuation_low: float,
        sde_valuation_high: float,
        sde_components: Dict[str, float],
        industry: str,
        business_size: str,
        adjustments: Dict[str, float],
        data_source: str,
    ) -> Dict[str, Any]:
        """
        Build the result dictionary for Step 2.7.
        
        Args:
            sde: Calculated SDE value
            sde_multiple: Applied SDE multiple
            sde_valuation: SDE-based enterprise value (mid)
            sde_valuation_low: Low range (P25)
            sde_valuation_high: High range (P75)
            sde_components: Breakdown of SDE components
            industry: Business industry
            business_size: Business size tier (micro/small/medium)
            adjustments: Applied adjustments
            data_source: Source of SDE multiples
            
        Returns:
            Result dictionary for StepOutput
        """
        return {
            # Core SDE values
            "sde": sde,
            "sde_multiple": sde_multiple,
            
            # SDE-based valuation range
            "sde_valuation": sde_valuation,
            "sde_valuation_low": sde_valuation_low,
            "sde_valuation_high": sde_valuation_high,
            
            # Methodology
            "methodology": "SDE",
            "methodology_description": "Seller's Discretionary Earnings",
            
            # Classification
            "industry": industry,
            "business_size": business_size,
            
            # Transparency
            "sde_components": sde_components,
            "adjustments_applied": adjustments,
            "data_source": data_source,
            
            # Academic citation
            "academic_source": "Trugman (2017): Understanding Business Valuation",
        }

    def build_metadata_dict(
        self,
        sde: float,
        sde_components: Dict[str, float],
        sde_multiple: float,
        sde_multiple_p25: float,
        sde_multiple_p75: float,
        industry: str,
        business_size: str,
        data_source: str,
        confidence: float,
        execution_time_ms: float,
        titan_normalization_used: bool,
        database_multiples_used: bool,
    ) -> Dict[str, Any]:
        """
        Build the metadata dictionary for Step 2.7 with full source tracing.
        
        Args:
            sde: Calculated SDE value
            sde_components: Breakdown of SDE components
            sde_multiple: Applied SDE multiple (median)
            sde_multiple_p25: 25th percentile multiple
            sde_multiple_p75: 75th percentile multiple
            industry: Business industry
            business_size: Business size tier
            data_source: Source of SDE multiples
            confidence: Confidence score
            execution_time_ms: Execution time in milliseconds
            titan_normalization_used: Whether Titan normalization was used
            database_multiples_used: Whether database multiples were used
            
        Returns:
            Metadata dictionary with full source tracing
        """
        # Build source tracing metadata
        source_metadata = build_source_metadata(
            step_key="step_2_7_sde",
            data_source="BIZBUYSELL_2024" if "BizBuySell" in data_source else "TITAN_BUSINESS_TYPES_DB",
        )
        
        return {
            "calculation_details": {
                "sde": sde,
                "sde_components": sde_components,
                "sde_multiple": sde_multiple,
                "sde_multiple_p25": sde_multiple_p25,
                "sde_multiple_p75": sde_multiple_p75,
            },
            "classification": {
                "industry": industry,
                "business_size": business_size,
            },
            "data_quality": {
                "source": data_source,
                "confidence": confidence,
                "titan_normalization_used": titan_normalization_used,
                "database_multiples_used": database_multiples_used,
            },
            "execution": {
                "step_number": self.step_number,
                "execution_time_ms": execution_time_ms,
            },
            # Source tracing (Primitive 2: Algorithmic Defensibility)
            "data_source": source_metadata["data_source"],
            "data_source_name": source_metadata["data_source_name"],
            "source_confidence": source_metadata["source_confidence"],
            "academic_sources": source_metadata["academic_sources"],
            "primary_citation": source_metadata["primary_citation"],
        }
