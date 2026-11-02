"""Money + quantization helpers for the startup valuation engine.

Single source of truth so every leg (Berkus / Scorecard / VC / SaaS Forward)
quantizes EUR amounts and percentages exactly the same way.  All math
inside the package goes through these helpers — *floats are only used at
the JSON serialization boundary*, never inside the engine.

The package-wide invariants enforced here:

* Banker's rounding (``ROUND_HALF_EVEN``) inherited from the platform
  decimal context — see :mod:`src.utils.decimal_helpers`.
* All EUR amounts are quantized to two cents.  All percentages /
  multipliers are quantized to four decimal places (sufficient for
  weight matrices, conservative enough to round-trip through reports).
* :class:`LegResult` is the shared value object every leg can adapt
  itself into so the synthesis blender doesn't need to special-case
  shapes.

Thread-safety
-------------
Every helper here is a pure function over its arguments; no module-level
state mutates after import.  Safe to call from multiple coroutines /
threads without locks.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Dict, Iterable, Optional

#: Canonical quantizers — never instantiate ``Decimal("0.01")`` ad-hoc
#: inside the engine; reuse these so call-sites are grep-able and the
#: rounding behaviour is consistent.
Q_EUR: Decimal = Decimal("0.01")
"""Two-cents granularity used for every EUR amount in the engine."""

Q_RATE: Decimal = Decimal("0.0001")
"""Four-decimal granularity used for weights, multipliers and discounts."""

Q_PCT: Decimal = Decimal("0.01")
"""Two-decimal granularity used for human-facing percentages."""

ZERO: Decimal = Decimal("0")
ONE: Decimal = Decimal("1")
ONE_HUNDRED: Decimal = Decimal("100")


def q_eur(value: Decimal) -> Decimal:
    """Quantize a EUR amount to two cents using the platform context."""
    return Decimal(value).quantize(Q_EUR)


def q_rate(value: Decimal) -> Decimal:
    """Quantize a multiplier / weight / discount to four decimal places."""
    return Decimal(value).quantize(Q_RATE)


def q_pct(value: Decimal) -> Decimal:
    """Quantize a human-facing percentage to two decimal places."""
    return Decimal(value).quantize(Q_PCT)


def clamp(value: Decimal, *, low: Decimal, high: Decimal) -> Decimal:
    """Clamp ``value`` into ``[low, high]`` (inclusive)."""
    if value < low:
        return low
    if value > high:
        return high
    return value


def safe_decimal(value: Any, *, default: Decimal = ZERO) -> Decimal:
    """Coerce ``value`` to ``Decimal`` returning ``default`` on bad input.

    Used at the request-validation seam where Pydantic occasionally
    leaks ``None`` / ``""`` / ``"NaN"`` from a malformed payload.

    Float inputs go through ``Decimal(str(value))`` rather than the raw
    ``Decimal(float)`` constructor — the latter exposes the IEEE-754
    binary representation (e.g. ``Decimal(0.1)`` ≡
    ``Decimal('0.1000000000000000055511151231257827021181583404541015625')``)
    and silently propagates 56-digit garbage through the engine. Aligns
    with the platform helper at ``src.utils.decimal_helpers.to_decimal``.
    """
    if value is None or value == "":
        return default
    if isinstance(value, Decimal):
        out = value
    elif isinstance(value, bool):
        # Defensive: ``bool`` is a subclass of ``int`` so a stray ``True``
        # would otherwise be coerced to ``Decimal('1')``. Reject explicitly
        # so a payload bug surfaces as a default rather than a false +€1.
        return default
    elif isinstance(value, int):
        out = Decimal(value)
    elif isinstance(value, float):
        # Pre-screen the float for NaN/Infinity *before* the str() round-trip
        # — ``str(float('nan'))`` gives ``'nan'`` which Decimal would happily
        # parse as Decimal('NaN'), which our downstream quantizers can't handle.
        if value != value or value in (float("inf"), float("-inf")):
            return default
        try:
            out = Decimal(str(value))
        except (ArithmeticError, TypeError, ValueError):
            return default
    else:
        try:
            out = Decimal(value)
        except (ArithmeticError, TypeError, ValueError):
            return default
    if out.is_nan() or out.is_infinite():
        return default
    return out


def safe_float(value: Any) -> Optional[float]:
    """Edge-of-engine float adapter for JSON payloads.

    Returns ``None`` when the value can't be coerced — *deliberate*
    behaviour: callers serialize the result into JSON and ``None``
    becomes ``null`` (clearer in the report than ``0.0``).
    """
    if value is None:
        return None
    if isinstance(value, Decimal):
        if value.is_nan() or value.is_infinite():
            return None
        return float(value)
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    if out != out:  # NaN check — float('nan') is the only value != itself
        return None
    return out


# ---------------------------------------------------------------------------
# Unified leg adapter
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LegResult:
    """Canonical shape every startup-valuation leg adapts itself into.

    The synthesis blender consumes :class:`LegResult` instances rather
    than the four bespoke leg dataclasses so that adding a 5th leg in
    the future is trivial (just produce another ``LegResult``).

    Attributes
    ----------
    key:
        Stable machine name (``"berkus"`` / ``"scorecard"`` / ``"vc"`` /
        ``"saas_forward"``).  Drives weight lookups in
        :data:`synthesis._STAGE_WEIGHTS`.
    label:
        Human-readable label for the football field row + report.
    pre_money:
        Quantized EUR pre-money valuation produced by the leg.
        ``Decimal('0')`` ⇒ leg is unavailable / didn't contribute.
    available:
        ``True`` when the leg actually contributed math to the blend.
        Berkus and Scorecard are *always* available (they default-out
        to a number); VC and SaaS Forward gate themselves on having
        forward-looking inputs.
    unavailable_reason:
        Localized (Dutch) one-liner explaining why an unavailable leg
        was dropped.  Surfaced under the football field row in the
        report so the founder isn't left guessing.
    confidence:
        Optional ``[0, 1]`` self-assessed confidence the leg attaches
        to its own number — currently advisory only (synthesis ignores
        it) but reserved so a future revision can multiplicatively
        de-weight low-confidence legs without a schema change.
    """

    key: str
    label: str
    pre_money: Decimal
    available: bool
    unavailable_reason: Optional[str] = None
    confidence: Optional[Decimal] = None
    assumptions: Dict[str, Any] = field(default_factory=dict)


def make_leg_result(
    *,
    key: str,
    label: str,
    pre_money: Decimal,
    available: Optional[bool] = None,
    unavailable_reason: Optional[str] = None,
    confidence: Optional[Decimal] = None,
    assumptions: Optional[Dict[str, Any]] = None,
) -> LegResult:
    """Construct a :class:`LegResult` with sensible defaults.

    When ``available`` is omitted we infer it from ``pre_money > 0`` —
    that's the same heuristic the synthesis blender uses, so callers
    get the ergonomic behaviour without needing to repeat it.
    """
    quantized = q_eur(pre_money)
    derived_available = available if available is not None else quantized > ZERO
    return LegResult(
        key=key,
        label=label,
        pre_money=quantized,
        available=derived_available,
        unavailable_reason=unavailable_reason,
        confidence=confidence,
        assumptions=assumptions or {},
    )


def sum_decimals(values: Iterable[Decimal]) -> Decimal:
    """Sum a sequence of ``Decimal`` values without falling back to float.

    The built-in ``sum`` works for ``Decimal`` but its ``start`` defaults
    to ``int(0)`` which sometimes triggers a noisy ``DeprecationWarning``
    on Python 3.13 when mixing types — this helper makes the contract
    explicit (``Decimal`` in, ``Decimal`` out).
    """
    total = ZERO
    for value in values:
        total += value
    return total
