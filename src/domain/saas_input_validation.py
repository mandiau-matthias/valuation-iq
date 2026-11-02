"""SaaS input plausibility & cross-validation — pure module, no I/O.

Catches the failure modes documented in the 2026-04-29 Defensibility Gate:
  - NRR=4 silently becoming 4% (typical real range: 70%–200%).
  - MRR×12 inconsistent with ARR (e.g. MRR €42k vs ARR €90k).
  - Gross margin / churn out of [0%, 100%].
  - Customer concentration above 100%.
  - ARR larger than total revenue (impossible).

Each finding is a ``SaasValidationFlag``: severity ``"error"`` blocks the ARR
method; ``"warning"`` lets it run but surfaces in the report. ``"info"``
flags are suggestions only.

The module is intentionally framework-free: callers (subcalculator, adjuster,
orchestrator) decide how to translate flags into ``triage_flags`` / report
sections / API responses.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Literal, Optional

from src.utils.adaptive_input_helpers import (
    get_business_context_decimal,
    get_business_context_percent,
)

Severity = Literal["info", "warning", "error"]


@dataclass(frozen=True)
class SaasValidationFlag:
    """A single validation finding on the SaaS metrics block."""

    field: str
    code: str
    severity: Severity
    message: str
    value: Optional[float] = None
    expected: Optional[str] = None

    def to_triage_dict(self) -> dict[str, object]:
        """Project into the ``TriageFlag`` shape used by the API response."""
        return {
            "field": self.field,
            "issue": self.code,
            "severity": self.severity,
            "value": self.value,
            "benchmark": self.expected,
        }


@dataclass(frozen=True)
class SaasValidationReport:
    """Aggregate of validation flags across all SaaS inputs."""

    flags: list[SaasValidationFlag] = field(default_factory=list)

    @property
    def has_errors(self) -> bool:
        return any(f.severity == "error" for f in self.flags)

    @property
    def has_warnings(self) -> bool:
        return any(f.severity == "warning" for f in self.flags)

    def by_severity(self, severity: Severity) -> list[SaasValidationFlag]:
        return [f for f in self.flags if f.severity == severity]

    def to_payload(self) -> list[dict[str, object]]:
        return [f.to_triage_dict() for f in self.flags]


# ── Plausibility thresholds (Belgian SME tuned) ──────────────────────
# Sources: Vlerick SME benchmark (2023), KeyBanc SaaS Survey (2024 EU cut),
# OPEXEngine (2023). Public SaaS NRR distribution: P5 ≈ 0.85, P95 ≈ 1.40.

_NRR_MIN_PLAUSIBLE = Decimal("0.50")  # below this means SaaS is collapsing
_NRR_MAX_PLAUSIBLE = Decimal("2.00")  # above this is almost certainly mis-entered
_NRR_TYPICAL_LOW = Decimal("0.70")
_NRR_TYPICAL_HIGH = Decimal("1.50")

_GROSS_MARGIN_MIN = Decimal("0")
_GROSS_MARGIN_MAX = Decimal("1.00")  # by definition

_CHURN_MIN = Decimal("0")
_CHURN_MAX_PLAUSIBLE = Decimal("0.50")  # 50%/yr would be terminal
_CHURN_HARD_MAX = Decimal("1.00")

_CUSTOMER_CONCENTRATION_MAX = Decimal("1.00")
_CUSTOMER_CONCENTRATION_HIGH = Decimal("0.50")

# MRR×12 vs ARR consistency tolerance — 25% covers bookkeeping cadence drift
# without masking a unit-error (MRR vs ARR confusion).
_MRR_ARR_TOLERANCE = Decimal("0.25")

# ARR cannot exceed top-line revenue. Allow 5% slack for fiscal-period drift
# (e.g. ARR snapshot at year-end vs revenue averaged across the year).
_ARR_REVENUE_SLACK = Decimal("0.05")


@dataclass(frozen=True)
class _SaasInputValues:
    arr: Optional[Decimal]
    mrr: Optional[Decimal]
    nrr: Optional[Decimal]
    revenue_churn: Optional[Decimal]
    customer_churn: Optional[Decimal]
    gross_margin: Optional[Decimal]
    customer_concentration: Optional[Decimal]
    expansion_revenue: Optional[Decimal]
    arr_growth: Optional[Decimal]


def _flag(
    *,
    field: str,
    code: str,
    severity: Severity,
    message: str,
    value: Optional[Decimal] = None,
    expected: Optional[str] = None,
) -> SaasValidationFlag:
    return SaasValidationFlag(
        field=field,
        code=code,
        severity=severity,
        message=message,
        value=float(value) if value is not None else None,
        expected=expected,
    )


def _extract_saas_input_values(ctx: Mapping[str, object]) -> _SaasInputValues:
    return _SaasInputValues(
        arr=get_business_context_decimal(ctx, "saas_arr"),
        mrr=get_business_context_decimal(ctx, "saas_mrr"),
        nrr=get_business_context_percent(ctx, "saas_nrr_pct"),
        revenue_churn=get_business_context_percent(ctx, "saas_churn_pct"),
        customer_churn=get_business_context_percent(ctx, "saas_customer_churn_pct"),
        gross_margin=get_business_context_percent(ctx, "saas_gross_margin_pct"),
        customer_concentration=get_business_context_percent(ctx, "saas_customer_concentration_pct"),
        expansion_revenue=get_business_context_percent(ctx, "saas_expansion_revenue_pct"),
        arr_growth=get_business_context_percent(ctx, "saas_arr_growth_pct"),
    )


def _append_negative_recurring_amount_flags(
    flags: list[SaasValidationFlag],
    values: _SaasInputValues,
) -> None:
    if values.arr is not None and values.arr < 0:
        flags.append(
            _flag(
                field="saas_arr",
                code="negative_arr",
                severity="error",
                message="ARR cannot be negative.",
                value=values.arr,
            )
        )

    if values.mrr is not None and values.mrr < 0:
        flags.append(
            _flag(
                field="saas_mrr",
                code="negative_mrr",
                severity="error",
                message="MRR cannot be negative.",
                value=values.mrr,
            )
        )


def _append_mrr_arr_consistency_flags(
    flags: list[SaasValidationFlag],
    values: _SaasInputValues,
) -> None:
    if values.arr is None or values.arr <= 0:
        return
    if values.mrr is None or values.mrr <= 0:
        return

    implied_arr = values.mrr * Decimal("12")
    relative_gap = abs(implied_arr - values.arr) / values.arr
    if relative_gap <= _MRR_ARR_TOLERANCE:
        return
    flags.append(
        _flag(
            field="saas_mrr",
            code="mrr_arr_inconsistent",
            severity="warning",
            message=(
                f"MRR×12 (€{float(implied_arr):,.0f}) deviates "
                f"{float(relative_gap * 100):.0f}% from ARR "
                f"(€{float(values.arr):,.0f}). Verify which metric is authoritative."
            ),
            value=values.arr,
            expected=f"MRR×12 within ±{int(_MRR_ARR_TOLERANCE * 100)}% of ARR",
        )
    )


def _append_arr_revenue_flags(
    flags: list[SaasValidationFlag],
    values: _SaasInputValues,
    revenue: Optional[Decimal],
) -> None:
    if values.arr is None or values.arr <= 0:
        return
    if revenue is None or revenue <= 0:
        return
    if values.arr <= revenue * (Decimal("1") + _ARR_REVENUE_SLACK):
        return
    flags.append(
        _flag(
            field="saas_arr",
            code="arr_exceeds_revenue",
            severity="error",
            message=(
                f"ARR (€{float(values.arr):,.0f}) exceeds total revenue "
                f"(€{float(revenue):,.0f}). ARR is a subset of revenue."
            ),
            value=values.arr,
            expected=f"≤ €{float(revenue):,.0f}",
        )
    )


def _append_nrr_flags(flags: list[SaasValidationFlag], nrr: Optional[Decimal]) -> None:
    if nrr is None:
        return
    if nrr < _NRR_MIN_PLAUSIBLE:
        flags.append(
            _flag(
                field="saas_nrr_pct",
                code="nrr_implausibly_low",
                severity="error",
                message=(
                    f"Net Revenue Retention of {float(nrr * 100):.1f}% is below "
                    "the 50% floor seen in any going-concern SaaS. Did you mean "
                    f"{float(nrr * 100) + 100:.0f}% (i.e. enter as 1{int(nrr * 100):02d})?"
                ),
                value=nrr * Decimal("100"),
                expected="50%–200% (typical SaaS range 70%–150%)",
            )
        )
    elif nrr > _NRR_MAX_PLAUSIBLE:
        flags.append(
            _flag(
                field="saas_nrr_pct",
                code="nrr_implausibly_high",
                severity="warning",
                message=(
                    f"Net Revenue Retention of {float(nrr * 100):.1f}% is above the "
                    "200% ceiling typical for any SaaS — verify input."
                ),
                value=nrr * Decimal("100"),
                expected="≤ 200%",
            )
        )
    elif nrr < _NRR_TYPICAL_LOW or nrr > _NRR_TYPICAL_HIGH:
        flags.append(
            _flag(
                field="saas_nrr_pct",
                code="nrr_atypical",
                severity="info",
                message=(
                    f"Net Revenue Retention {float(nrr * 100):.1f}% is outside "
                    "the typical 70–150% range — interpret with care."
                ),
                value=nrr * Decimal("100"),
                expected="70%–150%",
            )
        )


def _append_gross_margin_flags(
    flags: list[SaasValidationFlag],
    gross_margin: Optional[Decimal],
) -> None:
    if gross_margin is None:
        return
    if _GROSS_MARGIN_MIN <= gross_margin <= _GROSS_MARGIN_MAX:
        return
    flags.append(
        _flag(
            field="saas_gross_margin_pct",
            code="gross_margin_out_of_range",
            severity="error",
            message=(
                f"Gross margin {float(gross_margin * 100):.1f}% is outside "
                "the [0%, 100%] valid range."
            ),
            value=gross_margin * Decimal("100"),
            expected="0%–100%",
        )
    )


def _append_churn_flags(
    flags: list[SaasValidationFlag],
    *,
    field: str,
    churn_value: Optional[Decimal],
) -> None:
    if churn_value is None:
        return
    if churn_value < _CHURN_MIN:
        flags.append(
            _flag(
                field=field,
                code="churn_negative",
                severity="error",
                message="Churn cannot be negative.",
                value=churn_value * Decimal("100"),
            )
        )
    elif churn_value > _CHURN_HARD_MAX:
        flags.append(
            _flag(
                field=field,
                code="churn_exceeds_100",
                severity="error",
                message="Annual churn cannot exceed 100%.",
                value=churn_value * Decimal("100"),
                expected="0%–100%",
            )
        )
    elif churn_value > _CHURN_MAX_PLAUSIBLE:
        flags.append(
            _flag(
                field=field,
                code="churn_implausibly_high",
                severity="warning",
                message=(
                    f"Annual churn {float(churn_value * 100):.1f}% indicates a "
                    "non-going-concern profile — verify input."
                ),
                value=churn_value * Decimal("100"),
                expected="≤ 50%",
            )
        )


def _append_churn_bounds_flags(
    flags: list[SaasValidationFlag],
    values: _SaasInputValues,
) -> None:
    _append_churn_flags(
        flags,
        field="saas_churn_pct",
        churn_value=values.revenue_churn,
    )
    _append_churn_flags(
        flags,
        field="saas_customer_churn_pct",
        churn_value=values.customer_churn,
    )


def _append_customer_concentration_flags(
    flags: list[SaasValidationFlag],
    customer_concentration: Optional[Decimal],
) -> None:
    if customer_concentration is None:
        return
    if customer_concentration < 0 or customer_concentration > _CUSTOMER_CONCENTRATION_MAX:
        flags.append(
            _flag(
                field="saas_customer_concentration_pct",
                code="concentration_out_of_range",
                severity="error",
                message=(
                    f"Customer concentration {float(customer_concentration * 100):.1f}% "
                    "is outside the [0%, 100%] valid range."
                ),
                value=customer_concentration * Decimal("100"),
                expected="0%–100%",
            )
        )
    elif customer_concentration > _CUSTOMER_CONCENTRATION_HIGH:
        flags.append(
            _flag(
                field="saas_customer_concentration_pct",
                code="concentration_high",
                severity="warning",
                message=(
                    f"Top-customer concentration {float(customer_concentration * 100):.1f}% "
                    "materially compresses the multiple."
                ),
                value=customer_concentration * Decimal("100"),
                expected="< 50% (each)",
            )
        )


def _append_expansion_revenue_flags(
    flags: list[SaasValidationFlag],
    expansion_revenue: Optional[Decimal],
) -> None:
    if expansion_revenue is None:
        return
    if Decimal("0") <= expansion_revenue <= Decimal("1"):
        return
    flags.append(
        _flag(
            field="saas_expansion_revenue_pct",
            code="expansion_out_of_range",
            severity="warning",
            message=(
                f"Expansion revenue {float(expansion_revenue * 100):.1f}% is "
                "outside the typical [0%, 100%] range."
            ),
            value=expansion_revenue * Decimal("100"),
            expected="0%–100%",
        )
    )


def _append_arr_growth_flags(
    flags: list[SaasValidationFlag],
    arr_growth: Optional[Decimal],
) -> None:
    if arr_growth is None:
        return
    if Decimal("-1.0") <= arr_growth <= Decimal("10"):
        return
    flags.append(
        _flag(
            field="saas_arr_growth_pct",
            code="arr_growth_implausible",
            severity="warning",
            message=(
                f"ARR growth {float(arr_growth * 100):.1f}% is outside the "
                "[-100%, +1000%] band — verify."
            ),
            value=arr_growth * Decimal("100"),
            expected="-100% to +1000%",
        )
    )


def validate_saas_inputs(
    *,
    business_context: Optional[Mapping[str, object]],
    revenue: Optional[Decimal] = None,
) -> SaasValidationReport:
    """Run every SaaS-specific plausibility & cross-field check.

    Pure function — no logging, no I/O, no exceptions on bad data.
    Returns a ``SaasValidationReport`` that callers translate into errors,
    warnings, or triage flags as appropriate to their layer.
    """
    flags: list[SaasValidationFlag] = []
    ctx = dict(business_context or {})
    values = _extract_saas_input_values(ctx)
    _append_negative_recurring_amount_flags(flags, values)
    _append_mrr_arr_consistency_flags(flags, values)
    _append_arr_revenue_flags(flags, values, revenue)
    _append_nrr_flags(flags, values.nrr)
    _append_gross_margin_flags(flags, values.gross_margin)
    _append_churn_bounds_flags(flags, values)
    _append_customer_concentration_flags(flags, values.customer_concentration)
    _append_expansion_revenue_flags(flags, values.expansion_revenue)
    _append_arr_growth_flags(flags, values.arr_growth)

    return SaasValidationReport(flags=flags)


def diagnostic_summary(report: SaasValidationReport) -> tuple[str, str]:
    """Render a one-line headline + multi-line detail string for logs/UI.

    Returns ``("", "")`` when the report is clean.
    """
    if not report.flags:
        return "", ""

    error_count = len(report.by_severity("error"))
    warn_count = len(report.by_severity("warning"))
    info_count = len(report.by_severity("info"))

    headline_parts: list[str] = []
    if error_count:
        headline_parts.append(f"{error_count} error(s)")
    if warn_count:
        headline_parts.append(f"{warn_count} warning(s)")
    if info_count:
        headline_parts.append(f"{info_count} note(s)")
    headline = "SaaS validation: " + ", ".join(headline_parts)

    detail_lines = [f"  [{f.severity.upper()}] {f.field}: {f.message}" for f in report.flags]
    detail = "\n".join(detail_lines)
    return headline, detail
