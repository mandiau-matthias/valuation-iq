"""
Methodology Builder for Step 11 Synthesis

Handles methodology extraction and statement generation.
"""

from collections.abc import Mapping
from decimal import Decimal
from typing import Any, Dict, List, Optional

from src.domain.methodology_source_registry import get_methodology_source_registry
from src.utils.core.data_extraction_helpers import extract_owner_employee_counts_from_request
from src.utils.decimal_helpers import from_decimal, to_decimal
from src.utils.logging import get_logger
from src.utils.sole_trader_detector import SoleTraderDetector

from ...base_step import StepStatus

logger = get_logger(__name__)

_RANGE_METHODOLOGY_MARKERS = (
    "Multiple Dispersion",
    "Confidence Spread",
    "Asymmetric",
)
_STEP_METHODOLOGY_MARKERS = (
    (4, "OWNER_CONCENTRATION"),
    (5, "SIZE_DISCOUNT"),
    (6, "LIQUIDITY_DISCOUNT"),
    (8, "OWNERSHIP_ADJUSTMENT"),
)
_CRITICAL_REVIEW_STEPS = (0, 1, 2, 3, 7, 9, 10)


def _base_methodologies() -> dict[str, object]:
    return {
        "primary_method": None,
        "range_methodology": None,
        "dcf_used": False,
        "multiples_used": True,
        "hybrid_used": False,
        "confidence_methodology": "Big 4 8-factor model",
        "used_methodologies": ["MULTIPLES"],
    }


def _completed_step_result(
    previous_results: Mapping[int, object], step_num: int
) -> Optional[Mapping[str, object]]:
    step = previous_results.get(step_num)
    if not step or getattr(step, "status", None) != StepStatus.COMPLETED:
        return None

    result = getattr(step, "result", None)
    return result if isinstance(result, Mapping) else None


def _used_methodologies(methodologies: dict[str, object]) -> list[str]:
    used = methodologies.get("used_methodologies")
    if isinstance(used, list):
        return used

    methodologies["used_methodologies"] = []
    return methodologies["used_methodologies"]


def _apply_primary_methodology(
    methodologies: dict[str, object],
    previous_results: Mapping[int, object],
) -> None:
    step2_result = _completed_step_result(previous_results, 2)
    if step2_result is None:
        return

    primary_method = step2_result.get("primary_method")
    if primary_method:
        methodologies["primary_method"] = primary_method


def _apply_dcf_methodology(
    methodologies: dict[str, object],
    previous_results: Mapping[int, object],
) -> None:
    step0_result = _completed_step_result(previous_results, 0)
    if step0_result is None or not step0_result.get("dcf_eligible", False):
        return

    methodologies["dcf_used"] = True
    methodologies["hybrid_used"] = True
    used_methodologies = _used_methodologies(methodologies)
    used_methodologies.extend(["DCF", "HYBRID"])


def _apply_range_methodology(
    methodologies: dict[str, object],
    previous_results: Mapping[int, object],
) -> None:
    step10_result = _completed_step_result(previous_results, 10)
    if step10_result is None:
        return

    range_method = step10_result.get("methodology")
    if not range_method:
        return

    methodologies["range_methodology"] = range_method
    if any(marker in str(range_method) for marker in _RANGE_METHODOLOGY_MARKERS):
        _used_methodologies(methodologies).append("RANGE_METHODOLOGY")


def _append_completed_step_methodologies(
    methodologies: dict[str, object],
    previous_results: Mapping[int, object],
) -> None:
    used_methodologies = _used_methodologies(methodologies)
    for step_num, marker in _STEP_METHODOLOGY_MARKERS:
        if _completed_step_result(previous_results, step_num) is not None:
            used_methodologies.append(marker)


def _readiness_list(readiness: dict[str, object], key: str) -> list[str]:
    values = readiness[key]
    if isinstance(values, list):
        return values
    readiness[key] = []
    return readiness[key]


def _mark_not_ready(readiness: dict[str, object], warning: str) -> None:
    readiness["ready"] = False
    readiness["status"] = "NOT_READY"
    _readiness_list(readiness, "warnings").append(warning)


def _append_critical_step_checks(
    readiness: dict[str, object],
    previous_results: Mapping[int, object],
) -> None:
    for step_num in _CRITICAL_REVIEW_STEPS:
        step = previous_results.get(step_num)
        if not step or getattr(step, "status", None) != StepStatus.COMPLETED:
            _mark_not_ready(readiness, f"Critical step {step_num} not completed successfully")
        else:
            _readiness_list(readiness, "checks").append(f"Step {step_num} completed successfully")


def _append_ownership_step_check(
    readiness: dict[str, object],
    previous_results: Mapping[int, object],
) -> None:
    step8 = previous_results.get(8)
    step8_status = getattr(step8, "status", None)
    if step8_status == StepStatus.COMPLETED:
        _readiness_list(readiness, "checks").append(
            "Step 8 (ownership adjustment) completed successfully"
        )
    elif step8_status == StepStatus.FAILED:
        _mark_not_ready(readiness, "Critical step 8 not completed successfully")
    else:
        _readiness_list(readiness, "checks").append(
            "Step 8 (ownership adjustment) not applicable — no fractional-interest "
            "adjustment required"
        )


def _append_data_quality_check(
    readiness: dict[str, object],
    previous_results: Mapping[int, object],
) -> None:
    step0_result = _completed_step_result(previous_results, 0)
    if step0_result is None:
        return

    quality_score = step0_result.get("quality_score", 0)
    if quality_score < 50:
        _mark_not_ready(
            readiness,
            f"Data quality score ({quality_score}) below minimum threshold (50)",
        )
    elif quality_score < 70:
        _readiness_list(readiness, "warnings").append(
            f"Data quality score ({quality_score}) is moderate - review recommended"
        )
    else:
        _readiness_list(readiness, "checks").append(
            f"Data quality score ({quality_score}) meets professional standards"
        )


def _append_quality_checkpoint_check(
    readiness: dict[str, object],
    quality_checkpoint: Optional[Mapping[str, object]],
) -> None:
    if not quality_checkpoint:
        return

    if quality_checkpoint.get("status") == "degraded":
        _readiness_list(readiness, "warnings").append(
            "Data quality degraded during calculation - review recommended"
        )
    else:
        _readiness_list(readiness, "checks").append(
            "Data quality remained stable throughout calculation"
        )


def _append_range_documentation_checks(
    readiness: dict[str, object],
    previous_results: Mapping[int, object],
) -> None:
    step10 = previous_results.get(10)
    if not step10 or getattr(step10, "status", None) != StepStatus.COMPLETED:
        return

    metadata = getattr(step10, "metadata", {})
    if metadata.get("methodology_selection"):
        _readiness_list(readiness, "checks").append("Range methodology selection documented")
    if metadata.get("spread_calculation") or metadata.get("dispersion_calculation"):
        _readiness_list(readiness, "checks").append("Range calculation methodology documented")


def _append_value_chain_check(
    readiness: dict[str, object],
    previous_results: Mapping[int, object],
) -> None:
    step10 = previous_results.get(10)
    if not step10 or getattr(step10, "status", None) != StepStatus.COMPLETED:
        return

    metadata = getattr(step10, "metadata", {})
    if metadata.get("value_preservation_validated"):
        _readiness_list(readiness, "checks").append("Value chain consistency validated")
    else:
        _readiness_list(readiness, "warnings").append(
            "Value chain consistency not validated - review recommended"
        )


def _append_professional_review_notes(readiness: dict[str, object]) -> None:
    notes = _readiness_list(readiness, "notes")
    if readiness["ready"]:
        notes.append(
            "This comprehensive breakdown provides full transparency into every calculation step, "
            "formula, and assumption. The methodology and sources are documented to academic and "
            "professional standards."
        )
        notes.append(
            "Suitable for presentation to professors, valuation experts, and potential investors."
        )
    else:
        notes.append(
            "Review recommended before professional presentation. Some data quality or calculation "
            "completeness issues were detected."
        )


class MethodologyBuilder:
    """
    Builder for methodology operations.

    Responsibilities:
    - Extract methodology information from previous steps
    - Generate methodology statements
    - Generate academic sources
    - Assess professional review readiness
    """

    def __init__(self):
        """Initialize methodology builder."""
        pass

    def extract_methodologies(self, previous_results: Dict[int, Any]) -> Dict[str, Any]:
        """
        Extract methodology information from previous steps.

        Phase Decimal(\'2.1\'): Extracts methodologies used throughout the valuation journey.
        """
        methodologies = _base_methodologies()
        _apply_primary_methodology(methodologies, previous_results)
        _apply_dcf_methodology(methodologies, previous_results)
        _apply_range_methodology(methodologies, previous_results)
        _append_completed_step_methodologies(methodologies, previous_results)
        _used_methodologies(methodologies).append("CONFIDENCE_SCORING")
        return methodologies

    def generate_methodology_statement(
        self,
        methodologies: Dict[str, Any],
        source_registry: Any,
        previous_results: Dict[int, Any],
        request: Optional[Any] = None,
    ) -> str:
        """
        Generate dynamic methodology statement.

        Phase Decimal(\'2.2\'): Creates comprehensive methodology statement based on methodologies used.
        Includes sole-trader-specific messaging if applicable.
        """
        from .methodology.extractors import (
            AdjustmentExtractor,
            AssumptionExtractor,
            SoleTraderDetectorWrapper,
        )

        # Detect sole trader status
        is_sole_trader = SoleTraderDetectorWrapper.detect(request)

        # Extract adjustments and assumptions
        adjustments = AdjustmentExtractor.extract(previous_results, is_sole_trader)
        assumptions = AssumptionExtractor.extract(previous_results, is_sole_trader)

        # Generate statement using registry
        statement = source_registry.get_methodology_statement(
            methodologies=methodologies.get("used_methodologies", []),
            primary_method=methodologies.get("primary_method"),
            range_methodology=methodologies.get("range_methodology"),
            adjustments=adjustments,
            assumptions=assumptions,
            engine_version="2.0.0",
        )

        # Append sole-trader-specific note if applicable
        if is_sole_trader:
            statement += "\n\n**Sole Trader Valuation Note:** This valuation has been optimized for sole trader businesses, applying maximum owner concentration discounts, enhanced size and liquidity discounts, and asymmetric range methodology to reflect the higher risk profile and reduced marketability typical of owner-dependent businesses."

        return statement

    def generate_academic_sources(
        self, methodologies: Dict[str, Any], source_registry: Any
    ) -> List[Dict[str, Any]]:
        """
        Generate dynamic academic sources based on methodologies used.

        Phase Decimal(\'2.3\'): Returns only sources relevant to methodologies actually used.
        """
        used_methodologies = methodologies.get("used_methodologies", [])
        sources = source_registry.get_all_sources(used_methodologies)

        # Format sources for frontend display
        formatted_sources = []
        for source in sources:
            formatted_source = {
                "author": source.get("author", ""),
                "year": source.get("year", ""),
                "title": source.get("title", ""),
                "relevance": source.get("relevance", ""),
            }

            # Add optional fields
            if source.get("edition"):
                formatted_source["edition"] = source.get("edition")
            if source.get("publisher"):
                formatted_source["publisher"] = source.get("publisher")
            if source.get("journal"):
                formatted_source["journal"] = source.get("journal")
                if source.get("volume"):
                    formatted_source["volume"] = source.get("volume")
                if source.get("pages"):
                    formatted_source["pages"] = source.get("pages")

            formatted_sources.append(formatted_source)

        return formatted_sources

    def assess_professional_review_readiness(
        self, previous_results: Dict[int, Any], quality_checkpoint: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Assess professional review readiness.

        Phase Decimal(\'2.4\'): Validates that valuation is ready for professional review.
        """
        readiness = {
            "ready": True,
            "status": "PROFESSIONAL_REVIEW_READY",
            "checks": [],
            "warnings": [],
            "notes": [],
        }

        _append_critical_step_checks(readiness, previous_results)
        _append_ownership_step_check(readiness, previous_results)
        _append_data_quality_check(readiness, previous_results)
        _append_quality_checkpoint_check(readiness, quality_checkpoint)
        _append_range_documentation_checks(readiness, previous_results)
        _append_value_chain_check(readiness, previous_results)
        _append_professional_review_notes(readiness)
        return readiness
