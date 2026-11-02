"""
Report Configuration Module

RESPONSIBILITIES:
- Provide dynamic configuration for report generation
- Centralize configurable values that were previously hardcoded
- Support different configurations per methodology or business type

This module enables fully dynamic report generation without hardcoded values.
"""

from dataclasses import dataclass, field
from typing import Dict, List
from decimal import Decimal


@dataclass
class ReportConfiguration:
    """
    Dynamic configuration for valuation report generation.
    
    All values that were previously hardcoded in templates are now
    configurable through this class.
    """
    
    # =========================================================================
    # SENSITIVITY ANALYSIS CONFIGURATION
    # =========================================================================
    
    # EBITDA variation percentages for sensitivity table
    sensitivity_ebitda_variations: List[float] = field(
        default_factory=lambda: [-0.20, 0.0, 0.20]
    )
    
    # Multiple range factors (used when actual range not available)
    sensitivity_multiple_factor_low: float = 0.70  # 30% below
    sensitivity_multiple_factor_high: float = 1.30  # 30% above
    
    # =========================================================================
    # MULTI-YEAR WEIGHTING CONFIGURATION
    # =========================================================================
    
    # Standard 3-year recency ramp (50/33/17 — most recent gets highest weight).
    # Matches valuation_constants.recency_weights(3); the live engine derives the
    # ramp dynamically for 1-5 year windows, so this is illustrative only.
    weight_distribution: Dict[str, float] = field(
        default_factory=lambda: {
            "year_1": 0.50,  # Most recent year (3/6)
            "year_2": 0.33,  # Second year (2/6)
            "year_3": 0.17,  # Third year (1/6)
        }
    )
    
    # =========================================================================
    # DCF METHODOLOGY DEFAULTS
    # =========================================================================
    
    dcf_default_projection_years: int = 5
    dcf_default_terminal_growth_rate: float = 0.02  # 2%
    dcf_default_wacc: float = 0.12  # 12% for SMEs
    
    # =========================================================================
    # HYBRID METHODOLOGY WEIGHTS — REMOVED
    # =========================================================================
    # Hybrid DCF/multiples weights are determined at calculation time by
    # HybridWeightCalculator and persisted on the response.  The report
    # reads them via `valuation_contract.extract_methodology_weights()`.
    # There must be no static default here.  See domain/valuation_contract.py.
    
    # =========================================================================
    # RISK ASSESSMENT DEFAULTS
    # =========================================================================
    
    # Default risk level when assessment unavailable
    default_risk_level: str = "GEMIDDELD"
    
    # Risk level descriptions (Dutch)
    risk_level_descriptions: Dict[str, str] = field(
        default_factory=lambda: {
            "LAAG": "gediversifieerd klantenbestand, gedelegeerde operaties",
            "GEMIDDELD": "enige eigenaarafhankelijkheid, gedeeltelijke delegatie",
            "HOOG": "eigenaar-centrisch, belangrijke relaties in gevaar",
            "LOW": "gediversifieerd klantenbestand, gedelegeerde operaties",
            "MEDIUM": "enige eigenaarafhankelijkheid, gedeeltelijke delegatie",
            "HIGH": "eigenaar-centrisch, belangrijke relaties in gevaar",
        }
    )
    
    # =========================================================================
    # SIZE TIER CONFIGURATION
    # =========================================================================
    
    default_size_tier: str = "Micro"
    
    size_tier_labels: Dict[str, str] = field(
        default_factory=lambda: {
            "MICRO": "Micro-KMO",
            "SMALL": "Kleine KMO",
            "MEDIUM": "Middelgrote KMO",
        }
    )
    
    # =========================================================================
    # REPORT METADATA
    # =========================================================================
    
    # Minimum pages (cover + content)
    min_pages: int = 4
    
    # Report validity period in days
    validity_period_days: int = 90
    
    def to_dict(self) -> Dict:
        """Convert configuration to dictionary for template injection."""
        return {
            "sensitivity_ebitda_variations": self.sensitivity_ebitda_variations,
            "sensitivity_multiple_factor_low": self.sensitivity_multiple_factor_low,
            "sensitivity_multiple_factor_high": self.sensitivity_multiple_factor_high,
            "weight_distribution": self.weight_distribution,
            "dcf_default_projection_years": self.dcf_default_projection_years,
            "dcf_default_terminal_growth_rate": self.dcf_default_terminal_growth_rate,
            "dcf_default_wacc": self.dcf_default_wacc,
            "default_risk_level": self.default_risk_level,
            "risk_level_descriptions": self.risk_level_descriptions,
            "default_size_tier": self.default_size_tier,
            "size_tier_labels": self.size_tier_labels,
            "min_pages": self.min_pages,
            "validity_period_days": self.validity_period_days,
        }


# Singleton instance for default configuration
_default_config: ReportConfiguration = None


def get_report_config() -> ReportConfiguration:
    """Get the default report configuration instance."""
    global _default_config
    if _default_config is None:
        _default_config = ReportConfiguration()
    return _default_config


def create_custom_config(**kwargs) -> ReportConfiguration:
    """
    Create a custom report configuration with overrides.
    
    Example:
        config = create_custom_config(
            sensitivity_ebitda_variations=[-0.15, 0, 0.15],
            dcf_default_projection_years=7,
        )
    """
    return ReportConfiguration(**kwargs)
