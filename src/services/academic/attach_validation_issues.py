"""Attach academic guardrail failures to a ValuationResponse before API return."""

from __future__ import annotations

from typing import Any, List, Optional

from src.utils.valuation_logger import ValuationLogger

from .academic_validation_engine import get_validation_engine
from .calculation_provenance_tracker import CalculationProvenanceTracker


def attach_academic_validation_issues_to_response(
    response: Any,
    tracker: Optional[CalculationProvenanceTracker],
    logger: ValuationLogger,
    *,
    valuation_id: str = "",
) -> None:
    """Populate ``academic_validation_issues`` when provenance validation fails."""
    if tracker is None:
        return

    try:
        validation_engine = get_validation_engine()
        validation_report = validation_engine.validate_from_provenance(tracker)

        issues: List[str] = []
        for item in validation_report.get("critical_issues") or []:
            text = str(item).strip()
            if text and text not in issues:
                issues.append(text)
        for item in validation_report.get("warnings_list") or []:
            text = str(item).strip()
            if text and text not in issues:
                issues.append(text)

        if issues:
            try:
                response.academic_validation_issues = issues
            except (AttributeError, TypeError, ValueError):
                pass
            if validation_report.get("failed", 0) > 0:
                logger.warning(
                    "[ACADEMIC] Validation failures",
                    extra={"valuation_id": valuation_id, "report": validation_report},
                )
            else:
                logger.info(
                    "[ACADEMIC] Validation advisory warnings",
                    extra={"valuation_id": valuation_id, "warnings": len(issues)},
                )
        elif validation_report.get("total_validations", 0) == 0:
            logger.debug(
                "[ACADEMIC] Validation infrastructure ran but no rules matched recorded calculation_ids",
                extra={
                    "valuation_id": valuation_id,
                    "records": len(tracker.get_all_records()),
                },
            )
        else:
            logger.info(
                "[ACADEMIC] Validation passed",
                extra={"checks": validation_report.get("passed", 0)},
            )
    except Exception as exc:
        logger.warning(
            f"[ACADEMIC] Validation error (non-fatal): {type(exc).__name__}: {exc}",
            exc_info=True,
        )
