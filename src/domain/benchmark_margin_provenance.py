"""Provenance grading for the industry EBITDA-margin benchmark.

WHY THIS EXISTS
---------------
`upswitch_business_types.business_types` stores the sector margin as three
columns: `typical_ebitda_margin_min` / `_median` / `_max` (percent units).
Across the live 197 rows:

    * 149 rows carry ``median = 15.00`` -- the seeded default -- and 147 of
      those carry NULL for BOTH `_min` and `_max`.
    *  27 rows carry a hand-set median (18, 22, 25, 28 ...) with NULL min/max.
    *  10 rows carry a real band (accounting 22/28/38, saas -20/10/40).
    *  13 rows carry no median at all.

There is NO provenance column for the margin: `multiples_source` and
`sme_calibration_source` describe the *multiples*, and read ``BAYESIAN_UPDATE``
identically across all three cohorts. The band shape is therefore the only
signal that distinguishes a measurement from a placeholder.

That is what this module encodes, so every consumer applies one rule:

    measured        real dispersion (a min below and/or a max above the median).
                    Only this grade may drive a confidence penalty -- you cannot
                    call a margin "deviant" without knowing the spread.
    point_estimate  a hand-set median with no dispersion. May inform, must not
                    penalise.
    placeholder     the bare seed default (15%) with no dispersion, or a band so
                    incoherent it is evidence of corruption. Treat as ABSENT.
    absent          no usable median.

Note that `bakery` and `bar-pub` are genuinely 15% AND carry a band, so a naive
"median == 15" sentinel would silence two real sectors. Requiring dispersion
keeps them live.

Grading is deliberately asymmetric: an explicit "this is a default" string can
DOWNGRADE a band, but no string can PROMOTE a band-less median to `measured`.
Titan does not send a margin-provenance field today; when it starts, promotion
must be wired to that real vocabulary on purpose, not inferred from a substring.

Live consequence of not having this: a Belgian wholesale distributor with a
textbook-normal 2.6% margin was told it deviated from a "15.0% industry typical"
and was docked to 59/100 "low" confidence.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Optional

__all__ = [
    "SEED_DEFAULT_MARGIN",
    "IndustryMarginBenchmark",
    "resolve_industry_margin_benchmark",
]

# `business_types.typical_ebitda_margin_median` seed default (15.00), in the
# normalized fraction form used throughout this module.
SEED_DEFAULT_MARGIN = Decimal("0.15")

GRADE_MEASURED = "measured"
GRADE_POINT_ESTIMATE = "point_estimate"
GRADE_PLACEHOLDER = "placeholder"
GRADE_ABSENT = "absent"

# Honoured only as a DOWNGRADE (see module docstring): a band that declares
# itself a default is a placeholder whatever its shape.
_PLACEHOLDER_SOURCE_TOKENS = ("default", "placeholder", "seed", "assumed", "stub")
# Read from the band mapping only. `industry_benchmarks` is a blob of sibling
# benchmarks (ev_ebitda, ev_revenue, pe_ratio ...), so a `source` at its top
# level describes the payload, not this margin.
_SOURCE_KEYS = ("margin_source", "source", "provenance")


@dataclass(frozen=True)
class IndustryMarginBenchmark:
    """A resolved industry margin benchmark, graded by what it actually is.

    ``median``/``minimum``/``maximum`` are normalized to fraction form (0.15).
    """

    median: Optional[Decimal]
    minimum: Optional[Decimal]
    maximum: Optional[Decimal]
    grade: str
    reason: str
    source: Optional[str] = None

    @property
    def is_measured(self) -> bool:
        """True only for a real distribution. Gates the confidence penalty."""
        return self.grade == GRADE_MEASURED

    @property
    def is_comparable(self) -> bool:
        """True when a deviation may be *reported* (never implies a penalty)."""
        return self.grade in (GRADE_MEASURED, GRADE_POINT_ESTIMATE)

    @property
    def median_pct(self) -> Optional[float]:
        return float(self.median * 100) if self.median is not None else None

    @property
    def min_pct(self) -> Optional[float]:
        return float(self.minimum * 100) if self.minimum is not None else None

    @property
    def max_pct(self) -> Optional[float]:
        return float(self.maximum * 100) if self.maximum is not None else None


def _decimal_or_none(value: object) -> Optional[Decimal]:
    if value is None or isinstance(value, bool):
        return None
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    return parsed if parsed.is_finite() else None


def _declared_source(band: Mapping[str, object]) -> Optional[str]:
    for key in _SOURCE_KEYS:
        raw = band.get(key)
        if isinstance(raw, str) and raw.strip():
            return raw.strip()
    return None


def _declared_margin_basis(band: Mapping[str, object]) -> Optional[str]:
    """How the sender says the band was obtained, if it says at all.

    Titan sends `basis` on `typicalEbitdaMargin` from
    `business_types.typical_ebitda_margin_basis`: measured | curated |
    derived_from_multiples. `None` means an older payload that predates the
    column, in which case we fall back to grading on shape.
    """
    raw = band.get("basis")
    if isinstance(raw, str) and raw.strip():
        return raw.strip().lower()
    return None


def _absent(reason: str) -> IndustryMarginBenchmark:
    return IndustryMarginBenchmark(None, None, None, GRADE_ABSENT, reason)


def resolve_industry_margin_benchmark(benchmarks: object) -> IndustryMarginBenchmark:
    """Resolve ``industry_benchmarks["typical_ebitda_margin"]`` and grade it.

    Accepts the band-dict shape ({"min","median","max"}), a bare scalar
    (back-compat), a missing key, or garbage. Never raises.
    """
    if not isinstance(benchmarks, Mapping):
        return _absent("no_benchmarks")

    raw_band = benchmarks.get("typical_ebitda_margin")
    if raw_band is None:
        return _absent("no_typical_margin")

    if isinstance(raw_band, Mapping):
        band: Mapping[str, object] = raw_band
        raw_median = _decimal_or_none(band.get("median"))
        raw_min = _decimal_or_none(band.get("min"))
        raw_max = _decimal_or_none(band.get("max"))
    else:
        # Bare scalar: a point estimate with no dispersion by construction.
        band = {}
        raw_median = _decimal_or_none(raw_band)
        raw_min = raw_max = None

    if raw_median is None or raw_median <= 0:
        return _absent("no_median")

    # SCALE ONCE, FROM THE MEDIAN. The DB stores percent units and `saas`
    # carries min = -20, so scaling each bound independently on a ">1" test
    # would read -20 as -2000%. The median fixes the scale for all three.
    divisor = Decimal("100") if raw_median > Decimal("1.0") else Decimal("1")
    median = raw_median / divisor
    minimum = raw_min / divisor if raw_min is not None else None
    maximum = raw_max / divisor if raw_max is not None else None

    source = _declared_source(band)
    if source and any(token in source.lower() for token in _PLACEHOLDER_SOURCE_TOKENS):
        return IndustryMarginBenchmark(
            median, minimum, maximum, GRADE_PLACEHOLDER, "declared_placeholder", source
        )

    # A band only counts if it is coherent AND carries dispersion. An incoherent
    # band (inverted bounds, or a margin outside +/-100%) is evidence of
    # corruption, not spread.
    bounds_ordered = (minimum is None or minimum <= median) and (
        maximum is None or maximum >= median
    )
    in_range = all(
        Decimal("-1") <= value <= Decimal("1")
        for value in (median, minimum, maximum)
        if value is not None
    )
    has_dispersion = (minimum is not None and minimum < median) or (
        maximum is not None and maximum > median
    )

    # A DECLARED basis outranks the shape heuristic.
    #
    # Shape alone is only evidence of measurement when bands are rare. Since the
    # 20260821 migration every business type carries a min/median/max, and 185 of
    # 195 were DERIVED from the multiples (EV/Revenue over EV/EBITDA) rather than
    # measured. Grading those as `measured` on shape would let a derived band both
    # dock the customer's confidence score and print "the measured sector band
    # is ...", which is the same false assertion the 15% placeholder made.
    declared_basis = _declared_margin_basis(band)
    if has_dispersion and bounds_ordered and in_range and declared_basis is not None:
        if declared_basis == "measured":
            return IndustryMarginBenchmark(
                median, minimum, maximum, GRADE_MEASURED, "measured_band", source
            )
        # Coherent and useful for context, but not evidence. `point_estimate`
        # already means "report it, never penalise on it".
        return IndustryMarginBenchmark(
            median, minimum, maximum, GRADE_POINT_ESTIMATE, f"declared_{declared_basis}", source
        )

    if has_dispersion and bounds_ordered and in_range:
        return IndustryMarginBenchmark(
            median, minimum, maximum, GRADE_MEASURED, "measured_band", source
        )
    if (minimum is not None or maximum is not None) and not (bounds_ordered and in_range):
        return IndustryMarginBenchmark(
            median, minimum, maximum, GRADE_PLACEHOLDER, "incoherent_band", source
        )
    if median == SEED_DEFAULT_MARGIN:
        return IndustryMarginBenchmark(
            median, minimum, maximum, GRADE_PLACEHOLDER, "seed_default_no_dispersion", source
        )
    return IndustryMarginBenchmark(
        median, minimum, maximum, GRADE_POINT_ESTIMATE, "point_estimate_no_dispersion", source
    )
