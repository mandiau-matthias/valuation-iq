"""Financial-story report context helpers."""

import statistics
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional, Protocol, TypeAlias, cast

from src.services.reports.protocol_adapter import _attr, _unwrap

JsonMap: TypeAlias = dict[str, object]
MultiYearRows: TypeAlias = list[JsonMap]
NumericScalar: TypeAlias = int | float | str | Decimal


class FinancialStoryTranslations(Protocol):
    nwc_disclosure_unavailable: str
    nwc_disclosure_neutral: str
    nwc_disclosure_surplus: str
    nwc_disclosure_deficit: str
    exec_volatility_chip_label: str
    exec_volatility_chip_note_template: str


def _float_or_zero(value: object) -> float:
    return float(cast(NumericScalar, value or 0))


def _required_float(row: JsonMap, key: str) -> float:
    return float(cast(NumericScalar, row[key]))


# Peak/trough chip threshold — raised from 2× (May 2026) to 3× so monotonic
# SME growth profiles (e.g. doubling EBITDA over 4 years) are not flagged as
# volatile. Loss years always fire regardless of ratio.
VOLATILITY_RANGE_RATIO_THRESHOLD = 3.0

# Align with Step 2.5 MarginVolatilityAnalyzer.MEDIUM_VOLATILITY_THRESHOLD.
_SMOOTH_GROWTH_MARGIN_STDEV_PP = 3.0

# When normalisations exceed this share of reported EBITDA on the peak year,
# recompute the peak/trough ratio on reported EBITDA so one-off add-backs do
# not inflate the dispersion statistic.
_NORMALIZATION_SPIKE_THRESHOLD = 0.25


@dataclass(frozen=True)
class _VolatilityRange:
    ratio: Optional[float]
    driver: Optional[str] = None


def format_nwc_disclosure(response: Optional[object], t: FinancialStoryTranslations) -> str:
    """Render the localized working-capital sentence shown in the EV-to-equity callout."""
    nwc = _attr(response, "nwc_normalization", None) if response else None
    nwc_dict = _unwrap(nwc) if nwc is not None else None
    if not isinstance(nwc_dict, dict) or "surplus_deficit" not in nwc_dict:
        return t.nwc_disclosure_unavailable

    try:
        surplus_deficit = Decimal(str(nwc_dict.get("surplus_deficit", 0) or 0))
        target_pct = Decimal(str(nwc_dict.get("target_nwc_pct", 0) or 0))
        actual_pct = Decimal(str(nwc_dict.get("actual_nwc_pct", 0) or 0))
    except (TypeError, ValueError, ArithmeticError):
        return t.nwc_disclosure_unavailable

    threshold = abs(target_pct) / Decimal("10") if target_pct else Decimal("0.5")
    is_neutral = abs(surplus_deficit) <= max(Decimal("1000"), threshold * Decimal("100"))

    actual_pct_display = f"{float(actual_pct):.0f}"
    target_pct_display = f"{float(target_pct):.0f}"

    if is_neutral:
        return t.nwc_disclosure_neutral.format(
            actual_pct=actual_pct_display,
            target_pct=target_pct_display,
        )

    absolute = abs(surplus_deficit)
    if absolute >= Decimal("1000000"):
        amount = f"€{float(absolute) / 1_000_000:.1f}M"
    else:
        amount = f"€{float(absolute) / 1_000:.0f}K"

    template = t.nwc_disclosure_surplus if surplus_deficit > 0 else t.nwc_disclosure_deficit
    return template.format(
        amount=amount,
        actual_pct=actual_pct_display,
        target_pct=target_pct_display,
    )


def _reported_ebitda(row: JsonMap) -> float:
    if row.get("reported_ebitda") is not None:
        return _float_or_zero(row.get("reported_ebitda"))
    return _float_or_zero(row.get("normalized_ebitda"))


def _reported_margin_pct(row: JsonMap) -> Optional[float]:
    revenue = _float_or_zero(row.get("revenue"))
    reported = _reported_ebitda(row)
    if revenue <= 0:
        return None
    return reported / revenue * 100


def _is_normalization_spike(row: JsonMap) -> bool:
    reported = _reported_ebitda(row)
    if reported <= 0:
        return False
    adjustment = _float_or_zero(row.get("adjustment_total"))
    if adjustment == 0 and row.get("has_adjustments"):
        normalized = _float_or_zero(row.get("normalized_ebitda"))
        adjustment = normalized - reported
    return abs(adjustment) / reported > _NORMALIZATION_SPIKE_THRESHOLD


def _ratio_for_peak_trough(
    positives: list[JsonMap],
    *,
    value_key: str = "normalized_ebitda",
) -> Optional[float]:
    if len(positives) < 2:
        return None

    def _value(row: JsonMap) -> float:
        if value_key == "reported":
            return _reported_ebitda(row)
        return _required_float(row, "normalized_ebitda")

    min_pos = min(positives, key=_value)
    max_pos = max(positives, key=_value)
    min_v = _value(min_pos)
    if min_v <= 0:
        return None
    return _value(max_pos) / min_v


def _is_smooth_growth_profile(positives: list[JsonMap]) -> bool:
    """True when reported EBITDA trends monotonically with stable margins."""
    reported_rows = sorted(
        [row for row in positives if _reported_ebitda(row) > 0],
        key=lambda row: int(row.get("year") or 0),
    )
    if len(reported_rows) < 2:
        return False

    reported_values = [_reported_ebitda(row) for row in reported_rows]
    increasing = all(
        reported_values[index] < reported_values[index + 1]
        for index in range(len(reported_values) - 1)
    )
    decreasing = all(
        reported_values[index] > reported_values[index + 1]
        for index in range(len(reported_values) - 1)
    )
    if not increasing and not decreasing:
        return False

    margins = [margin for row in reported_rows if (margin := _reported_margin_pct(row)) is not None]
    if len(margins) < 2:
        return increasing or decreasing

    margin_stdev = statistics.stdev(margins)
    return margin_stdev <= _SMOOTH_GROWTH_MARGIN_STDEV_PP


def _is_material_loss_year(row: JsonMap) -> bool:
    """Loss years with revenue — not empty placeholder rows (0/0)."""
    normalized = _float_or_zero(row.get("normalized_ebitda"))
    if normalized >= 0:
        return False
    return _float_or_zero(row.get("revenue")) > 0


def _is_placeholder_financial_row(row: JsonMap) -> bool:
    """Skip wizard placeholder years (zero revenue and zero EBITDA)."""
    revenue = _float_or_zero(row.get("revenue"))
    normalized = _float_or_zero(row.get("normalized_ebitda"))
    reported = _reported_ebitda(row)
    return revenue <= 0 and normalized == 0 and reported == 0


def _valid_volatility_rows(multi_year: MultiYearRows) -> list[JsonMap]:
    return [
        row
        for row in multi_year
        if isinstance(row, dict)
        and row.get("normalized_ebitda") is not None
        and row.get("year") is not None
        and not _is_placeholder_financial_row(row)
    ]


def _positive_normalized_rows(rows: list[JsonMap]) -> list[JsonMap]:
    return [row for row in rows if _float_or_zero(row.get("normalized_ebitda")) > 0]


def _normalization_adjusted_range(positives: list[JsonMap]) -> _VolatilityRange:
    if len(positives) < 2:
        return _VolatilityRange(ratio=None)

    range_ratio = _ratio_for_peak_trough(positives)
    max_norm_row = max(
        positives,
        key=lambda row: _required_float(row, "normalized_ebitda"),
    )
    if range_ratio is None or not _is_normalization_spike(max_norm_row):
        return _VolatilityRange(ratio=range_ratio)

    reported_ratio = _ratio_for_peak_trough(positives, value_key="reported")
    if reported_ratio is None:
        return _VolatilityRange(ratio=range_ratio)
    return _VolatilityRange(ratio=reported_ratio, driver="normalization")


def _normalized_ebitda_bounds(rows: list[JsonMap]) -> tuple[JsonMap, JsonMap]:
    min_row = min(rows, key=lambda row: _required_float(row, "normalized_ebitda"))
    max_row = max(rows, key=lambda row: _required_float(row, "normalized_ebitda"))
    return min_row, max_row


def _is_range_above_volatility_threshold(range_ratio: Optional[float]) -> bool:
    return range_ratio is not None and range_ratio >= VOLATILITY_RANGE_RATIO_THRESHOLD


def _is_volatile_ebitda_window(
    *,
    has_loss_year: bool,
    range_ratio: Optional[float],
    positives: list[JsonMap],
) -> bool:
    if has_loss_year:
        return True
    return _is_range_above_volatility_threshold(range_ratio) and not _is_smooth_growth_profile(
        positives
    )


def _margin_or_none(row: JsonMap) -> Optional[float]:
    if row.get("ebitda_margin") is None:
        return None
    return _required_float(row, "ebitda_margin")


def _is_growth_ramp(positives: list[JsonMap]) -> bool:
    """True when normalized EBITDA rises monotonically from the earliest year.

    A young company ramping from a low or near-breakeven start year produces a
    large peak/trough ratio that reads as 'volatility' but is really growth. We
    tolerate a flat/plateau year (e.g. a duplicated latest year) so a single
    repeated value does not break detection. The trough must be the earliest
    year — a low *final* year is a decline, not a ramp.
    """
    if len(positives) < 3:
        return False
    rows = sorted(positives, key=lambda row: int(row.get("year") or 0))
    values = [_required_float(row, "normalized_ebitda") for row in rows]
    non_decreasing = all(values[index] <= values[index + 1] for index in range(len(values) - 1))
    rises = values[-1] > values[0]
    trough_is_earliest = values[0] == min(values)
    return non_decreasing and rises and trough_is_earliest


def detect_duplicate_consecutive_years(multi_year: MultiYearRows) -> Optional[JsonMap]:
    """Flag consecutive displayed years with identical revenue AND EBITDA.

    Two book years matching to the cent is a data-entry artifact (a duplicated
    year), not real history — it silently double-counts a year in the weighted-
    EBITDA basis. We surface it so the advisor/owner verifies the figures rather
    than treating the duplicate as genuine. Returns the offending year pair, or
    None when no consecutive duplicate is present.
    """
    rows = [row for row in (multi_year or []) if isinstance(row, dict) and row.get("year") is not None]
    rows.sort(key=lambda row: int(row.get("year") or 0))
    for earlier, later in zip(rows, rows[1:]):
        rev_a = _float_or_zero(earlier.get("revenue"))
        rev_b = _float_or_zero(later.get("revenue"))
        eb_a = _float_or_zero(earlier.get("normalized_ebitda"))
        eb_b = _float_or_zero(later.get("normalized_ebitda"))
        if rev_a <= 0 and eb_a == 0:
            continue  # skip empty wizard placeholder years
        if abs(rev_a - rev_b) < 0.01 and abs(eb_a - eb_b) < 0.01:
            return {"year_a": int(earlier.get("year")), "year_b": int(later.get("year"))}
    return None


def compute_ebitda_volatility(
    multi_year: MultiYearRows,
    t: FinancialStoryTranslations,
) -> Optional[JsonMap]:
    """Summarise normalized-EBITDA spread across the displayed multi-year window."""
    if not multi_year:
        return None

    numeric = _valid_volatility_rows(multi_year)
    if len(numeric) < 2:
        return None

    positives = _positive_normalized_rows(numeric)
    has_loss_year = any(_is_material_loss_year(row) for row in numeric)
    volatility_range = _normalization_adjusted_range(positives)
    min_row, max_row = _normalized_ebitda_bounds(numeric)

    is_volatile = _is_volatile_ebitda_window(
        has_loss_year=has_loss_year,
        range_ratio=volatility_range.ratio,
        positives=positives,
    )

    # Classify the dispersion driver so the report can reframe a young company's
    # growth ramp ("€10K → €78K") instead of presenting a bare, alarming peak/
    # trough ratio. A genuine loss year or a normalization spike keeps priority.
    driver = volatility_range.driver
    if driver is None and not has_loss_year and _is_growth_ramp(positives):
        driver = "growth_ramp"

    return {
        "is_volatile": is_volatile,
        "has_loss_year": has_loss_year,
        "min_ebitda": _required_float(min_row, "normalized_ebitda"),
        "max_ebitda": _required_float(max_row, "normalized_ebitda"),
        "min_year": int(min_row.get("year") or 0),
        "max_year": int(max_row.get("year") or 0),
        "range_ratio": volatility_range.ratio,
        "volatility_driver": driver,
        "min_margin_pct": _margin_or_none(min_row),
        "max_margin_pct": _margin_or_none(max_row),
        "chip_label": t.exec_volatility_chip_label,
        "chip_note_template": t.exec_volatility_chip_note_template,
    }
