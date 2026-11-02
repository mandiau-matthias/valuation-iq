"""
Risk Factors Builders

Extracted from risk_factors_extraction_coordinator.py to reduce complexity.
These builders handle individual priority-based risk factor generation.
"""

from datetime import date
from decimal import Decimal
from typing import Any, Dict, List, Optional

from src.utils.logging import get_logger
from src.services.infrastructure.report_confidence import (
    confidence_score_display,
    confidence_score_percent,
)

logger = get_logger(__name__)


class DataQualityRiskBuilder:
    """Builds risk factors based on data quality score."""

    @staticmethod
    def build_risks(transparency: Dict[str, Any]) -> List[str]:
        """
        Build risk factors from Step 0 data quality score.

        Args:
            transparency: Transparency data containing calculation steps

        Returns:
            List of risk factors (may be empty)
        """
        risks = []
        calculation_steps = (
            transparency.get("calculation_steps", []) if isinstance(transparency, dict) else []
        )

        data_quality_score = None
        for step in calculation_steps:
            if isinstance(step, dict) and step.get("step_number") == 0:
                step_result = step.get("result", {})
                if isinstance(step_result, dict):
                    data_quality_score = step_result.get(
                        "data_quality_score"
                    ) or step_result.get("quality_score")
                    break

        if data_quality_score is not None and data_quality_score < 70:
            risks.append(
                f"Limited financial data reduces valuation confidence (data quality: {data_quality_score}%)"
            )

        return risks


class ConfidenceRiskBuilder:
    """Builds risk factors based on confidence score."""

    @staticmethod
    def build_risks(results: Dict[str, Any]) -> List[str]:
        """
        Build risk factors from confidence score.

        Args:
            results: Valuation results containing confidence score

        Returns:
            List of risk factors (may be empty)
        """
        risks = []
        confidence_score = confidence_score_percent(results.get("confidence_score"))
        if confidence_score is not None and confidence_score < 60:
            risks.append(
                f"Lower confidence score ({confidence_score_display(confidence_score)}%) indicates valuation uncertainty due to limited comparables or data gaps"
            )
        return risks


class MissingDataRiskBuilder:
    """Builds risk factors based on missing financial data."""

    @staticmethod
    def build_risks(current_year_data: Any) -> List[str]:
        """
        Build risk factors from missing financial data fields.

        Args:
            current_year_data: Current year financial data

        Returns:
            List of risk factors (may be empty)
        """
        risks = []
        if not current_year_data:
            return risks

        missing_fields = []
        if not hasattr(current_year_data, "ebitda") or current_year_data.ebitda is None:
            missing_fields.append("EBITDA")
        if not hasattr(current_year_data, "revenue") or current_year_data.revenue is None:
            missing_fields.append("revenue")
        if (
            not hasattr(current_year_data, "net_income")
            or current_year_data.net_income is None
        ):
            missing_fields.append("net income")

        if missing_fields:
            risks.append(
                f"Missing financial data ({', '.join(missing_fields)}) limits valuation precision"
            )

        return risks


class SizeRiskBuilder:
    """Builds risk factors based on company size."""

    @staticmethod
    def build_risks(revenue: Decimal) -> List[str]:
        """
        Build risk factors from company revenue size.

        Args:
            revenue: Company revenue (Decimal)

        Returns:
            List of risk factors (may be empty)
        """
        from src.utils.decimal_helpers import to_decimal
        
        risks = []
        revenue_decimal = to_decimal(revenue)
        if revenue_decimal > 0:
            if revenue_decimal < Decimal("1000000"):
                risks.append(
                    "Micro company size (<€1M revenue) increases valuation uncertainty and reduces market comparables"
                )
            elif revenue_decimal < Decimal("5000000"):
                risks.append(
                    "Small company size (<€5M revenue) increases valuation uncertainty due to limited comparable transactions"
                )
        return risks


class OwnerDependencyRiskBuilder:
    """Builds risk factors based on owner dependency."""

    @staticmethod
    def build_risks(request: Any) -> List[str]:
        """
        Build risk factors from owner dependency metrics.

        Args:
            request: Valuation request containing owner dependency data

        Returns:
            List of risk factors (may be empty)
        """
        risks = []
        owner_dependency = getattr(request, "owner_dependency", None)
        owner_dependency_decimal = None
        if owner_dependency is not None and not isinstance(owner_dependency, bool):
            try:
                owner_dependency_decimal = (
                    owner_dependency
                    if isinstance(owner_dependency, Decimal)
                    else Decimal(str(owner_dependency))
                )
            except (ArithmeticError, TypeError, ValueError):
                owner_dependency_decimal = None
        if (
            owner_dependency_decimal is not None
            and owner_dependency_decimal > Decimal("0.5")
        ):
            risks.append(
                f"High owner dependency ({owner_dependency_decimal:.0%}) indicates key person risk that may impact business continuity"
            )
        elif hasattr(request, "number_of_owners") and hasattr(request, "number_of_employees"):
            owners = request.number_of_owners or 0
            employees = max(request.number_of_employees or 1, 1)
            if owners / employees > 0.5:
                risks.append(
                    f"Owner concentration ({owners}/{employees} owners) indicates key person dependency risk"
                )
        return risks


class OperatingHistoryRiskBuilder:
    """Builds risk factors based on operating history."""

    @staticmethod
    def build_risks(request: Any) -> List[str]:
        """
        Build risk factors from operating history.

        Args:
            request: Valuation request containing founding year

        Returns:
            List of risk factors (may be empty)
        """
        risks = []
        if hasattr(request, "founding_year") and request.founding_year:
            years = date.today().year - request.founding_year
            if years < 3:
                risks.append(
                    f"Limited operating history ({years} years) increases valuation uncertainty"
                )
        return risks


class GenericRiskBuilder:
    """Builds generic risk factors as fallback."""

    @staticmethod
    def build_risks(revenue: Decimal) -> List[str]:
        """
        Build generic risk factors when no specific risks are identified.

        Args:
            revenue: Company revenue (Decimal)

        Returns:
            List with at least 1 generic risk factor
        """
        from src.utils.decimal_helpers import to_decimal
        
        risks = []
        revenue_decimal = to_decimal(revenue)
        if revenue_decimal < Decimal("5000000"):
            risks.append(
                "Small company size increases valuation uncertainty due to limited comparable market transactions"
            )
        else:
            risks.append(
                "Valuation based on market multiples may vary based on comparable company selection and market conditions"
            )
        return risks
