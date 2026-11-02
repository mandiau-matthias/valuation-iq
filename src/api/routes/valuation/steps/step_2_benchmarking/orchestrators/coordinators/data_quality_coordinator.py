"""
Data Quality Coordinator

Orchestrates data quality warnings and validation for Step 2.
"""

from collections.abc import Mapping
from decimal import Decimal
from typing import Any, Dict, List, Optional

from src.domain.benchmark_margin_provenance import (
    IndustryMarginBenchmark,
    resolve_industry_margin_benchmark,
)
from src.domain.report_integrity import build_ebitda_benchmark_deviation_warning
from src.utils.logging import get_logger

logger = get_logger(__name__)


def _as_mapping(value: object) -> Mapping[str, object]:
    if isinstance(value, Mapping):
        return value
    return {}


def _optional_int(value: object) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _optional_decimal(value: object) -> Decimal | None:
    try:
        return Decimal(str(value)) if value is not None else None
    except (TypeError, ValueError, ArithmeticError):
        return None


def _micro_business_warning(revenue: Decimal) -> dict[str, object] | None:
    if revenue and revenue < 500_000:
        return {
            "type": "micro_business_risk",
            "severity": "medium",
            "message": f"Micro business (€{revenue:,.0f} < €500K) - higher valuation uncertainty due to limited scale",
            "impact": "Confidence score reduced by 5 points",
            "recommendation": "Consider obtaining independent business appraisal for validation",
        }
    return None


def _small_absolute_ebitda_warning(ebitda: Optional[Decimal]) -> dict[str, object] | None:
    if ebitda and ebitda > 0 and ebitda < 100_000:
        return {
            "type": "small_absolute_ebitda",
            "severity": "medium",
            "message": f"Small EBITDA base (€{ebitda:,.0f} < €100K) - minor operational changes have large relative impact",
            "impact": "Confidence score reduced by 3 points",
            "recommendation": "Focus on EBITDA sustainability and growth trajectory",
        }
    return None


def _low_margin_warning(
    ebitda: Optional[Decimal], ebitda_margin: Decimal
) -> dict[str, object] | None:
    if ebitda and ebitda > 0 and Decimal("3.0") <= ebitda_margin < Decimal("5.0"):
        return {
            "type": "low_margin_warning",
            "severity": "medium",
            "message": f"Low profitability margin ({ebitda_margin:.1f}%) - EBITDA multiple used but elevated risk",
            "impact": "Confidence score reduced by 5 points",
            "recommendation": "Monitor margin trends and cost structure carefully",
        }
    return None


def _small_business_quality_warning(
    revenue: Decimal, ebitda_margin: Decimal
) -> dict[str, object] | None:
    if revenue and 500_000 <= revenue < 1_000_000 and ebitda_margin >= Decimal("10.0"):
        return {
            "type": "small_business_quality",
            "severity": "low",
            "message": f"Small business with strong margin (€{revenue:,.0f}, {ebitda_margin:.1f}% margin) - EBITDA multiple appropriate",
            "impact": "Confidence score reduced by 3 points (size only)",
            "recommendation": "Valuation based on profitability, not size. No methodology restriction applied.",
        }
    return None


_ASSET_HEAVY_FIXED_TO_REVENUE = Decimal("3")
_ASSET_HEAVY_TOTAL_TO_REVENUE = Decimal("4")
_ASSET_HEAVY_MARGIN = Decimal("0.5")


def _asset_heavy_profile_warnings(
    current_year_data: object, revenue: Decimal, ebitda_margin: Decimal
) -> list[dict[str, Any]]:
    """Flag a balance sheet that an operating EBITDA multiple cannot price.

    The engine routes to yield / NAV only on NACE 64.2x / 68.1x / 68.2x or an
    explicit holding / patrimony industry tag. A property company registered
    under a construction code (the first paying advisor's DEBAETS REAL ESTATE:
    KBO NACE 43240, fixed assets 4.2× revenue, EBITDA margin 84%) therefore
    received a 5.08× EBITDA multiple with no warning at all. Method choice is the
    advisor's call; this makes sure the report asks the question.
    """
    if current_year_data is None or revenue is None or revenue <= 0:
        return []
    total_assets = _optional_decimal(getattr(current_year_data, "total_assets", None))
    fixed_assets = _optional_decimal(getattr(current_year_data, "fixed_assets", None))
    current_assets = _optional_decimal(getattr(current_year_data, "current_assets", None))
    non_current = fixed_assets
    if non_current is None and total_assets is not None and current_assets is not None:
        non_current = total_assets - current_assets

    margin = _optional_decimal(ebitda_margin) or Decimal("0")
    if margin > Decimal("1"):  # percent form
        margin = margin / Decimal("100")

    fixed_heavy = non_current is not None and non_current >= revenue * _ASSET_HEAVY_FIXED_TO_REVENUE
    balance_heavy = (
        total_assets is not None
        and total_assets >= revenue * _ASSET_HEAVY_TOTAL_TO_REVENUE
        and margin >= _ASSET_HEAVY_MARGIN
    )
    if not (fixed_heavy or balance_heavy):
        return []

    basis = non_current if non_current is not None else total_assets
    ratio = basis / revenue
    return [
        {
            "type": "asset_heavy_profile",
            "severity": "medium",
            "step_number": 2,
            "message": (
                f"Asset-heavy profile: non-current assets of €{basis:,.0f} are {ratio:.1f}× "
                f"revenue and the EBITDA margin is {margin * 100:.0f}%. This looks like a "
                "property or holding entity; an operating EBITDA multiple may not be the right method."
            ),
            "impact": "Method fit — the multiple prices operating earnings, not the asset base",
            "recommendation": (
                "Confirm the business type before sharing this report: a property company "
                "(Vastgoed / patrimony) or a holding is routed to yield / net-asset value, "
                "not to an EBITDA multiple."
            ),
            "details": {
                "non_current_assets": float(basis),
                "non_current_to_revenue": float(ratio),
                "ebitda_margin_pct": float(margin * 100),
                "trigger": "fixed_asset_intensity" if fixed_heavy else "balance_sheet_and_margin",
            },
        }
    ]


def _scale_warnings(
    revenue: Decimal, ebitda: Optional[Decimal], ebitda_margin: Decimal
) -> list[dict[str, object]]:
    warnings = (
        _micro_business_warning(revenue),
        _small_absolute_ebitda_warning(ebitda),
        _low_margin_warning(ebitda, ebitda_margin),
        _small_business_quality_warning(revenue, ebitda_margin),
    )

    return [warning for warning in warnings if warning is not None]


def _thin_comparable_signals(
    sample_size: int | None, quality_score: Decimal | None, is_proxy_source: bool
) -> list[str]:
    signals: list[str] = []
    if sample_size is not None and sample_size <= 3:
        signals.append(f"sample_size={sample_size}")
    if quality_score is not None and quality_score < Decimal("0.7"):
        signals.append(f"quality_score={float(quality_score):.2f}")
    if is_proxy_source:
        signals.append("proxy-sector source")
    return signals


def _thin_comparables_warning(
    multiples_data: Mapping[str, object],
) -> tuple[dict[str, object], dict[str, object]] | None:
    details = _as_mapping(multiples_data.get("data_source_details"))
    sample_size = _optional_int(details.get("multiples_sample_size"))
    quality_score = _optional_decimal(details.get("multiples_quality_score"))
    multiples_source_value = details.get("multiples_source") or ""
    multiples_source = str(multiples_source_value).lower()
    data_source = multiples_data.get("data_source")

    is_proxy_source = any(
        token in multiples_source for token in ("proxy", "comparable-sector", "comparable sector")
    )
    thin_sample = sample_size is not None and sample_size <= 3
    low_quality = quality_score is not None and quality_score < Decimal("0.7")

    if not (thin_sample or low_quality or is_proxy_source):
        return None

    signals = _thin_comparable_signals(sample_size, quality_score, is_proxy_source)
    quality_score_float = float(quality_score) if quality_score is not None else None
    log_extra = {
        "data_source": data_source,
        "multiples_source": details.get("multiples_source"),
        "sample_size": sample_size,
        "quality_score": quality_score_float,
        "business_type_id": details.get("business_type_id"),
    }
    warning = {
        "type": "thin_comparables_proxy",
        "severity": "high",
        "message": (
            "Industry multiple is derived from thin or proxy-sector data ("
            + ", ".join(signals)
            + "). The headline multiple is not statistically robust on its own."
        ),
        "impact": (
            "Treat the resulting EV as indicative; widen the band and validate "
            "against an independent comparables search before delivering."
        ),
        "recommendation": (
            "Confirm the business_type_id matches the actual operating model and, "
            "if the company is in a different sector than the proxy, override the "
            "multiple manually or request a deeper benchmarks pull."
        ),
        "details": {
            "data_source": data_source,
            "multiples_source": details.get("multiples_source"),
            "sample_size": sample_size,
            "quality_score": quality_score_float,
            "business_type_id": details.get("business_type_id"),
        },
    }
    return warning, log_extra


def _benchmark_unavailable_warning(
    benchmark: IndustryMarginBenchmark,
) -> dict[str, object]:
    """Disclose that no measured sector band exists, without accusing anyone.

    This replaces the deviation warning for the 147 business types whose
    `typical_ebitda_margin_median` is the untouched seed default.
    """
    return {
        "type": "industry_margin_benchmark_unavailable",
        "severity": "low",
        "message": (
            "No measured sector EBITDA-margin benchmark exists for this business "
            "type, so this company's margin has not been compared against one."
        ),
        "impact": "No confidence adjustment applied for margin deviation.",
        "recommendation": (
            "Read the margin on its own merits. Request a calibrated sector "
            "margin band before making any peer-comparison claim."
        ),
        "details": {
            "benchmark_measured": False,
            "benchmark_grade": benchmark.grade,
            "provenance_reason": benchmark.reason,
            "placeholder_margin_pct": benchmark.median_pct,
        },
    }


def _band_clause(benchmark: IndustryMarginBenchmark) -> str:
    """Sentence fragment stating what the sector figure actually is.

    A deviation only means something against a spread, so the reader is told
    which of the two they are looking at.
    """
    low, high = benchmark.min_pct, benchmark.max_pct

    if not benchmark.is_measured:
        # A band we DERIVED (EV/Revenue over EV/EBITDA) or CURATED has a spread
        # but not a measured one. Say what it is; never call it measured.
        if benchmark.reason.startswith("declared_") and low is not None and high is not None:
            return (
                f" The sector band of {low:.1f}%–{high:.1f}% is derived from valuation "
                "multiples rather than measured from filings, so it is context, not "
                "evidence that this margin is abnormal."
            )
        return (
            " The sector figure is a single estimate with no measured spread, "
            "so it cannot establish that this margin is abnormal."
        )
    if low is not None and high is not None:
        return f" The measured sector band is {low:.1f}%–{high:.1f}%."
    if low is not None:
        return f" The measured sector band starts at {low:.1f}%."
    if high is not None:
        return f" The measured sector band tops out at {high:.1f}%."
    return ""


class DataQualityCoordinator:
    """
    Coordinates data quality warnings and validation operations.
    """

    def __init__(self, logger_instance=None) -> None:
        self.logger = logger_instance or logger

    def generate_data_quality_warnings(
        self,
        revenue: Decimal,
        ebitda: Optional[Decimal],
        ebitda_margin: Decimal,
        titan_benchmarks: Optional[Dict[str, Any]] = None,
        multiples_data: Optional[Dict[str, Any]] = None,
        margin_basis: Optional[str] = None,
        current_year_data: object = None,
    ) -> List[Dict[str, Any]]:
        """
        Generate data quality warnings.

        BANK-GRADE: Warnings inform users about data quality issues without blocking valuations.
        Atypical values are common in real businesses and should:
        - Reduce confidence scores (not block valuations)
        - Be transparently communicated to users
        - Help users understand valuation uncertainty

        Args:
            revenue: Revenue value
            ebitda: EBITDA value (optional)
            ebitda_margin: EBITDA margin
            titan_benchmarks: Optional industry benchmarks from Titan enrichment
            margin_basis: Which earnings basis `ebitda_margin` was computed on,
                echoed into the warning so the reported figure is provably the
                same measurement as `financial_metrics.ebitda_margin`

        Returns:
            List of warning dictionaries
        """
        warnings = []

        # ========================================================================
        # BANK-GRADE: Industry Benchmark Deviation Warnings (INFORMATIONAL ONLY)
        # ========================================================================
        # These warnings help users understand why their valuation confidence may be lower,
        # but they do NOT block valuations. Many legitimate businesses have atypical metrics.
        if titan_benchmarks:
            warnings.extend(
                self._generate_industry_benchmark_warnings(
                    ebitda_margin, revenue, titan_benchmarks, margin_basis=margin_basis
                )
            )

        warnings.extend(_scale_warnings(revenue, ebitda, ebitda_margin))
        warnings.extend(_asset_heavy_profile_warnings(current_year_data, revenue, ebitda_margin))

        # ====================================================================
        # Thin comparables / proxy sector warning
        # --------------------------------------------------------------------
        # Triggered by the Metaalbewerking-class signal: sample_size = 1 and
        # quality_score = 0.65 with multiples_source mentioning "proxy" or
        # "comparable-sector". The previous behaviour silently used these as
        # an "authoritative" multiple. Surface it as a HIGH-severity warning
        # so advisors can override the multiple before delivering the report.
        # ====================================================================
        if multiples_data:
            thin_finding = _thin_comparables_warning(multiples_data)
            if thin_finding is not None:
                warning, log_extra = thin_finding
                warnings.append(warning)
                self.logger.warning(
                    "[BENCHMARK-QUALITY] Thin/proxy multiples — emitted high-severity warning",
                    extra=log_extra,
                )

        return warnings

    def validate_multiples_data(
        self,
        multiples_data: Dict[str, Any],
        *,
        allow_untrusted_multiples_fallback: bool = False,
    ) -> Dict[str, Any]:
        """
        Validate multiples data and ensure required fields exist.

        Args:
            multiples_data: Multiples data dictionary

        Returns:
            Validated multiples data dictionary
        """
        from src.utils.decimal_helpers import to_decimal

        ev_revenue = multiples_data.get("ev_revenue")
        # Handle string values (from JSON serialization) by converting to Decimal
        if ev_revenue is not None:
            try:
                ev_revenue_decimal = to_decimal(ev_revenue)
            except (ValueError, TypeError):
                ev_revenue_decimal = None
        else:
            ev_revenue_decimal = None

        # BANK-GRADE: Use explicit None check to handle Decimal("0") correctly
        # Decimal("0") is falsy but mathematically valid - must check for None explicitly, not truthiness
        if ev_revenue_decimal is None or ev_revenue_decimal <= 0:
            if not allow_untrusted_multiples_fallback:
                self.logger.warning(
                    "Step 2 revenue multiple missing or invalid; leaving unset because "
                    "untrusted fallback was not explicitly allowed",
                    extra={"ev_revenue": multiples_data.get("ev_revenue")},
                )
                return multiples_data
            self.logger.error(
                "Revenue multiple missing or invalid; using explicitly disclosed untrusted fallback",
                extra={"ev_revenue": multiples_data.get("ev_revenue")},
            )
            multiples_data["ev_revenue"] = Decimal("1.0")
            multiples_data["ev_revenue_p25"] = Decimal("0.8")
            multiples_data["ev_revenue_p50"] = Decimal("1.0")
            multiples_data["ev_revenue_p75"] = Decimal("1.2")
            if multiples_data.get("data_source") == "unknown":
                multiples_data["data_source"] = "forced_fallback"

        return multiples_data

    def generate_multiples_checksum(self, multiples_data: Dict[str, Any]) -> str:
        """
        Generate checksum for multiples data integrity validation.

        Args:
            multiples_data: Multiples data dictionary

        Returns:
            Non-security checksum string
        """
        import hashlib
        import json

        from src.utils.decimal_helpers import to_decimal

        # Convert Decimal values to strings for JSON serialization
        ev_revenue_decimal = to_decimal(multiples_data.get("ev_revenue") or 0)
        ev_ebitda_decimal = to_decimal(multiples_data.get("ev_ebitda") or 0)

        checksum_data = {
            "ev_revenue": str(ev_revenue_decimal),
            "ev_ebitda": str(ev_ebitda_decimal),
            "data_source": multiples_data.get("data_source", ""),
        }
        return hashlib.md5(
            json.dumps(checksum_data, sort_keys=True).encode(),
            usedforsecurity=False,
        ).hexdigest()

    def calculate_growth_rate(self, request: Any) -> Optional[Decimal]:
        """
        Calculate growth rate from historical data.

        Args:
            request: Valuation request

        Returns:
            Growth rate as Decimal or None
        """
        if (
            not hasattr(request, "historical_years_data")
            or not request.historical_years_data
            or len(request.historical_years_data) < 2
        ):
            return None

        try:
            from src.utils.decimal_helpers import to_decimal

            historical_years = sorted(
                request.historical_years_data,
                key=lambda year: getattr(year, "year", 0),
            )
            _cur_rev = historical_years[-1].revenue
            _pri_rev = historical_years[-2].revenue
            current_year_revenue = to_decimal(_cur_rev) if _cur_rev is not None else Decimal("0")
            prior_year_revenue = to_decimal(_pri_rev) if _pri_rev is not None else Decimal("0")
            if prior_year_revenue and prior_year_revenue > 0:
                growth_rate = (
                    (current_year_revenue - prior_year_revenue) / prior_year_revenue
                ) * Decimal("100")
                if growth_rate.is_nan() or growth_rate.is_infinite():
                    return Decimal("0.0")
                return growth_rate
        except (AttributeError, IndexError, TypeError):
            pass

        return None

    def _generate_industry_benchmark_warnings(
        self,
        ebitda_margin: Decimal,
        revenue: Optional[Decimal],
        titan_benchmarks: Dict[str, Any],
        *,
        margin_basis: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        BANK-GRADE: Generate warnings for industry benchmark deviations.

        These are INFORMATIONAL ONLY - they do NOT block valuations.
        Many legitimate businesses have atypical metrics due to:
        - Business model differences (e.g., high-growth SaaS with low margins)
        - Investment phase (reinvesting profits into growth)
        - Market position (premium pricing or cost leadership strategies)
        - One-time factors (restructuring, acquisition integration)

        Args:
            ebitda_margin: EBITDA margin as Decimal (e.g., 0.046 for 4.6%)
            revenue: Revenue value
            titan_benchmarks: Industry benchmarks from Titan enrichment
            margin_basis: Which earnings basis `ebitda_margin` was computed on

        Returns:
            List of warning dictionaries (informational only)
        """
        warnings = []

        # ========================================================================
        # EBITDA Margin vs Industry Typical (INFORMATIONAL WARNING ONLY)
        # ========================================================================
        # PROVENANCE GATE (src/domain/benchmark_margin_provenance.py).
        # 147 of the 197 rows in `business_types` carry the seeded default
        # median = 15.00 with NULL min/max. A bare seed median is not a
        # measurement: it must not be used to accuse a business of deviating,
        # and it must not dock confidence. Only a band with real dispersion
        # establishes what "typical" and "deviant" even mean.
        benchmark = resolve_industry_margin_benchmark(titan_benchmarks)

        if benchmark.median is None:
            return warnings

        if not benchmark.is_comparable:
            self.logger.info(
                "[BENCHMARK-PROVENANCE] Sector margin benchmark is a placeholder — "
                "deviation warning and confidence penalty suppressed",
                extra={
                    "placeholder_margin_pct": benchmark.median_pct,
                    "benchmark_grade": benchmark.grade,
                    "provenance_reason": benchmark.reason,
                },
            )
            warnings.append(_benchmark_unavailable_warning(benchmark))
            return warnings

        if ebitda_margin is not None:
            try:
                expected_margin = benchmark.median

                # Calculate deviation (only if expected_margin is positive)
                if expected_margin > 0:
                    # Normalize ebitda_margin if needed
                    actual_margin = ebitda_margin
                    if actual_margin > Decimal("1.0"):
                        actual_margin = actual_margin / Decimal("100")

                    deviation = abs(actual_margin - expected_margin) / expected_margin

                    if deviation > Decimal("0.5"):  # >50% deviation from typical
                        direction = "higher" if actual_margin > expected_margin else "lower"

                        # Only a MEASURED band may drive a confidence penalty. A
                        # hand-set point estimate has no known spread, so a
                        # "deviation" from it is not evidence of anything.
                        confidence_impact = (
                            min(int(deviation * 10), 10) if benchmark.is_measured else 0
                        )

                        # Severity calibration (measured band only):
                        # - lower + >50% deviation: medium (often distressed
                        #   business or wrong sector classification — must be
                        #   visible. Three Towers Capital regression).
                        # - higher + <100% deviation: low (often legitimate
                        #   competitive advantage).
                        # - any direction + >100% deviation: medium here. The
                        #   must-disclose ebitda_benchmark_deviation built below
                        #   from this same measurement carries the Page-1
                        #   "high", so the fact is stated at high severity once.
                        if not benchmark.is_measured:
                            severity = "low"
                        elif deviation > Decimal("1.0") or direction == "lower":
                            severity = "medium"
                        else:
                            severity = "low"
                        actual_margin_basis = margin_basis or "step_1_earnings_basis"

                        warnings.append(
                            {
                                "type": "industry_margin_deviation",
                                "severity": severity,
                                "message": (
                                    f"EBITDA margin ({actual_margin:.1%}) is {direction} than industry typical "
                                    f"({expected_margin:.1%})." + _band_clause(benchmark)
                                ),
                                "impact": (
                                    f"Confidence score may be reduced by up to {confidence_impact} points"
                                    if confidence_impact
                                    else "No confidence adjustment applied — the sector figure is "
                                    "not a measured distribution."
                                ),
                                "recommendation": (
                                    "Check that the business_type_id matches the actual operating "
                                    "model. If it does, this margin is a fact about the business, "
                                    "not a defect — many sectors and business models sit well "
                                    "outside the sector median."
                                    # A measured deviation also raises the must-disclose
                                    # flag below, whose advice is to document the reason;
                                    # "no action required" would contradict it.
                                    if direction == "lower" or benchmark.is_measured
                                    else "No action required - this is informational."
                                ),
                                "details": {
                                    "actual_margin_pct": float(actual_margin * 100),
                                    "actual_margin_basis": actual_margin_basis,
                                    "typical_margin_pct": float(expected_margin * 100),
                                    "typical_margin_min_pct": benchmark.min_pct,
                                    "typical_margin_max_pct": benchmark.max_pct,
                                    "deviation_pct": float(deviation * 100),
                                    "direction": direction,
                                    "benchmark_measured": benchmark.is_measured,
                                    "benchmark_grade": benchmark.grade,
                                    "provenance_reason": benchmark.reason,
                                },
                            }
                        )
                        # One measurement, one must-disclose flag. Only a measured
                        # sector distribution can show that a margin deviates
                        # materially; a derived or hand-set band was disclosed above
                        # as context and must not also reach the Page-1 callout.
                        # The flag reuses this warning's margin, median and basis,
                        # so the two can never state different figures.
                        if benchmark.is_measured:
                            warnings.append(
                                build_ebitda_benchmark_deviation_warning(
                                    actual_margin_pct=float(actual_margin),
                                    expected_margin_pct=float(expected_margin),
                                    direction=direction,
                                    actual_margin_basis=actual_margin_basis,
                                )
                            )

                        # Log for monitoring (not an error)
                        self.logger.info(
                            f"[BENCHMARK-INFO] EBITDA margin deviation detected (not blocking)",
                            extra={
                                "actual_margin_pct": float(actual_margin * 100),
                                "typical_margin_pct": float(expected_margin * 100),
                                "deviation_pct": float(deviation * 100),
                                "direction": direction,
                                "blocking": False,
                            },
                        )
            except (ValueError, TypeError, ZeroDivisionError) as e:
                self.logger.debug(f"Could not calculate margin deviation: {e}")

        return warnings
