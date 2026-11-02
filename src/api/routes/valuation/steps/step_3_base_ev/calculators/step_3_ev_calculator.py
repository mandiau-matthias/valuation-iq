"""
Step 3 EV Calculator

Calculates enterprise values and extracts supporting data.
"""

from collections.abc import Mapping
from decimal import Decimal
from typing import Any, Dict, NamedTuple, Optional, Tuple

from src.utils.decimal_helpers import money_multiply, to_decimal
from src.utils.logging import get_logger

from ...step_utilities import extract_ebitda, extract_revenue

logger = get_logger(__name__)

NumericValue = str | int | float | Decimal | None
RawPercentiles = Tuple[NumericValue, NumericValue, NumericValue]
DecimalPercentiles = Tuple[Decimal, Decimal, Decimal]


def _optional_decimal(value: NumericValue) -> Optional[Decimal]:
    try:
        return to_decimal(value)
    except (TypeError, ValueError):
        return None


def _positive_decimal(value: NumericValue) -> Optional[Decimal]:
    converted = _optional_decimal(value)
    if converted is None or converted <= 0:
        return None
    return converted


def _positive_decimal_percentiles(raw_percentiles: RawPercentiles) -> Optional[DecimalPercentiles]:
    p25 = _positive_decimal(raw_percentiles[0])
    p50 = _positive_decimal(raw_percentiles[1])
    p75 = _positive_decimal(raw_percentiles[2])
    if p25 is None or p50 is None or p75 is None:
        return None
    return p25, p50, p75


def _percentiles_in_order(percentiles: DecimalPercentiles) -> bool:
    p25, p50, p75 = percentiles
    return p25 < p50 < p75


def _ordered_percentiles(percentiles: DecimalPercentiles) -> DecimalPercentiles:
    p25, p50, p75 = percentiles
    if _percentiles_in_order(percentiles):
        return p25, p50, p75

    low = min(percentiles)
    high = max(percentiles)
    median = p50
    if low >= median or median >= high:
        median = (low + high) / Decimal("2")
    return low, median, high


def _estimated_percentiles(median_multiple: Decimal) -> DecimalPercentiles:
    return (
        median_multiple * Decimal("0.8"),
        median_multiple,
        median_multiple * Decimal("1.2"),
    )


def _quality_adjusted_percentiles(
    percentiles: DecimalPercentiles, quality_adjustment: Decimal
) -> DecimalPercentiles:
    p25, p50, p75 = percentiles
    return _ordered_percentiles(
        (
            p25 + quality_adjustment,
            p50 + quality_adjustment,
            p75 + quality_adjustment,
        )
    )


def _select_revenue_percentiles(step2: Mapping[str, NumericValue]) -> RawPercentiles:
    p25 = step2.get("ev_revenue_p25")
    p50 = step2.get("ev_revenue_p50")
    fallback = step2.get("ev_revenue_multiple")

    if _positive_decimal(p50) is None:
        logger.warning(
            "⚠️ Step 3: ev_revenue_p50 missing/invalid from Step 2, falling back to median",
            extra={
                "step_number": 3,
                "ev_revenue_p50_original": step2.get("ev_revenue_p50"),
                "ev_revenue_multiple_fallback": fallback,
            },
        )
        p50 = fallback
    else:
        logger.info(
            "✅ Step 3: Using ev_revenue_p50 from Step 2",
            extra={"step_number": 3, "ev_revenue_p50": p50},
        )

    return p25, p50, step2.get("ev_revenue_p75")


def _scaled_ebitda_band(
    calibrated: NumericValue,
    raw_p25: NumericValue,
    raw_p50: NumericValue,
    raw_p75: NumericValue,
) -> Tuple[Decimal, Decimal]:
    calibrated_decimal = to_decimal(calibrated)
    p25 = _optional_decimal(raw_p25)
    p50 = _positive_decimal(raw_p50)
    p75 = _optional_decimal(raw_p75)

    if p25 is not None and p50 is not None and p75 is not None:
        scale = calibrated_decimal / p50
        return p25 * scale, p75 * scale

    return calibrated_decimal * Decimal("0.8"), calibrated_decimal * Decimal("1.2")


def _select_ebitda_percentiles(step2: Mapping[str, NumericValue]) -> RawPercentiles:
    calibrated = step2.get("ev_ebitda_multiple")
    raw_p25 = step2.get("ev_ebitda_p25")
    raw_p50 = step2.get("ev_ebitda_p50")
    raw_p75 = step2.get("ev_ebitda_p75")

    if _positive_decimal(calibrated) is not None:
        p25, p75 = _scaled_ebitda_band(calibrated, raw_p25, raw_p50, raw_p75)
        logger.debug(
            "✅ Step 3: Using SME-calibrated ev_ebitda_multiple as pipeline starting point",
            extra={
                "step_number": 3,
                "ev_ebitda_multiple_calibrated": calibrated,
                "raw_ev_ebitda_p50": raw_p50,
            },
        )
        return p25, calibrated, p75

    if _positive_decimal(raw_p50) is not None:
        logger.warning(
            "⚠️ Step 3: No calibrated ev_ebitda_multiple, falling back to raw ev_ebitda_p50",
            extra={"step_number": 3, "ev_ebitda_p50": raw_p50},
        )
        return raw_p25, raw_p50, raw_p75

    logger.warning(
        "⚠️ Step 3: No EBITDA multiples available from Step 2",
        extra={"step_number": 3},
    )
    return None, None, None


class MultipleSelection(NamedTuple):
    multiple_raw: NumericValue
    metric: Decimal
    metric_name: str
    fallback_used: bool


def _select_revenue_multiple(
    step2: Mapping[str, NumericValue],
    revenue: Decimal,
    ebitda: Optional[Decimal],
) -> MultipleSelection:
    revenue_multiple = step2.get("ev_revenue_multiple")
    if _positive_decimal(revenue_multiple) is not None:
        logger.debug(
            "✅ Revenue multiple available",
            extra={"step_number": 3, "ev_revenue_multiple": revenue_multiple},
        )
        return MultipleSelection(revenue_multiple, revenue, "Revenue", False)

    ebitda_multiple = step2.get("ev_ebitda_multiple")
    if _positive_decimal(ebitda_multiple) is not None and ebitda is not None and ebitda > 0:
        logger.warning(
            "⚠️ Revenue multiple unavailable — falling back to full EBITDA method (metric + multiple)",
            extra={
                "step_number": 3,
                "ev_revenue_multiple": revenue_multiple,
                "ebitda_fallback_multiple": ebitda_multiple,
            },
        )
        return MultipleSelection(ebitda_multiple, ebitda, "EBITDA (Revenue fallback)", True)

    logger.warning(
        "⚠️ Revenue multiple unavailable, no viable EBITDA fallback",
        extra={"step_number": 3},
    )
    logger.error("Both revenue and EBITDA multiples unavailable, using safe default 1.0x revenue")
    return MultipleSelection(Decimal("1.0"), revenue, "Revenue", True)


def _select_ebitda_multiple(
    step2: Mapping[str, NumericValue],
    revenue: Decimal,
    ebitda: Optional[Decimal],
) -> MultipleSelection:
    if ebitda is None or ebitda <= 0:
        revenue_multiple = step2.get("ev_revenue_multiple")
        logger.warning(
            "EBITDA unavailable or negative, using Revenue multiple as fallback",
            extra={
                "revenue": to_decimal(revenue or 0),
                "multiple_used": _optional_decimal(revenue_multiple),
            },
        )
        multiple_raw = revenue_multiple
        if _positive_decimal(multiple_raw) is None:
            logger.error("Both EBITDA and revenue multiples unavailable, using safe default 5.0x")
            multiple_raw = Decimal("5.0")
        return MultipleSelection(multiple_raw, revenue, "Revenue (EBITDA fallback)", True)

    ebitda_multiple = step2.get("ev_ebitda_multiple")
    if _positive_decimal(ebitda_multiple) is not None:
        return MultipleSelection(ebitda_multiple, ebitda, "EBITDA", False)

    revenue_multiple = step2.get("ev_revenue_multiple")
    logger.warning(
        "EBITDA multiple unavailable, using Revenue multiple as fallback",
        extra={"multiple_used": revenue_multiple},
    )
    if _positive_decimal(revenue_multiple) is None:
        logger.error("Both EBITDA and revenue multiples unavailable, using safe default 5.0x")
        revenue_multiple = Decimal("5.0")

    return MultipleSelection(revenue_multiple, ebitda, "EBITDA", True)


def _apply_step25_multiple_calibration(
    base_multiple: Decimal, step2_5: Optional[Mapping[str, NumericValue]]
) -> Decimal:
    if not step2_5 or "quality_multiple_adjustment" not in step2_5:
        logger.info(
            "ℹ️ Step 3: Using base multiple from Step 2 (no quality calibration)",
            extra={
                "step_number": 3,
                "base_multiple": to_decimal(base_multiple),
                "note": "Step 2.5 quality calibration not available",
            },
        )
        return base_multiple

    quality_adj = to_decimal(step2_5.get("quality_multiple_adjustment") or 0)
    calibrated_multiple = base_multiple + quality_adj
    logger.debug(
        "✅ Step 3: Applied quality-based multiple calibration from Step 2.5",
        extra={
            "step_number": 3,
            "base_multiple": to_decimal(base_multiple),
            "quality_adjustment": to_decimal(quality_adj),
            "calibrated_multiple": to_decimal(calibrated_multiple),
            "methodology": "Multiple-first approach (Big 4 standard)",
            "note": "Quality adjustment applied to MULTIPLE, not EBITDA",
        },
    )
    return calibrated_multiple


def _as_mapping(value: object) -> Optional[Mapping[str, object]]:
    if isinstance(value, Mapping):
        return value
    return None


def _first_truthy(*values: object) -> object | None:
    for value in values:
        if value:
            return value
    return None


def _calibration_metadata(metadata: Mapping[str, object]) -> Mapping[str, object]:
    for key in ("multiple_calibration", "advisor_multiple_calibration"):
        calibration = _as_mapping(metadata.get(key))
        if calibration is not None:
            return calibration
    return {}


def _resolve_manual_adjustment(current: object, metadata: Mapping[str, object]) -> object | None:
    if current is not None:
        return current

    calibration = _calibration_metadata(metadata)
    return _first_truthy(
        calibration.get("adjustment"),
        calibration.get("specific_risk_quality_premium"),
        calibration.get("premium"),
        metadata.get("multiple_calibration_adjustment"),
    )


def _resolve_manual_note(current: object, metadata: Mapping[str, object]) -> object | None:
    if current is not None:
        return current

    calibration = _calibration_metadata(metadata)
    return _first_truthy(
        calibration.get("note"),
        calibration.get("rationale"),
        metadata.get("multiple_calibration_note"),
    )


class Step3EVCalculator:
    """Calculates enterprise values for Step 3."""

    def extract_metrics(
        self, step1: Dict[str, Any], request: any, step2_5: Optional[Dict[str, Any]] = None
    ) -> Tuple[Decimal, Optional[Decimal]]:
        """
        Extract revenue/EBITDA from Step 1.

        MULTIPLE-FIRST METHODOLOGY:
        Always use REPORTED EBITDA from Step 1. Quality adjustments from Step 2.5
        are applied to the MULTIPLE, not the EBITDA metric, preventing double-counting.

        Args:
            step1: Step 1 result dictionary
            request: Valuation request
            step2_5: Step 2.5 result (quality calibration) - OPTIONAL, used for logging only

        Returns:
            Tuple of (revenue, ebitda)
        """
        revenue_raw = step1.get("revenue")
        revenue = to_decimal(revenue_raw) if revenue_raw is not None else Decimal("0")
        ebitda_raw = step1.get("ebitda")
        ebitda = to_decimal(ebitda_raw) if ebitda_raw is not None else None

        # MULTIPLE-FIRST: Always use REPORTED EBITDA (no normalization)
        # Quality adjustments from Step 2.5 are applied to the MULTIPLE in extract_multiples()
        if step2_5 and "quality_multiple_adjustment" in step2_5:
            quality_adj = step2_5.get("quality_multiple_adjustment", 0)

            logger.debug(
                "✅ Step 3: Using REPORTED EBITDA (MULTIPLE-FIRST methodology)",
                extra={
                    "step_number": 3,
                    "reported_ebitda": to_decimal(ebitda) if ebitda is not None else None,
                    "quality_multiple_adjustment": quality_adj,
                    "methodology": "Multiple-first approach (Big 4 standard)",
                    "note": "Quality adjustment applied to MULTIPLE, not EBITDA (prevents double-counting)",
                    "source": "Step 2.5 Quality Calibration",
                },
            )
        elif ebitda is not None:
            logger.debug(
                "ℹ️ Step 3: Using REPORTED EBITDA (Step 2.5 quality calibration not available)",
                extra={
                    "step_number": 3,
                    "reported_ebitda": to_decimal(ebitda),
                    "note": "No quality calibration - using base multiple from Step 2",
                },
            )

        # Fallback to extract directly from request if Step 1 missing data
        if revenue <= 0:
            logger.warning(
                "⚠️ Step 3: Revenue from Step 1 is zero, attempting fallback to request",
                extra={
                    "step_number": 3,
                    "step1_revenue": to_decimal(revenue),
                    "fallback_attempt": "extracting_from_request",
                },
            )
            revenue_decimal = extract_revenue(request)
            if revenue_decimal is not None and revenue_decimal > 0:
                revenue = revenue_decimal
                logger.info(
                    "✅ Step 3: Revenue extracted from request (fallback)",
                    extra={
                        "step_number": 3,
                        "revenue": to_decimal(revenue),
                        "source": "step_utilities.extract_revenue",
                    },
                )

        # Extract EBITDA from request if not available from Step 1 (and no normalization)
        if ebitda is None:
            ebitda_decimal = extract_ebitda(request)
            if ebitda_decimal is not None:
                ebitda = ebitda_decimal
                logger.info(
                    "✅ Step 3: EBITDA extracted from request (fallback)",
                    extra={
                        "step_number": 3,
                        "ebitda": to_decimal(ebitda),
                        "source": "step_utilities.extract_ebitda",
                    },
                )

        return revenue, ebitda

    def determine_primary_method(self, step2: Dict[str, Any]) -> str:
        """
        Determine and validate primary method.

        Args:
            step2: Step 2 result dictionary

        Returns:
            Primary method ('EV/Revenue' or 'EV/EBITDA')
        """
        primary_method = self._normalize_primary_method(step2.get("primary_method"))

        if primary_method is None:
            fallback_method = (
                "EV/EBITDA"
                if to_decimal(step2.get("ev_ebitda_multiple", 0) or 0) > 0
                else "EV/Revenue"
            )
            logger.warning(
                "⚠️ Unknown primary method in Step 2, using validated fallback",
                extra={
                    "step_number": 3,
                    "primary_method": step2.get("primary_method"),
                    "fallback_method": fallback_method,
                },
            )
            primary_method = fallback_method

        return primary_method

    @staticmethod
    def _normalize_primary_method(primary_method: Any) -> Optional[str]:
        """Normalize legacy Step 2 method tokens to canonical Step 3 tokens.

        Accepts all known aliases emitted by Step 2 orchestrator, recovery
        handlers, and legacy updaters so no variant silently falls through.
        """
        if primary_method is None:
            return None
        normalized = str(primary_method).strip().upper()
        if normalized in {"EV/EBITDA", "EBITDA_MULTIPLE", "EBITDA", "EV_EBITDA"}:
            return "EV/EBITDA"
        if normalized in {"EV/REVENUE", "REVENUE_MULTIPLE", "REVENUE", "EV_REVENUE"}:
            return "EV/Revenue"
        return None

    def extract_manual_multiple_calibration(self, request: Any) -> Tuple[Decimal, Optional[str]]:
        """Return advisor-entered multiple adjustment and audit note."""
        adjustment_raw = getattr(request, "multiple_calibration_adjustment", None)
        note_raw = getattr(request, "multiple_calibration_note", None)

        metadata = _as_mapping(getattr(request, "metadata", None))
        if metadata is not None:
            adjustment_raw = _resolve_manual_adjustment(adjustment_raw, metadata)
            note_raw = _resolve_manual_note(note_raw, metadata)

        adjustment = to_decimal(adjustment_raw or 0)
        note = str(note_raw or "").strip() or None
        return adjustment, note

    def extract_multiples(
        self,
        step2: Dict[str, Any],
        primary_method: str,
        revenue: Decimal,
        ebitda: Optional[Decimal],
        step2_5: Optional[Dict[str, Any]] = None,
        request: Any = None,
    ) -> Tuple[Decimal, Decimal, str, bool]:
        """
        Extract multiples from Step 2 with fallbacks.

        Args:
            step2: Step 2 result dictionary
            primary_method: Primary method ('EV/Revenue' or 'EV/EBITDA')
            revenue: Revenue value
            ebitda: EBITDA value (optional)

        Returns:
            Tuple of (multiple, metric, metric_name, fallback_used)
        """
        if primary_method == "EV/Revenue":
            selection = _select_revenue_multiple(step2, revenue, ebitda)
        else:  # EV/EBITDA
            selection = _select_ebitda_multiple(step2, revenue, ebitda)

        base_multiple = to_decimal(selection.multiple_raw)
        multiple = _apply_step25_multiple_calibration(base_multiple, step2_5)

        manual_adj, manual_note = (
            self.extract_manual_multiple_calibration(request)
            if request is not None
            else (Decimal("0"), None)
        )
        if manual_adj != Decimal("0"):
            multiple += manual_adj
            logger.info(
                "✅ Step 3: Applied advisor-specific multiple calibration",
                extra={
                    "step_number": 3,
                    "base_multiple": to_decimal(base_multiple),
                    "manual_adjustment": to_decimal(manual_adj),
                    "calibrated_multiple": to_decimal(multiple),
                    "audit_note": manual_note,
                    "methodology": "Advisor override applied to the benchmark multiple",
                },
            )

        return multiple, selection.metric, selection.metric_name, selection.fallback_used

    def extract_percentiles(
        self,
        step2: Dict[str, Any],
        primary_method: str,
        median_multiple: Decimal,
        quality_adjustment: Decimal = Decimal("0"),
    ) -> Tuple[Decimal, Decimal, Decimal, bool]:
        """
        Extract percentiles (P25/P50/P75) with validation and fallback to estimation.

        Args:
            step2: Step 2 result dictionary
            primary_method: Primary method ('EV/Revenue' or 'EV/EBITDA')
            median_multiple: Median multiple for fallback estimation
            quality_adjustment: Quality/manual multiple adjustment (shifts entire distribution)

        Returns:
            Tuple of (multiple_p25, multiple_p50, multiple_p75, using_real_percentiles)
        """
        if primary_method == "EV/Revenue":
            raw_percentiles = _select_revenue_percentiles(step2)
        else:  # EV/EBITDA
            raw_percentiles = _select_ebitda_percentiles(step2)

        real_percentiles = _positive_decimal_percentiles(raw_percentiles)
        using_real_percentiles = real_percentiles is not None

        if real_percentiles is not None:
            if not _percentiles_in_order(real_percentiles):
                logger.warning(
                    "⚠️ Step 3: Invalid percentile ordering detected, auto-correcting",
                    extra={
                        "p25_before": to_decimal(real_percentiles[0]),
                        "p50_before": to_decimal(real_percentiles[1]),
                        "p75_before": to_decimal(real_percentiles[2]),
                        "primary_method": primary_method,
                    },
                )

            multiple_p25, multiple_p50, multiple_p75 = _ordered_percentiles(real_percentiles)

            if quality_adjustment and quality_adjustment != Decimal("0"):
                multiple_p25, multiple_p50, multiple_p75 = _quality_adjusted_percentiles(
                    (multiple_p25, multiple_p50, multiple_p75),
                    quality_adjustment,
                )

                logger.debug(
                    "✅ Step 3: Applied quality/manual adjustment to percentiles",
                    extra={
                        "step_number": 3,
                        "multiple_adjustment": to_decimal(quality_adjustment),
                        "adjusted_p25": to_decimal(multiple_p25),
                        "adjusted_p50": to_decimal(multiple_p50),
                        "adjusted_p75": to_decimal(multiple_p75),
                    },
                )

            logger.debug(
                "✓ Using real percentiles from Step 2",
                extra={
                    "p25": to_decimal(multiple_p25),
                    "p50": to_decimal(multiple_p50),
                    "p75": to_decimal(multiple_p75),
                    "source": (
                        "Step 2 percentiles (quality-adjusted)"
                        if quality_adjustment
                        else "Step 2 percentiles"
                    ),
                    "primary_method": primary_method,
                },
            )
        else:
            multiple_p25, multiple_p50, multiple_p75 = _estimated_percentiles(median_multiple)

            logger.info(
                "⚠️ Percentiles not available from Step 2, using estimation",
                extra={
                    "p25": to_decimal(multiple_p25),
                    "p50": to_decimal(multiple_p50),
                    "p75": to_decimal(multiple_p75),
                    "source": "estimated (80%/120% of median)",
                },
            )

        return multiple_p25, multiple_p50, multiple_p75, using_real_percentiles

    def calculate_ev_range(
        self, metric: Decimal, multiple_p25: Decimal, multiple_p50: Decimal, multiple_p75: Decimal
    ) -> Tuple[Decimal, Decimal, Decimal]:
        """
        Calculate EV range using percentiles.

        Args:
            metric: Metric value (revenue or EBITDA)
            multiple_p25: P25 multiple
            multiple_p50: P50 multiple
            multiple_p75: P75 multiple

        Returns:
            Tuple of (ev_low, ev_mid, ev_high)
        """
        enterprise_value_low = money_multiply(metric, multiple_p25)
        enterprise_value_mid = money_multiply(metric, multiple_p50)
        enterprise_value_high = money_multiply(metric, multiple_p75)

        return enterprise_value_low, enterprise_value_mid, enterprise_value_high

    def validate_and_correct_range(
        self, ev_low: Decimal, ev_mid: Decimal, ev_high: Decimal
    ) -> Tuple[Decimal, Decimal, Decimal]:
        """
        Validate and correct EV range ordering.

        Args:
            ev_low: EV low value
            ev_mid: EV mid value
            ev_high: EV high value

        Returns:
            Tuple of (corrected_ev_low, corrected_ev_mid, corrected_ev_high)
        """
        if ev_low >= ev_mid or ev_mid >= ev_high:
            logger.warning(
                "⚠️ Invalid EV range detected, auto-correcting",
                extra={
                    "ev_low": to_decimal(ev_low),
                    "ev_mid": to_decimal(ev_mid),
                    "ev_high": to_decimal(ev_high),
                },
            )
            # Auto-correct: ensure proper ordering
            ev_values = [ev_low, ev_mid, ev_high]
            ev_low = min(ev_values)
            ev_high = max(ev_values)
            # Recalculate mid as average if ordering was invalid
            if ev_low >= ev_mid or ev_mid >= ev_high:
                ev_mid = (ev_low + ev_high) / to_decimal("2")
                logger.info(
                    "✓ Auto-corrected EV range",
                    extra={
                        "ev_low": to_decimal(ev_low),
                        "ev_mid": to_decimal(ev_mid),
                        "ev_high": to_decimal(ev_high),
                    },
                )
        return ev_low, ev_mid, ev_high

    def validate_consistency(
        self,
        primary_method: str,
        metric_name: str,
        metric_value: Decimal,
        revenue: Decimal,
        ebitda: Optional[Decimal],
    ) -> Tuple[Decimal, str]:
        """
        Validate metric/method consistency and auto-correct if needed.

        Args:
            primary_method: Primary method ('EV/Revenue' or 'EV/EBITDA')
            metric_name: Current metric name
            metric_value: Current metric value
            revenue: Revenue value
            ebitda: EBITDA value (optional)

        Returns:
            Tuple of (corrected_metric, corrected_metric_name)
        """
        corrected_metric = metric_value
        corrected_metric_name = metric_name

        if primary_method == "EV/Revenue" and metric_name != "Revenue":
            logger.error(
                "❌ CRITICAL: Step 3 metric mismatch - primary_method is EV/Revenue but metric is not Revenue",
                extra={
                    "step_number": 3,
                    "primary_method": primary_method,
                    "metric_name": metric_name,
                    "metric_value": to_decimal(metric_value),
                },
            )
            # Auto-correct: Use Revenue as metric
            corrected_metric = revenue
            corrected_metric_name = "Revenue"
            logger.warning(
                "⚠️ Auto-corrected: Using Revenue as metric to match primary_method",
                extra={"corrected_metric": to_decimal(corrected_metric)},
            )
        elif primary_method == "EV/EBITDA" and metric_name not in [
            "EBITDA",
            "Revenue (EBITDA fallback)",
        ]:
            logger.error(
                "❌ CRITICAL: Step 3 metric mismatch - primary_method is EV/EBITDA but metric is not EBITDA",
                extra={
                    "step_number": 3,
                    "primary_method": primary_method,
                    "metric_name": metric_name,
                    "metric_value": to_decimal(metric_value),
                },
            )
            # Auto-correct: Use EBITDA as metric if available
            if ebitda and ebitda > 0:
                corrected_metric = ebitda
                corrected_metric_name = "EBITDA"
                logger.warning(
                    "⚠️ Auto-corrected: Using EBITDA as metric to match primary_method",
                    extra={"corrected_metric": to_decimal(corrected_metric)},
                )

        return corrected_metric, corrected_metric_name
