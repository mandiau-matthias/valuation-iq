"""
Step 2.5 Orchestrator

Orchestrates EBITDA normalization execution flow.
"""

import time
from decimal import Decimal
from typing import Any, Dict, Optional

from src.services.academic.calculation_provenance_tracker import record_calculation_safe
from src.utils.decimal_helpers import to_decimal, from_decimal
from src.utils.fiscal_year import get_current_filing_year
from src.utils.logging import get_logger

from ...base_step import StepOutput, StepStatus
from ..builders.step_2_5_result_builder import Step25ResultBuilder
from ..calculators.normalization_calculator import NormalizationCalculator
from ..handlers.step_2_5_error_handler import Step25ErrorHandler

logger = get_logger(__name__)


class Step25Orchestrator:
    """Orchestrates Step 2.5 execution."""
    
    def __init__(self, step_name: str):
        """Initialize orchestrator with step name."""
        self.step_name = step_name
        self.calculator = NormalizationCalculator()
        self.result_builder = Step25ResultBuilder(step_name)
        self.error_handler = Step25ErrorHandler(step_name)
    
    async def orchestrate_execution(
        self,
        request: Any,
        step1: Dict[str, Any],
        step2: Dict[str, Any],
        correlation_id: Optional[str],
        execution_start_time: float
    ) -> StepOutput:
        """
        Orchestrate EBITDA normalization execution.
        
        Args:
            request: Valuation request
            step1: Step 1 results (input data)
            step2: Step 2 results (benchmarking)
            correlation_id: Correlation ID
            execution_start_time: Start time for execution tracking
            
        Returns:
            StepOutput with normalization results
        """
        # Check if user has already normalized EBITDA
        current_year_data = getattr(request, "current_year_data", None)
        if current_year_data and getattr(current_year_data, "ebitda_normalized", False):
            metadata = getattr(current_year_data, "ebitda_normalization_metadata", {})
            logger.info(
                "✅ User-normalized EBITDA detected, skipping automatic normalization",
                extra={
                    "reported_ebitda": metadata.get("reported_ebitda"),
                    "normalized_ebitda": current_year_data.ebitda,
                    "valuation_ebitda_basis": step1.get("ebitda"),
                    "total_adjustments": metadata.get("total_adjustments"),
                    "adjustment_count": metadata.get("adjustment_count"),
                    "confidence": metadata.get("confidence_score"),
                }
            )
            return StepOutput(
                step_number=2,
                step_name=self.step_name,
                status=StepStatus.COMPLETED,
                result={
                    "automatic_normalization_skipped": True,
                    "reason": "User normalization applied",
                    "user_normalization_metadata": metadata,
                    "reported_ebitda": metadata.get("reported_ebitda"),
                    "normalized_ebitda": from_decimal(to_decimal(current_year_data.ebitda)),
                    "current_year_normalized_ebitda": from_decimal(to_decimal(current_year_data.ebitda)),
                    "valuation_ebitda_basis": from_decimal(to_decimal(step1.get("ebitda", 0))),
                    "total_adjustments": metadata.get("total_adjustments", 0),
                },
                execution_time_ms=(time.time() - execution_start_time) * 1000,
                metadata={"user_normalized": True}
            )
        
        # Extract required data from Step 1 (guard None — .get default won't help if key exists with None value)
        revenue_raw = step1.get("revenue")
        revenue = to_decimal(revenue_raw) if revenue_raw is not None else Decimal("0")
        ebitda_raw = step1.get("ebitda")
        reported_ebitda = to_decimal(ebitda_raw) if ebitda_raw is not None else None
        
        # CRITICAL: Extract current year EBITDA for transparency (may differ from weighted)
        current_year_ebitda_raw = None
        current_year = get_current_filing_year()
        if hasattr(request, 'current_year_data') and request.current_year_data:
            current_year_ebitda_raw = to_decimal(getattr(request.current_year_data, 'ebitda', None))
            current_year = int(getattr(request.current_year_data, 'year', None) or current_year)
        
        # CRITICAL: Log EBITDA source transparency
        using_weighted_from_step1 = step1.get("using_weighted_metrics", False)
        # DEBUG: input audit; [STEP-2.5-SUMMARY] below carries the canonical
        # full audit trail.
        logger.debug(
            "🔍 [EBITDA-TRANSPARENCY] Step 2.5 EBITDA sources",
            extra={
                "step_1_ebitda_used": from_decimal(reported_ebitda),
                "step_1_using_weighted": using_weighted_from_step1,
                "current_year_ebitda_raw": from_decimal(current_year_ebitda_raw) if current_year_ebitda_raw else None,
                "ebitda_source_match": current_year_ebitda_raw == reported_ebitda if current_year_ebitda_raw else None,
                "note": "If using_weighted=True, Step 1 EBITDA is weighted average from historical years (McKinsey methodology)",
                "transparency_issue": "reported_ebitda label may be misleading if weighted average is used",
                "correlation_id": correlation_id,
            }
        )
        
        # Validate inputs
        if revenue <= 0:
            return self.error_handler.handle_invalid_data(
                "Revenue is zero or negative",
                from_decimal(reported_ebitda),
                from_decimal(revenue)
            )
        
        if reported_ebitda is None:
            logger.warning(
                "⚠️ EBITDA not available, normalization skipped",
                extra={"step_number": 2.5}
            )
            return self.error_handler.handle_invalid_data(
                "EBITDA not available",
                None,
                from_decimal(revenue)
            )
        
        # Extract historical data (correct field name per schemas.py)
        historical_data = getattr(request, "historical_years_data", [])
        
        # Extract optional owner compensation (if provided)
        owner_compensation_raw = getattr(
            getattr(request, "current_year_data", None), 
            "owner_compensation", 
            None
        )
        owner_compensation = to_decimal(owner_compensation_raw) if owner_compensation_raw else None
        
        # Extract business context from Step 2
        business_category = step2.get("business_type_category")
        business_type_id = step2.get("business_type_id")
        
        # Get location from request
        location = getattr(request, "location", "Belgium")
        
        logger.debug(
            "🔍 Orchestrating EBITDA normalization",
            extra={
                "reported_ebitda": from_decimal(reported_ebitda),
                "revenue": from_decimal(revenue),
                "historical_years": len(historical_data),
                "historical_data_received": historical_data is not None and len(historical_data) > 0,
                "historical_data_list": [
                    {
                        "year": getattr(year_data, "year", None),
                        "revenue": from_decimal(to_decimal(getattr(year_data, "revenue", 0))),
                        "ebitda": from_decimal(to_decimal(getattr(year_data, "ebitda", 0))),
                    }
                    for year_data in (historical_data[:3] if historical_data else [])
                ] if historical_data else [],
                "has_owner_comp": owner_compensation is not None,
                "business_category": business_category,
                "correlation_id": correlation_id,
            }
        )
        
        # Extract base multiple from Step 2 (for reference)
        base_multiple = to_decimal(step2.get('ev_ebitda_multiple', 0)) if step2 else None
        
        # Execute quality-based multiple calibration (MULTIPLE-FIRST)
        quality_result = self.calculator.calculate_quality_multiple_adjustment(
            reported_ebitda=reported_ebitda,
            revenue=revenue,
            historical_data=historical_data,
            base_multiple=base_multiple,
            owner_compensation=owner_compensation,
            business_category=business_category,
            location=location,
            business_type_id=business_type_id,
            current_year=current_year,
        )
        
        # DEBUG: dup of "[STEP-2.5-SUMMARY] Multiple Calibration Complete - FULL AUDIT TRAIL".
        logger.debug(
            "✅ Step 2.5 quality calibration complete (MULTIPLE-FIRST)",
            extra={
                "reported_ebitda": from_decimal(reported_ebitda),
                "base_multiple": from_decimal(base_multiple) if base_multiple else None,
                "quality_multiple_adjustment": quality_result.get("quality_multiple_adjustment"),
                "num_quality_factors": len(quality_result.get("quality_factors", [])),
                "earnings_quality_score": quality_result.get("quality_analysis", {}).get("earnings_quality_score"),
                "volatility_level": quality_result.get("margin_analysis", {}).get("volatility_level"),
                "confidence": quality_result.get("confidence_score"),
                "methodology": "Multiple-first (no double-counting)",
                "correlation_id": correlation_id,
            }
        )

        # Academic provenance: record the calibrated EBITDA multiple
        # (base + quality adjustment). Validation rule `ebitda_multiple_range`
        # enforces 2.0x - 15.0x per Damodaran (2012) / Ibbotson (2024).
        quality_adj_for_validation = quality_result.get("quality_multiple_adjustment") or 0
        if base_multiple is not None and base_multiple > 0:
            adjusted_multiple = float(base_multiple) + float(quality_adj_for_validation)
            record_calculation_safe(
                "ebitda_multiple_adjustment",
                adjusted_multiple,
                step_number=2,
                section_name="Multiple Calibration",
                inputs={
                    "base_multiple": from_decimal(base_multiple),
                    "quality_adjustment": float(quality_adj_for_validation),
                },
            )
        
        # Calculate execution time
        # CRITICAL FIX: Convert execution_start_time to float if it's Decimal to match time.time() return type
        execution_start_time_float = float(execution_start_time) if isinstance(execution_start_time, Decimal) else execution_start_time
        execution_time_ms = to_decimal((time.time() - execution_start_time_float) * 1000)
        
        # CRITICAL: Add transparency metadata about EBITDA source
        transparency_metadata = {
            "current_year_ebitda": from_decimal(current_year_ebitda_raw) if current_year_ebitda_raw else None,
            "using_weighted_from_step1": using_weighted_from_step1,
            "ebitda_source_explanation": (
                "Weighted average from historical years (McKinsey methodology)" 
                if using_weighted_from_step1 
                else "Current year reported EBITDA"
            ),
        }
        
        # Build and return result
        result_output = self.result_builder.build_success_output(
            quality_result,
            execution_time_ms,
            correlation_id,
            transparency_metadata
        )
        
        # CRITICAL: Final audit trail summary
        logger.info(
            "🎯 [STEP-2.5-SUMMARY] Multiple Calibration Complete - FULL AUDIT TRAIL",
            extra={
                "input_ebitda_from_step1": from_decimal(reported_ebitda),
                "input_was_weighted": using_weighted_from_step1,
                "current_year_ebitda_actual": from_decimal(current_year_ebitda_raw) if current_year_ebitda_raw else None,
                "normalized_ebitda_output": quality_result.get("normalized_ebitda"),
                "adjustments_applied": len(quality_result.get("ebitda_adjustments", [])),
                "quality_multiple_adjustment": quality_result["quality_multiple_adjustment"],
                "methodology": "Multiple-First (adjustments to multiple, not EBITDA)",
                "transparency_note": (
                    f"Weighted EBITDA ({from_decimal(reported_ebitda):,.0f}) used instead of current year ({from_decimal(current_year_ebitda_raw):,.0f}) per McKinsey methodology"
                    if using_weighted_from_step1 and current_year_ebitda_raw
                    else "Using current year reported EBITDA"
                ),
                "correlation_id": correlation_id,
            }
        )
        
        # Log final output structure
        logger.debug(
            "🔍 Step 2.5 final output structure",
            extra={
                "has_result": hasattr(result_output, "result"),
                "result_type": type(result_output.result).__name__ if hasattr(result_output, "result") else None,
                "result_keys": list(result_output.result.keys()) if hasattr(result_output, "result") and isinstance(result_output.result, dict) else [],
                "status": result_output.status.value if hasattr(result_output, "status") else None,
                "correlation_id": correlation_id,
            }
        )
        
        return result_output
