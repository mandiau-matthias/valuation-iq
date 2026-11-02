"""
Sensitivity Analysis Builder

Builds sensitivity analysis data for Info Tab display, showing how changes in
EBITDA and multiple affect the final valuation.

Academic Reference: Damodaran (2012) - Sensitivity analysis is critical for
understanding valuation uncertainty and risk ranges.
"""

from decimal import Decimal
from typing import Any, Dict, List, Optional

from src.utils.decimal_helpers import to_decimal, from_decimal
from src.utils.logging import get_logger

logger = get_logger(__name__)


class SensitivityAnalysisBuilder:
    """
    Builds sensitivity analysis data for valuation reports.
    
    Calculates sensitivity to:
    - EBITDA changes (±10%, ±20%)
    - Multiple changes (±0.5x, ±1.0x)
    - Combined sensitivity matrix
    """
    
    @staticmethod
    def build_sensitivity_analysis(
        base_equity_value: Decimal,
        base_ebitda: Decimal,
        base_multiple: Decimal
    ) -> Dict[str, Any]:
        """
        Build sensitivity analysis data structure.
        
        WHAT: Calculates valuation sensitivity to EBITDA and multiple changes
        WHY: Provides transparency in valuation uncertainty (Academic Persona requirement)
        HOW: Varies EBITDA and multiple inputs and calculates resulting equity values
        WHEN: Called during Info Tab HTML generation
        
        Args:
            base_equity_value: Base equity value (mid)
            base_ebitda: Base EBITDA value
            base_multiple: Base multiple value
            
        Returns:
            Dictionary with sensitivity tables and chart data
        """
        try:
            # Validate inputs
            if base_equity_value is None or base_ebitda is None or base_multiple is None:
                logger.warning(
                    "⚠️ [SENSITIVITY-ANALYSIS-BUILDER] Missing required inputs for sensitivity analysis",
                    extra={
                        "base_equity_value": str(base_equity_value) if base_equity_value else None,
                        "base_ebitda": str(base_ebitda) if base_ebitda else None,
                        "base_multiple": str(base_multiple) if base_multiple else None
                    }
                )
                return {
                    "base_equity_value": None,
                    "base_ebitda": None,
                    "base_multiple": None,
                    "ebitda_sensitivity": [],
                    "multiple_sensitivity": [],
                    "combined_matrix": [],
                    "ebitda_percentages": [],
                    "multiple_adjustments": []
                }
            
            base_equity_decimal = to_decimal(base_equity_value)
            base_ebitda_decimal = to_decimal(base_ebitda)
            base_multiple_decimal = to_decimal(base_multiple)
            
            # Validate non-zero values
            if base_ebitda_decimal <= 0 or base_multiple_decimal <= 0:
                logger.warning(
                    "⚠️ [SENSITIVITY-ANALYSIS-BUILDER] Invalid input values (zero or negative)",
                    extra={
                        "base_ebitda": str(base_ebitda_decimal),
                        "base_multiple": str(base_multiple_decimal)
                    }
                )
                return {
                    "base_equity_value": float(from_decimal(base_equity_decimal)) if base_equity_decimal else None,
                    "base_ebitda": float(from_decimal(base_ebitda_decimal)) if base_ebitda_decimal else None,
                    "base_multiple": float(from_decimal(base_multiple_decimal)) if base_multiple_decimal else None,
                    "ebitda_sensitivity": [],
                    "multiple_sensitivity": [],
                    "combined_matrix": [],
                    "ebitda_percentages": [],
                    "multiple_adjustments": []
                }
            
            # EBITDA Sensitivity: -20%, -10%, base, +10%, +20%
            ebitda_sensitivity = []
            ebitda_percentages = [-0.20, -0.10, 0.0, 0.10, 0.20]
            
            for pct in ebitda_percentages:
                adjusted_ebitda = base_ebitda_decimal * (Decimal("1") + Decimal(str(pct)))
                equity_value = adjusted_ebitda * base_multiple_decimal
                ebitda_sensitivity.append({
                    "ebitda_change_pct": pct * 100,
                    "adjusted_ebitda": float(from_decimal(adjusted_ebitda)),
                    "equity_value": float(from_decimal(equity_value)),
                    "value_change": float(from_decimal(equity_value - base_equity_decimal)),
                    "value_change_pct": float(from_decimal((equity_value - base_equity_decimal) / base_equity_decimal * Decimal("100"))) if base_equity_decimal > 0 else 0.0
                })
            
            # Multiple Sensitivity: -1.0x, -0.5x, base, +0.5x, +1.0x
            multiple_sensitivity = []
            multiple_adjustments = [Decimal("-1.0"), Decimal("-0.5"), Decimal("0.0"), Decimal("0.5"), Decimal("1.0")]
            
            for adj in multiple_adjustments:
                adjusted_multiple = base_multiple_decimal + adj
                if adjusted_multiple <= 0:
                    continue  # Skip negative multiples
                equity_value = base_ebitda_decimal * adjusted_multiple
                multiple_sensitivity.append({
                    "multiple_adjustment": float(adj),
                    "adjusted_multiple": float(from_decimal(adjusted_multiple)),
                    "equity_value": float(from_decimal(equity_value)),
                    "value_change": float(from_decimal(equity_value - base_equity_decimal)),
                    "value_change_pct": float(from_decimal((equity_value - base_equity_decimal) / base_equity_decimal * Decimal("100"))) if base_equity_decimal > 0 else 0.0
                })
            
            # Combined Sensitivity Matrix (EBITDA × Multiple)
            # Create matrix with EBITDA changes on rows, multiple changes on columns
            combined_matrix = []
            ebitda_matrix_pcts = [-0.20, -0.10, 0.0, 0.10, 0.20]
            multiple_matrix_adjs = [Decimal("-1.0"), Decimal("-0.5"), Decimal("0.0"), Decimal("0.5"), Decimal("1.0")]
            
            for ebitda_pct in ebitda_matrix_pcts:
                row = []
                adjusted_ebitda = base_ebitda_decimal * (Decimal("1") + Decimal(str(ebitda_pct)))
                
                for mult_adj in multiple_matrix_adjs:
                    adjusted_multiple = base_multiple_decimal + mult_adj
                    if adjusted_multiple <= 0:
                        row.append(None)
                        continue
                    
                    equity_value = adjusted_ebitda * adjusted_multiple
                    row.append({
                        "equity_value": float(from_decimal(equity_value)),
                        "ebitda_change_pct": ebitda_pct * 100,
                        "multiple_adjustment": float(mult_adj),
                        "adjusted_ebitda": float(from_decimal(adjusted_ebitda)),
                        "adjusted_multiple": float(from_decimal(adjusted_multiple))
                    })
                combined_matrix.append(row)
            
            return {
                "base_equity_value": float(from_decimal(base_equity_decimal)),
                "base_ebitda": float(from_decimal(base_ebitda_decimal)),
                "base_multiple": float(from_decimal(base_multiple_decimal)),
                "ebitda_sensitivity": ebitda_sensitivity,
                "multiple_sensitivity": multiple_sensitivity,
                "combined_matrix": combined_matrix,
                "ebitda_percentages": [p * 100 for p in ebitda_matrix_pcts],
                "multiple_adjustments": [float(adj) for adj in multiple_matrix_adjs]
            }
            
        except Exception as e:
            logger.error(
                "❌ [SENSITIVITY-ANALYSIS-BUILDER] Failed to build sensitivity analysis",
                extra={
                    "base_equity_value": str(base_equity_value) if base_equity_value else None,
                    "base_ebitda": str(base_ebitda) if base_ebitda else None,
                    "base_multiple": str(base_multiple) if base_multiple else None,
                    "error": str(e)
                },
                exc_info=True
            )
            return {
                "base_equity_value": None,
                "base_ebitda": None,
                "base_multiple": None,
                "ebitda_sensitivity": [],
                "multiple_sensitivity": [],
                "combined_matrix": [],
                "ebitda_percentages": [],
                "multiple_adjustments": []
            }
