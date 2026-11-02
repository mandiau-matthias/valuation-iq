"""Validation-check construction for comprehensive transparency output."""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal

from src.domain.transparency import ValidationCheck


def build_validation_checks(
    step_0_data: Mapping[str, object] | None,
    revenue: Decimal,
    ebitda: Decimal | None,
    confidence_score: Decimal,
) -> list[ValidationCheck]:
    """Build validation checks from Step 0 data and headline financials."""
    validation_checks: list[ValidationCheck] = []

    if step_0_data:
        quality_score = step_0_data.get("quality_score", 0)
        validation_checks.append(
            ValidationCheck(
                check_name="Data Quality Assessment",
                check_type="data_quality",
                status="passed" if quality_score >= 60 else "warning",
                severity="info" if quality_score >= 60 else "warning",
                message=f"Data quality score: {quality_score}%",
                impact_on_confidence=0,
            )
        )

        dimension_scores = step_0_data.get("dimension_scores", {})
        if isinstance(dimension_scores, Mapping):
            for dimension, score in dimension_scores.items():
                if isinstance(score, (int, float, Decimal)) and not isinstance(score, bool):
                    validation_checks.append(
                        ValidationCheck(
                            check_name=f"{dimension.replace('_', ' ').title()}",
                            check_type="data_quality",
                            status="passed" if score >= 60 else "warning",
                            severity="info",
                            message=f"{dimension.replace('_', ' ').title()} score: {score}%",
                            impact_on_confidence=0,
                        )
                    )

        sub_calculations = step_0_data.get("sub_calculations")
        saas_analysis = (
            sub_calculations.get("saas_analysis") if isinstance(sub_calculations, Mapping) else None
        )
        if isinstance(saas_analysis, Mapping):
            raw_metrics = saas_analysis.get("metrics")
            metrics = raw_metrics if isinstance(raw_metrics, Mapping) else {}
            arr_multiple = saas_analysis.get("arr_multiple")
            rule_of_40 = metrics.get("rule_of_40")
            nrr_pct = metrics.get("nrr_pct")
            validation_checks.append(
                ValidationCheck(
                    check_name="SaaS profile assessment",
                    check_type="consistency",
                    status="passed",
                    severity="info",
                    message=(
                        "SaaS-specific valuation signals applied"
                        f" (ARR multiple {arr_multiple}x, Rule of 40 {rule_of_40}, NRR {nrr_pct}%)."
                    ),
                    impact_on_confidence=0,
                )
            )

    if revenue > 0:
        validation_checks.append(
            ValidationCheck(
                check_name="Revenue validation",
                check_type="data_quality",
                status="passed",
                severity="info",
                message="Revenue is positive",
                impact_on_confidence=0,
            )
        )
    if ebitda is not None:
        validation_checks.append(
            ValidationCheck(
                check_name="EBITDA validation",
                check_type="data_quality",
                status="passed",
                severity="info",
                message="EBITDA provided",
                impact_on_confidence=0,
            )
        )

    return validation_checks
