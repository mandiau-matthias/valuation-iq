"""
DCF Result Converter

Extracted from synthesizer.py to reduce complexity.
Handles conversion of DCFResult from dataclass to BaseModel.
"""

from decimal import Decimal
from typing import Optional, cast

from src.domain.models import ConfidenceLevel, DCFResult
from src.utils.decimal_helpers import to_decimal
from src.utils.exceptions import DCFCalculationError
from src.utils.logging import get_logger

logger = get_logger(__name__)


class DCFResultConverter:
    """Converts DCFResult from dataclass to BaseModel format."""

    def convert(self, dcf_result: Optional[object]) -> Optional[DCFResult]:
        """
        Convert DCFResult from dataclass to BaseModel if needed.

        Args:
            dcf_result: DCF result (may be dataclass or BaseModel)

        Returns:
            BaseModel DCFResult or None if conversion fails
        """
        if not dcf_result:
            return None

        # If already BaseModel, return as-is
        if not hasattr(dcf_result, "__dataclass_fields__"):
            return cast(DCFResult, dcf_result)

        # Convert from dataclass to BaseModel
        try:
            from dataclasses import asdict

            dcf_dict = asdict(dcf_result)

            # Convert confidence_factors from list[str] to dict[str, str]
            confidence_factors_dict = self._convert_confidence_factors(
                dcf_dict.get("confidence_factors", [])
            )

            # Convert confidence from str to ConfidenceLevel enum
            confidence_val = self._convert_confidence(dcf_dict.get("confidence", "medium"))

            # Convert confidence_score from Decimal to int
            confidence_score_val = self._convert_confidence_score(
                dcf_dict.get("confidence_score", Decimal("0.5"))
            )

            # Convert sensitivity dicts from dict[Decimal, Decimal] to dict[str, Decimal]
            sensitivity_wacc_dict = self._convert_sensitivity_dict(
                dcf_dict.get("sensitivity_wacc", {})
            )
            sensitivity_growth_dict = self._convert_sensitivity_dict(
                dcf_dict.get("sensitivity_growth", {})
            )

            return DCFResult(
                enterprise_value=dcf_dict.get("enterprise_value"),
                equity_value=dcf_dict.get("equity_value"),
                wacc=dcf_dict.get("wacc"),
                cost_of_equity=dcf_dict.get("cost_of_equity"),
                cost_of_debt=dcf_dict.get("cost_of_debt"),
                terminal_growth_rate=dcf_dict.get("terminal_growth_rate"),
                fcf_projections=dcf_dict.get("fcf_projections", []),
                pv_fcf_projections=dcf_dict.get("pv_fcf_projections", []),
                terminal_value=dcf_dict.get("terminal_value"),
                pv_terminal_value=dcf_dict.get("pv_terminal_value"),
                sensitivity_wacc=sensitivity_wacc_dict,
                sensitivity_growth=sensitivity_growth_dict,
                confidence=confidence_val,
                confidence_score=confidence_score_val,
                confidence_factors=confidence_factors_dict,
            )
        except DCFCalculationError as e:
            logger.warning(f"Failed to convert DCFResult dataclass to BaseModel: {e}")
            return None

    def _convert_confidence_factors(self, confidence_factors_list: list[object]) -> dict[str, str]:
        """Convert confidence factors from list to dict."""
        confidence_factors_dict = {}
        if isinstance(confidence_factors_list, list):
            for i, factor in enumerate(confidence_factors_list):
                confidence_factors_dict[f"factor_{i+1}"] = str(factor)
        return confidence_factors_dict

    def _convert_confidence(self, confidence_val: object) -> ConfidenceLevel:
        """Convert confidence value to ConfidenceLevel enum."""
        if isinstance(confidence_val, str):
            try:
                return ConfidenceLevel(confidence_val.lower())
            except (ValueError, AttributeError):
                return ConfidenceLevel.MEDIUM
        return (
            confidence_val
            if isinstance(confidence_val, ConfidenceLevel)
            else ConfidenceLevel.MEDIUM
        )

    def _convert_confidence_score(self, confidence_score_val: object) -> int:
        """Convert confidence score to an integer percentage."""
        if confidence_score_val is None:
            return 50
        try:
            score_decimal = to_decimal(confidence_score_val)
        except (ValueError, TypeError):
            return 50
        if Decimal("0") <= score_decimal <= Decimal("1"):
            score = int(score_decimal * Decimal("100"))
        else:
            score = int(score_decimal)
        return max(0, min(100, score))

    def _convert_sensitivity_dict(
        self, sensitivity_dict: dict[object, object]
    ) -> dict[str, object]:
        """Convert sensitivity dict keys from Decimal to str."""
        converted = {}
        if sensitivity_dict:
            for k, v in sensitivity_dict.items():
                converted[str(k)] = v
        return converted
