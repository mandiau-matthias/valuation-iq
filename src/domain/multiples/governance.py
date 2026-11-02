"""Centralized override governance — bounds + out-of-band flagging (BET-524).

ONE authority for the sane, basis-aware ranges every advisor lever is held to.
The rule the epic settled on: **full flexibility, fully traced.**

Two tiers of control:
  * **Absolute bounds** — a hard, basis-aware sanity range. Outside it the
    value is rejected (a 50x EBITDA SME multiple is never valid).
  * **Soft band vs the model** — inside the absolute range but far from the
    Upswitch model number. Allowed, but only with explicit advisor
    confirmation, and always stamped "out of band" in the dossier so a
    manipulated number stays defensible instead of silent.

The model baseline is always preserved alongside the advisor's value; this
module never mutates it.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

# Absolute basis-aware sanity ranges for an SME *multiple* (turns of earnings).
# Wide enough not to fight legitimate advisor judgment, tight enough to catch
# fat-finger / wrong-basis errors (e.g. an EBITDA multiple typed onto SDE).
MULTIPLE_BOUNDS_BY_BASIS: dict[str, tuple[Decimal, Decimal]] = {
    "EBITDA": (Decimal("1.0"), Decimal("20.0")),
    "SDE": (Decimal("0.5"), Decimal("6.0")),
    "EBIT": (Decimal("1.0"), Decimal("25.0")),
    "Revenue": (Decimal("0.1"), Decimal("10.0")),
}
_DEFAULT_MULTIPLE_BOUNDS = (Decimal("0.1"), Decimal("50.0"))

# Per-discount influence weight: 0 disables, 1 keeps the model, capped at 2x.
DISCOUNT_WEIGHT_BOUNDS = (Decimal("0"), Decimal("2"))

# Multiplicative discount-stack floor factor: never below 0.2 (an 80% haircut),
# never above 1.0 (a floor can't add value).
FLOOR_FACTOR_BOUNDS = (Decimal("0.2"), Decimal("1.0"))

# Soft band: an override more than ±60% away from the model number is "out of
# band" — allowed only with explicit confirmation, always flagged.
DEFAULT_SOFT_BAND = Decimal("0.60")


def _dec(value: object) -> Decimal | None:
    if value is None or value == "":
        return None
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def multiple_bounds_for_basis(basis: object) -> tuple[Decimal, Decimal]:
    token = str(basis or "").strip().upper()
    for key, bounds in MULTIPLE_BOUNDS_BY_BASIS.items():
        if key.upper() == token:
            return bounds
    return _DEFAULT_MULTIPLE_BOUNDS


@dataclass(frozen=True)
class BoundsVerdict:
    """The governance verdict for one advisor lever."""

    value: Decimal
    lower: Decimal
    upper: Decimal
    within_absolute: bool
    out_of_band: bool
    reason: str | None = None

    @property
    def allowed_without_confirmation(self) -> bool:
        return self.within_absolute and not self.out_of_band


def check_multiple(
    value: object,
    *,
    basis: object,
    model_value: object = None,
    soft_band: Decimal = DEFAULT_SOFT_BAND,
) -> BoundsVerdict:
    """Govern a multiple override (per-type or effective) against basis bounds.

    `within_absolute=False` ⇒ hard reject. `out_of_band=True` ⇒ allowed only
    with explicit confirmation, and stamped on the dossier.
    """
    lower, upper = multiple_bounds_for_basis(basis)
    parsed = _dec(value) or Decimal("0")
    within_absolute = lower <= parsed <= upper

    reason: str | None = None
    if not within_absolute:
        reason = (
            f"{parsed} is outside the sane {basis} multiple range "
            f"[{lower}, {upper}] — check the earnings basis."
        )

    out_of_band = False
    model = _dec(model_value)
    if within_absolute and model is not None and model > 0:
        deviation = abs(parsed - model) / model
        if deviation > soft_band:
            out_of_band = True
            reason = (
                f"{parsed}× deviates {round(float(deviation) * 100)}% from the "
                f"model {model}× (>±{round(float(soft_band) * 100)}%); "
                "requires advisor confirmation."
            )

    return BoundsVerdict(
        value=parsed,
        lower=lower,
        upper=upper,
        within_absolute=within_absolute,
        out_of_band=out_of_band,
        reason=reason,
    )


# The effective ("below-the-line") multiple is post-discount, so it can sit
# legitimately below the raw-multiple lower bound (a floored micro-business).
# Sanity range only; defensibility comes from the soft band vs the model.
EFFECTIVE_MULTIPLE_BOUNDS = (Decimal("0.1"), Decimal("50.0"))


def check_effective_multiple(
    value: object,
    *,
    model_value: object,
    soft_band: Decimal = DEFAULT_SOFT_BAND,
) -> BoundsVerdict:
    """Govern the effective (below-the-line) multiple override.

    Uses a wide absolute sanity range (it is post-discount) and the soft band
    vs the model effective multiple to decide out-of-band.
    """
    lower, upper = EFFECTIVE_MULTIPLE_BOUNDS
    parsed = _dec(value) or Decimal("0")
    within_absolute = lower <= parsed <= upper

    reason: str | None = None
    if not within_absolute:
        reason = f"Effective multiple {parsed} is outside the sane range [{lower}, {upper}]."

    out_of_band = False
    model = _dec(model_value)
    if within_absolute and model is not None and model > 0:
        deviation = abs(parsed - model) / model
        if deviation > soft_band:
            out_of_band = True
            reason = (
                f"Effective {parsed}× deviates {round(float(deviation) * 100)}% from the "
                f"model effective {model}× (>±{round(float(soft_band) * 100)}%); "
                "requires advisor confirmation."
            )

    return BoundsVerdict(
        value=parsed,
        lower=lower,
        upper=upper,
        within_absolute=within_absolute,
        out_of_band=out_of_band,
        reason=reason,
    )


def clamp_floor_factor(value: object) -> Decimal:
    lower, upper = FLOOR_FACTOR_BOUNDS
    parsed = _dec(value)
    if parsed is None:
        return upper
    return min(upper, max(lower, parsed))


def clamp_discount_weight(value: object) -> Decimal:
    lower, upper = DISCOUNT_WEIGHT_BOUNDS
    parsed = _dec(value)
    if parsed is None:
        return Decimal("1")
    return min(upper, max(lower, parsed))
