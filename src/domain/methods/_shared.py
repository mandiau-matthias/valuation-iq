"""Shared helpers used by multiple valuation method modules."""

import logging
import math
from collections.abc import Mapping
from decimal import Decimal
from typing import TYPE_CHECKING, Literal, Optional, cast

from src.domain.financial_arithmetic import FinancialNumber, decimal_number
from src.domain.saas_valuation_adjuster import SaasAdjustmentResult
from src.utils.decimal_helpers import optional_decimal

if TYPE_CHECKING:
    from src.domain.saas_eligibility import SaasEligibilityVerdict
    from src.domain.saas_input_validation import SaasValidationFlag, SaasValidationReport

_logger = logging.getLogger(__name__)


def _decimal_or_none(value: object) -> Optional[Decimal]:
    parsed = optional_decimal(value)
    return parsed if isinstance(parsed, Decimal) else None


def equity_from_ev(
    ev: FinancialNumber,
    *,
    total_adjustment: FinancialNumber,
    total_debt: FinancialNumber,
    cash: FinancialNumber,
    ownership_multiplier: FinancialNumber = 1,
    nwc_adjustment: FinancialNumber = 0,
) -> Decimal:
    """EV-to-equity bridge for multiples-derived enterprise values.

    Applies ``total_adjustment`` (size, liquidity, country risk discounts)
    before subtracting debt and adding cash/NWC.
    """
    enterprise = decimal_number(ev, "enterprise value")
    adjustment = decimal_number(total_adjustment, "risk adjustment")
    debt = decimal_number(total_debt, "financial debt")
    cash_amount = decimal_number(cash, "cash")
    ownership = decimal_number(ownership_multiplier, "ownership")
    nwc = decimal_number(nwc_adjustment, "working capital adjustment")
    if not 0 <= adjustment <= 1 or not 0 <= ownership <= 1:
        raise ValueError("risk adjustment and ownership must be between zero and one")
    return (enterprise * (1 - adjustment) - debt + cash_amount + nwc) * ownership


def dcf_equity_from_ev(
    ev: FinancialNumber,
    *,
    total_debt: FinancialNumber,
    cash: FinancialNumber,
    ownership_multiplier: FinancialNumber = 1,
    nwc_adjustment: FinancialNumber = 0,
) -> Decimal:
    """EV-to-equity bridge for DCF — risk is already in WACC, so
    ``total_adjustment`` is NOT applied (would double-count risk).
    """
    return equity_from_ev(
        ev,
        total_adjustment=0.0,
        total_debt=total_debt,
        cash=cash,
        ownership_multiplier=ownership_multiplier,
        nwc_adjustment=nwc_adjustment,
    )


def debt_overhang_details(
    *,
    enterprise_value: FinancialNumber,
    equity_value: FinancialNumber,
    total_debt: FinancialNumber,
    cash: FinancialNumber,
    ownership_multiplier: FinancialNumber = 1.0,
    nwc_adjustment: FinancialNumber = 0.0,
    total_adjustment: FinancialNumber = 0.0,
) -> dict[str, object]:
    """Auditable bridge payload for distressed cases where equity is negative."""
    enterprise_value = decimal_number(enterprise_value, "enterprise_value")
    equity_value = decimal_number(equity_value, "equity_value")
    total_debt = decimal_number(total_debt, "total_debt")
    cash = decimal_number(cash, "cash")
    ownership_multiplier = decimal_number(ownership_multiplier, "ownership_multiplier")
    nwc_adjustment = decimal_number(nwc_adjustment, "nwc_adjustment")
    total_adjustment = decimal_number(total_adjustment, "total_adjustment")
    net_debt = total_debt - cash
    return {
        "enterprise_value": round(enterprise_value, 2),
        "equity_value": round(equity_value, 2),
        "debt_overhang": round(abs(min(equity_value, Decimal(0))), 2),
        "net_debt": round(net_debt, 2),
        "total_debt": round(total_debt, 2),
        "cash": round(cash, 2),
        "nwc_adjustment": round(nwc_adjustment, 2),
        "ownership_multiplier": round(ownership_multiplier, 6),
        "total_adjustment": round(total_adjustment, 6),
        "premise": "negative_equity_after_debt_bridge",
        "transaction_readiness_implication": (
            "Debt exceeds the post-adjustment enterprise value; buyer discussions "
            "should treat this as a debt-overhang / restructuring case rather than "
            "a missing valuation."
        ),
    }


def finite_float(value: Optional[float], fallback: float = 0.0) -> float:
    """Clamp NaN/Inf/None to *fallback*; pass finite values through."""
    if value is None or not math.isfinite(value):
        return fallback
    return value


def resolve_book_equity(balance_sheet: Optional[Mapping[str, object]]) -> Optional[Decimal]:
    if not isinstance(balance_sheet, Mapping):
        return None

    explicit_equity = _decimal_or_none(balance_sheet.get("total_equity"))
    if explicit_equity is not None:
        return explicit_equity

    total_assets = _decimal_or_none(balance_sheet.get("total_assets"))
    total_liabilities = _decimal_or_none(balance_sheet.get("total_liabilities"))
    if total_assets is not None and total_liabilities is not None:
        return total_assets - total_liabilities

    # Interest-bearing debt excludes trade creditors, tax and other liabilities.
    # Assets minus financial debt is not the accounting equity identity.

    return None


def default_methodology_justification(primary_basis: str) -> str:
    if primary_basis == "asset_based":
        return (
            "Voor dit profiel is gekozen voor een balansgedreven (substantie-)route, "
            "omdat de onderneming vooral wordt gewaardeerd op basis van haar activa en passiva."
        )
    return (
        "Voor dit profiel is gekozen voor de standaard SME-route met marktmultiples en DCF "
        "als primaire waarderingsankers."
    )


def _string_list(value: object) -> list[str]:
    return [str(item) for item in value] if isinstance(value, list) else []


def _saas_validation_flag_from_raw(
    raw: Mapping[str, object],
) -> Optional["SaasValidationFlag"]:
    from src.domain.saas_input_validation import SaasValidationFlag

    try:
        return cast(
            "SaasValidationFlag",
            SaasValidationFlag(
                field=str(raw.get("field") or "saas"),
                code=str(raw.get("issue") or raw.get("code") or "saas_validation"),
                severity=str(raw.get("severity") or "warning"),
                message=str(raw.get("message") or ""),
                value=raw.get("value"),
                expected=raw.get("benchmark") or raw.get("expected"),
            ),
        )
    except Exception:
        return None


def _rehydrate_saas_validation_report(
    saas_analysis: Mapping[str, object],
) -> Optional["SaasValidationReport"]:
    from src.domain.saas_input_validation import SaasValidationReport

    validation_flags_raw = saas_analysis.get("validation_flags") or []
    if not isinstance(validation_flags_raw, list):
        return None

    flags: list[SaasValidationFlag] = []
    for raw in validation_flags_raw:
        if not isinstance(raw, Mapping):
            continue
        flag = _saas_validation_flag_from_raw(raw)
        if flag is not None:
            flags.append(flag)
    return cast("SaasValidationReport", SaasValidationReport(flags=flags))


def _rehydrate_saas_eligibility_verdict(
    saas_analysis: Mapping[str, object],
) -> Optional["SaasEligibilityVerdict"]:
    from src.domain.saas_eligibility import SaasEligibilityVerdict

    elig_raw = saas_analysis.get("eligibility")
    if not isinstance(elig_raw, Mapping):
        return None

    try:
        signals = elig_raw.get("signals") or {}
        suggested = elig_raw.get("suggested_alternative_method")
        return cast(
            "SaasEligibilityVerdict",
            SaasEligibilityVerdict(
                eligible=bool(elig_raw.get("eligible", False)),
                recurring_share=_decimal_or_none(elig_raw.get("recurring_share")),
                arr=_decimal_or_none(elig_raw.get("arr")),
                blocking_reasons=_string_list(elig_raw.get("blocking_reasons") or []),
                warnings=_string_list(elig_raw.get("warnings") or []),
                signals=dict(signals) if isinstance(signals, Mapping) else {},
                suggested_alternative_method=str(suggested) if suggested is not None else None,
            ),
        )
    except Exception:
        return None


def _saas_artifact_numbers_are_valid(
    *,
    arr: Optional[Decimal],
    arr_multiple: Optional[Decimal],
    ebitda_adjustment_factor: Optional[Decimal],
) -> bool:
    return (
        arr is not None
        and arr > 0
        and arr_multiple is not None
        and arr_multiple > 0
        and ebitda_adjustment_factor is not None
        and ebitda_adjustment_factor > 0
    )


def _saas_adjustment_breakdown_rows(saas_analysis: Mapping[str, object]) -> list[dict[str, object]]:
    adjustment_breakdown = saas_analysis.get("adjustment_breakdown")
    return adjustment_breakdown if isinstance(adjustment_breakdown, list) else []


def _saas_artifact_has_diagnostics(
    *,
    eligibility_verdict: Optional["SaasEligibilityVerdict"],
    validation_report: Optional["SaasValidationReport"],
) -> bool:
    return eligibility_verdict is not None or bool(getattr(validation_report, "flags", None))


def saas_adjustment_from_artifact(
    saas_analysis: Optional[Mapping[str, object]],
) -> Optional[SaasAdjustmentResult]:
    """Re-hydrate a ``SaasAdjustmentResult`` from the Step-0 artifact dict.

    Round-trips the eligibility + validation diagnostics so downstream
    consumers (ARR method, EBITDA factor, adaptive secondary-key gate)
    receive the same context the live computation produced. Without
    this, the orchestrator's pre-computed artifact path would silently
    strip the diagnostic chain on re-hydration.
    """
    if not isinstance(saas_analysis, Mapping):
        return None

    metrics = saas_analysis.get("metrics")
    if not isinstance(metrics, Mapping):
        return None
    metrics_payload = dict(metrics)

    arr = _decimal_or_none(metrics.get("arr"))
    arr_multiple = _decimal_or_none(saas_analysis.get("arr_multiple"))
    ebitda_adjustment_factor = _decimal_or_none(saas_analysis.get("ebitda_adjustment_factor"))
    validation_report = _rehydrate_saas_validation_report(saas_analysis)
    eligibility_verdict = _rehydrate_saas_eligibility_verdict(saas_analysis)
    adjustment_rows = _saas_adjustment_breakdown_rows(saas_analysis)

    # When the artifact wasn't applicable, surface diagnostics rather
    # than dropping the object — this is what lets the ARR method emit
    # a structured unavailable_reason on the round-trip path.
    is_applicable = bool(saas_analysis.get("applicable", True))
    has_diagnostics = _saas_artifact_has_diagnostics(
        eligibility_verdict=eligibility_verdict,
        validation_report=validation_report,
    )

    if not _saas_artifact_numbers_are_valid(
        arr=arr,
        arr_multiple=arr_multiple,
        ebitda_adjustment_factor=ebitda_adjustment_factor,
    ):
        # Cannot compute ARR — but if we have diagnostics, return a
        # non-saas result that still carries them.
        if has_diagnostics:
            return SaasAdjustmentResult(
                is_saas=False,
                arr=arr,
                arr_multiple=None,
                ebitda_adjustment_factor=Decimal("1"),
                computed_metrics=metrics_payload,
                adjustment_breakdown=adjustment_rows,
                eligibility=eligibility_verdict,
                validation=validation_report,
            )
        return None

    return SaasAdjustmentResult(
        is_saas=is_applicable,
        arr=arr,
        arr_multiple=arr_multiple,
        ebitda_adjustment_factor=ebitda_adjustment_factor,
        computed_metrics=metrics_payload,
        adjustment_breakdown=adjustment_rows,
        eligibility=eligibility_verdict,
        validation=validation_report,
    )
