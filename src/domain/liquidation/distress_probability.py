"""Altman Z'' financial screen; no fitted probability model is available.

The legacy function name is retained for callers. A discriminant score is
not a probability. Missing observations cannot be replaced by zero.
"""

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum

DISTRESS_SOURCES = ("Altman (2000), Predicting Financial Distress of Companies — Z'' score",)
SCORE_VERSION = "altman-z-double-prime.complete-inputs.v2"


class DistressZone(str, Enum):
    SAFE = "safe"
    GREY = "grey"
    DISTRESS = "distress"
    UNDETERMINED = "undetermined"


class DistressUnavailableReason(str, Enum):
    TOTAL_ASSETS_NON_POSITIVE = "DISTRESS_TOTAL_ASSETS_NON_POSITIVE"
    TOTAL_LIABILITIES_NON_POSITIVE = "DISTRESS_TOTAL_LIABILITIES_NON_POSITIVE"
    INSUFFICIENT_INPUTS = "DISTRESS_INSUFFICIENT_INPUTS"
    INVALID_INPUTS = "DISTRESS_INVALID_INPUTS"
    INCONSISTENT_BALANCE_SHEET = "DISTRESS_INCONSISTENT_BALANCE_SHEET"


@dataclass(frozen=True)
class DistressRatios:
    x1_working_capital_ratio: Decimal
    x2_retained_earnings_ratio: Decimal
    x3_ebit_ratio: Decimal
    x4_equity_to_liabilities: Decimal

    def to_dict(self) -> dict[str, float]:
        return {
            "x1_working_capital_ratio": float(self.x1_working_capital_ratio),
            "x2_retained_earnings_ratio": float(self.x2_retained_earnings_ratio),
            "x3_ebit_ratio": float(self.x3_ebit_ratio),
            "x4_equity_to_liabilities": float(self.x4_equity_to_liabilities),
        }


@dataclass(frozen=True)
class DistressAssessment:
    z_double_prime: Decimal | None
    zone: DistressZone
    probability_of_distress: None
    ratios: DistressRatios | None
    rationale: str
    sources: tuple[str, ...]
    available: bool
    unavailable_code: DistressUnavailableReason | None = None
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "model_version": SCORE_VERSION,
            "assessment_status": "financial_screen" if self.available else "not_assessed",
            "probability_status": "not_calibrated",
            "z_double_prime": (
                float(self.z_double_prime) if self.z_double_prime is not None else None
            ),
            "zone": self.zone.value,
            "probability_of_distress": None,
            "ratios": self.ratios.to_dict() if self.ratios is not None else None,
            "rationale": self.rationale,
            "sources": list(self.sources),
            "available": self.available,
            "unavailable_code": self.unavailable_code.value if self.unavailable_code else None,
            "warnings": list(self.warnings),
        }


def _unavailable(code: DistressUnavailableReason, rationale: str) -> DistressAssessment:
    return DistressAssessment(
        z_double_prime=None,
        zone=DistressZone.UNDETERMINED,
        probability_of_distress=None,
        ratios=None,
        rationale=rationale,
        sources=DISTRESS_SOURCES,
        available=False,
        unavailable_code=code,
        warnings=(rationale,),
    )


def assess_distress_probability(
    *,
    total_assets: Decimal | None,
    total_liabilities: Decimal | None,
    current_assets: Decimal | None = None,
    current_liabilities: Decimal | None = None,
    retained_earnings: Decimal | None = None,
    ebit: Decimal | None = None,
    total_equity: Decimal | None = None,
) -> DistressAssessment:
    """Compute the four-ratio screen from finite, same-period observations.

    Signed retained earnings, EBIT and equity are valid. Equity may be
    derived from complete accounting totals. Ratios and score retain Decimal
    precision; classification happens before any presentation rounding.
    This screen does not establish SME-specific predictive performance,
    a probability horizon, insolvency or a valuation premise.
    """
    values = (
        total_assets,
        total_liabilities,
        current_assets,
        current_liabilities,
        retained_earnings,
        ebit,
        total_equity,
    )
    if any(
        v is not None
        and (
            not isinstance(v, Decimal)
            or not v.is_finite()
            or abs(v) > Decimal("1e15")
            or (v != 0 and abs(v) < Decimal("1e-12"))
        )
        for v in values
    ):
        return _unavailable(
            DistressUnavailableReason.INVALID_INPUTS, "Invalid financial observation."
        )
    if total_assets is None or total_assets <= 0:
        return _unavailable(
            DistressUnavailableReason.TOTAL_ASSETS_NON_POSITIVE,
            "Z'' requires positive total assets.",
        )
    if total_liabilities is None or total_liabilities <= 0:
        return _unavailable(
            DistressUnavailableReason.TOTAL_LIABILITIES_NON_POSITIVE,
            "Z'' requires positive total liabilities for the equity ratio.",
        )
    if (
        current_assets is None
        or current_liabilities is None
        or retained_earnings is None
        or ebit is None
    ):
        return _unavailable(
            DistressUnavailableReason.INSUFFICIENT_INPUTS,
            "Z'' requires current assets, current liabilities, retained earnings and EBIT; missing is not zero.",
        )
    if not (0 <= current_assets <= total_assets and 0 <= current_liabilities <= total_liabilities):
        return _unavailable(
            DistressUnavailableReason.INCONSISTENT_BALANCE_SHEET,
            "Current assets/liabilities must reconcile within their accounting totals.",
        )
    derived_equity = total_assets - total_liabilities
    if total_equity is not None and abs(total_equity - derived_equity) > Decimal("0.01"):
        return _unavailable(
            DistressUnavailableReason.INCONSISTENT_BALANCE_SHEET,
            "Assets must equal liabilities plus equity (one-cent tolerance).",
        )
    warnings: tuple[str, ...] = (
        "Financial screen only; probability, valuation weights and local predictive accuracy are not calibrated.",
    )
    if total_equity is None:
        total_equity = derived_equity
        warnings += ("Equity derived from total assets less total liabilities.",)
    x1 = (current_assets - current_liabilities) / total_assets
    x2 = retained_earnings / total_assets
    x3 = ebit / total_assets
    x4 = total_equity / total_liabilities
    z = Decimal("6.56") * x1 + Decimal("3.26") * x2 + Decimal("6.72") * x3 + Decimal("1.05") * x4
    zone = (
        DistressZone.SAFE
        if z > Decimal("2.60")
        else (DistressZone.GREY if z >= Decimal("1.10") else DistressZone.DISTRESS)
    )
    return DistressAssessment(
        z_double_prime=z,
        zone=zone,
        probability_of_distress=None,
        ratios=DistressRatios(x1, x2, x3, x4),
        rationale="The financial score is a screening indicator, not a probability or a conclusion on going concern.",
        sources=DISTRESS_SOURCES,
        available=True,
        warnings=warnings,
    )
