"""Strict, independently testable DCF source admission."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from pydantic import ValidationError

from src.api.schemas.forecast_evidence import ForecastEvidence
from src.api.schemas.valuation_contracts import ValuationCase
from src.utils.source_policy_monitoring import SourcePolicyIssue, record_source_policy_issue


class ForecastEvidenceError(ValueError):
    """DCF is unavailable; other independently eligible methods may continue."""

    def __init__(self, message: str) -> None:
        record_source_policy_issue(
            SourcePolicyIssue.CURRENCY_PERIOD_CONFLICT
            if message.startswith(("FORECAST_CURRENCY_", "FORECAST_PERIOD_"))
            else SourcePolicyIssue.EVIDENCE_REJECTION
        )
        super().__init__(message)


def require_committed_forecast(request: object) -> ForecastEvidence:
    case = getattr(request, "valuation_case", None)
    forecast = getattr(case, "forecast_evidence", None)
    if forecast is None:
        raise ForecastEvidenceError(
            "FORECAST_EVIDENCE_MISSING: provide a verified company forecast or cash-flow schedule"
        )
    if (
        getattr(case, "schema_version", None) != "valuation_case.v2"
        or getattr(case, "case_attestation", None) is None
    ):
        raise ForecastEvidenceError(
            "FORECAST_EVIDENCE_UNSIGNED: forecast must be committed by a signed company case"
        )
    # model_copy(update=...) bypasses Pydantic validators. Recheck the case
    # signature at the pricing boundary so a resealed forecast cannot replace
    # the document authenticated at request admission.
    try:
        case = ValuationCase.model_validate(
            case.model_dump(mode="json") if isinstance(case, ValuationCase) else case
        )
    except (ValidationError, ValueError) as exc:
        raise ForecastEvidenceError(
            "FORECAST_EVIDENCE_UNSIGNED: signed case commitment failed validation"
        ) from exc
    try:
        forecast = ForecastEvidence.model_validate(
            forecast.model_dump(mode="json") if isinstance(forecast, ForecastEvidence) else forecast
        )
    except ValidationError as exc:
        raise ForecastEvidenceError(
            "FORECAST_EVIDENCE_INVALID: source commitment or schedule failed validation"
        ) from exc
    evidence = getattr(case, "accounting_evidence", None)
    tenant = getattr(evidence, "tenant_id", None)
    if isinstance(evidence, dict):
        tenant = evidence.get("tenant_id")
    if forecast.company_id != getattr(case, "company_id", None) or forecast.tenant_id != tenant:
        raise ForecastEvidenceError(
            "FORECAST_IDENTITY_MISMATCH: forecast company and tenant must match source evidence"
        )
    if forecast.currency != getattr(request, "currency", None):
        raise ForecastEvidenceError("FORECAST_CURRENCY_MISMATCH")
    verified_at = datetime.fromisoformat(forecast.verification.verified_at.replace("Z", "+00:00"))
    if verified_at > datetime.now(timezone.utc):
        raise ForecastEvidenceError("FORECAST_VERIFICATION_IN_FUTURE")
    return forecast


def require_verified_forecast(request: object) -> ForecastEvidence:
    forecast = require_committed_forecast(request)
    if getattr(request, "projection_years", len(forecast.periods)) != len(forecast.periods):
        raise ForecastEvidenceError(
            "FORECAST_SCHEDULE_MISMATCH: projection horizon must equal the verified schedule"
        )
    rows = sorted(
        (
            row
            for row in getattr(
                request, "historical_years", getattr(request, "historical_years_data", [])
            )
            if getattr(row, "is_forecast", False)
        ),
        key=lambda row: row.year,
    )
    if len(rows) != len(forecast.periods):
        raise ForecastEvidenceError(
            "FORECAST_SCHEDULE_MISMATCH: all forecast periods must be supplied"
        )
    for row, period in zip(rows, forecast.periods):
        # The existing annual DCF engine cannot faithfully price a stub schedule.
        if (
            period.start_date.month != 1
            or period.start_date.day != 1
            or period.end_date.month != 12
            or period.end_date.day != 31
            or period.start_date.year != period.end_date.year
        ):
            raise ForecastEvidenceError(
                "FORECAST_PERIOD_UNSUPPORTED: annual calendar periods required by this DCF engine"
            )
        if row.year != period.end_date.year:
            raise ForecastEvidenceError("FORECAST_SCHEDULE_MISMATCH: fiscal year differs")
        if row.year <= getattr(
            getattr(request, "current_year", getattr(request, "current_year_data", None)),
            "year",
            row.year - 1,
        ):
            raise ForecastEvidenceError("FORECAST_PERIOD_OVERLAPS_ACTUALS")
        for field in (
            "revenue",
            "ebitda",
            "depreciation",
            "amortization",
            "capex",
            "free_cash_flow",
        ):
            value = getattr(row, field, None)
            if value is None or Decimal(str(value)) != Decimal(getattr(period, field)):
                raise ForecastEvidenceError(f"FORECAST_SCHEDULE_MISMATCH: {row.year}.{field}")
    if getattr(request, "dcf_input_mode", None) != "fcff_only":
        raise ForecastEvidenceError(
            "FORECAST_FCFF_MODE_REQUIRED: use the reconciled company cash-flow schedule"
        )
    from src.utils.adaptive_input_helpers import get_dcf_mid_year_discounting

    if get_dcf_mid_year_discounting(request) != (forecast.discount_timing == "mid_year"):
        raise ForecastEvidenceError("FORECAST_DISCOUNT_TIMING_MISMATCH")
    return forecast


def optional_verified_forecast(request: object) -> ForecastEvidence | None:
    """Allow disclosed scenarios, but never ignore a supplied verification claim.

    A signed case is checked even when its forecast is absent so deleting a
    committed forecast with model_copy cannot downgrade a tampered request.
    """
    case = getattr(request, "valuation_case", None)
    if getattr(case, "forecast_evidence", None) is not None:
        return require_verified_forecast(request)
    if getattr(case, "case_attestation", None) is not None:
        try:
            ValuationCase.model_validate(
                case.model_dump(mode="json") if isinstance(case, ValuationCase) else case
            )
        except (ValidationError, ValueError) as exc:
            raise ForecastEvidenceError(
                "FORECAST_EVIDENCE_UNSIGNED: signed case commitment failed validation"
            ) from exc
    return None
