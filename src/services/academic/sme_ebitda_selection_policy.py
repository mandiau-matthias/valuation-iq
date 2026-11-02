"""EBITDA multiple selection policy for SME valuation."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from decimal import Decimal
from typing import NamedTuple, Optional

from src.services.academic import sme_ebitda_base_resolution
from src.services.academic.sme_multiple_catalog import (
    CATEGORY_TO_SME_KEY,
    EBITDA_MAX_INDUSTRY_OVERRIDES,
    SME_MULTIPLE_BOUNDS,
)
from src.utils.logging import get_logger

logger = get_logger(__name__)

try:
    from src.api.routes.valuation.metrics import (
        sme_calibration_fallback_counter,
        sme_calibration_source_counter,
        sme_multiple_bounds_violation_counter,
    )

    METRICS_AVAILABLE = True
except ImportError:
    METRICS_AVAILABLE = False
    logger.warning("Prometheus metrics not available - SME calibration metrics disabled")


class SmeAdjustmentResult(NamedTuple):
    multiple: Decimal
    rationales: list[str]


def record_sme_calibration_metrics(
    *,
    sme_class: str,
    industry_norm: str,
    data_source_priority: str,
    metrics_available: bool,
    database_defaults_available: bool,
) -> None:
    if not (metrics_available and METRICS_AVAILABLE):
        return

    try:
        sme_calibration_source_counter.labels(
            source=data_source_priority or "unknown",
            sme_class=sme_class,
            industry=industry_norm,
        ).inc()

        if data_source_priority == "hardcoded_fallback":
            reason = "db_not_initialized" if not database_defaults_available else "db_lookup_failed"
            sme_calibration_fallback_counter.labels(
                sme_class=sme_class, industry=industry_norm, reason=reason
            ).inc()
    except Exception as exc:
        logger.debug(f"Failed to record SME calibration metrics: {exc}")


def resolve_base_ebitda_multiple_for_selector(
    *,
    industry: str,
    industry_norm: str,
    sme_class: str,
    business_type: Optional[str],
    business_category: Optional[str],
    country: str,
    use_transaction_data: bool,
    sme_calibration: Optional[Mapping[str, object]],
    database_defaults: object,
    database_defaults_available: bool,
) -> sme_ebitda_base_resolution.SmeEbitdaBaseMultipleResolution:
    """Resolve through the extracted module while preserving legacy patch points."""
    sme_ebitda_base_resolution.DatabaseDrivenDefaults = database_defaults
    sme_ebitda_base_resolution.DATABASE_DRIVEN_DEFAULTS_AVAILABLE = (
        database_defaults_available
    )
    return sme_ebitda_base_resolution.resolve_base_ebitda_multiple(
        industry=industry,
        industry_norm=industry_norm,
        sme_class=sme_class,
        business_type=business_type,
        business_category=business_category,
        country=country,
        use_transaction_data=use_transaction_data,
        sme_calibration=sme_calibration,
    )


def _max_multiple_for_industry(sme_class: str, industry_norm: str) -> Decimal:
    bounds = SME_MULTIPLE_BOUNDS.get(sme_class, {})
    max_multiple = bounds.get("ebitda_max", Decimal("10.0"))
    industry_overrides = EBITDA_MAX_INDUSTRY_OVERRIDES.get(industry_norm, {})

    if not industry_overrides:
        resolved_key = CATEGORY_TO_SME_KEY.get(industry_norm)
        if resolved_key:
            industry_overrides = EBITDA_MAX_INDUSTRY_OVERRIDES.get(resolved_key, {})

    if sme_class in industry_overrides:
        return industry_overrides[sme_class]
    return max_multiple


def _record_bounds_violation(sme_class: str, bound_type: str, metrics_available: bool) -> None:
    if not (metrics_available and METRICS_AVAILABLE):
        return

    try:
        sme_multiple_bounds_violation_counter.labels(
            sme_class=sme_class, bound_type=bound_type
        ).inc()
    except Exception:
        pass


def clamp_to_academic_bounds(
    *,
    multiple: Decimal,
    sme_class: str,
    industry_norm: str,
    metrics_available: bool,
) -> Decimal:
    bounds = SME_MULTIPLE_BOUNDS.get(sme_class, {})
    min_multiple = bounds.get("ebitda_min", Decimal("2.0"))
    max_multiple = _max_multiple_for_industry(sme_class, industry_norm)

    if multiple < min_multiple:
        logger.warning(
            f"Multiple {multiple}x below academic floor {min_multiple}x, adjusting",
            sme_class=sme_class,
            original_multiple=float(multiple),
            adjusted_multiple=float(min_multiple),
        )
        _record_bounds_violation(sme_class, "min_floor", metrics_available)
        return min_multiple

    if multiple > max_multiple:
        logger.warning(
            f"Multiple {multiple}x above academic ceiling {max_multiple}x, adjusting",
            sme_class=sme_class,
            original_multiple=float(multiple),
            adjusted_multiple=float(max_multiple),
        )
        _record_bounds_violation(sme_class, "max_ceiling", metrics_available)
        return max_multiple

    return multiple


def apply_growth_stage_adjustment(
    *,
    multiple: Decimal,
    base_multiple: Decimal,
    growth_stage: str,
    growth_adjustment_factor: Decimal,
) -> SmeAdjustmentResult:
    if growth_adjustment_factor >= Decimal("1.0"):
        return SmeAdjustmentResult(multiple, [])

    adjusted_multiple = multiple * growth_adjustment_factor
    adjustment_pct = (Decimal("1.0") - growth_adjustment_factor) * Decimal("100")
    logger.info(
        "Applied growth stage adjustment",
        growth_stage=growth_stage,
        adjustment_factor=float(growth_adjustment_factor),
        adjustment_pct=float(adjustment_pct),
        base_multiple=float(base_multiple),
        adjusted_multiple=float(adjusted_multiple),
    )
    return SmeAdjustmentResult(
        adjusted_multiple,
        [
            f"Growth stage adjustment (-{float(adjustment_pct):.1f}%): "
            f"startup stage (higher risk) per founded year and historical data analysis"
        ],
    )


def _calibration_has_owner_dependency(sme_calibration: Optional[Mapping[str, object]]) -> bool:
    return (
        isinstance(sme_calibration, Mapping)
        and sme_calibration.get("owner_dependency_impact") is not None
    )


def _resolve_owner_dependency(
    *,
    config: object,
    business_type: str,
    sme_calibration: Optional[Mapping[str, object]],
    fallback_resolver: Callable[[Optional[str]], Optional[Decimal]],
) -> Optional[Decimal]:
    if _calibration_has_owner_dependency(sme_calibration):
        owner_dep = getattr(config, "owner_dependency_impact", None)
        if owner_dep is not None:
            return owner_dep
    return fallback_resolver(business_type)


def _apply_owner_dependency_adjustment(
    *, multiple: Decimal, business_type: str, owner_dep: Optional[Decimal]
) -> SmeAdjustmentResult:
    if owner_dep is not None and owner_dep >= Decimal("0.7"):
        return SmeAdjustmentResult(
            multiple * Decimal("0.85"),
            [
                f"Owner dependency adjustment (-15%) per business type '{business_type}' "
                f"(dependency impact: {float(owner_dep):.1%})"
            ],
        )

    if owner_dep is not None and owner_dep >= Decimal("0.4"):
        return SmeAdjustmentResult(
            multiple * Decimal("0.92"),
            [
                f"Owner dependency adjustment (-8%) per business type '{business_type}' "
                f"(dependency impact: {float(owner_dep):.1%})"
            ],
        )

    return SmeAdjustmentResult(multiple, [])


def _typical_margin(config: object) -> Optional[Decimal]:
    margin_min = getattr(config, "typical_ebitda_margin_min", None)
    margin_max = getattr(config, "typical_ebitda_margin_max", None)
    if margin_min is not None and margin_max is not None:
        return (margin_min + margin_max) / 2
    return None


def _apply_margin_adjustment(
    *,
    multiple: Decimal,
    business_type: str,
    revenue: Decimal,
    ebitda: Optional[Decimal],
    config: object,
) -> SmeAdjustmentResult:
    if not (ebitda and ebitda > Decimal("0") and revenue > Decimal("0")):
        return SmeAdjustmentResult(multiple, [])

    typical_margin = _typical_margin(config)
    if not typical_margin:
        return SmeAdjustmentResult(multiple, [])

    actual_margin = (ebitda / revenue) * Decimal("100")
    if actual_margin >= (typical_margin * Decimal("0.8")):
        return SmeAdjustmentResult(multiple, [])

    return SmeAdjustmentResult(
        multiple * Decimal("0.90"),
        [
            f"Margin adjustment (-10%): actual margin {float(actual_margin):.1f}% "
            f"below typical {float(typical_margin):.1f}% for business type '{business_type}'"
        ],
    )


def apply_business_type_adjustments(
    *,
    multiple: Decimal,
    business_type: Optional[str],
    revenue: Decimal,
    ebitda: Optional[Decimal],
    sme_calibration: Optional[Mapping[str, object]],
    business_type_service_available: bool,
    business_type_service_factory: Callable[[], object] | None,
    owner_dependency_resolver: Callable[[Optional[str]], Optional[Decimal]],
) -> SmeAdjustmentResult:
    if not (
        business_type and business_type_service_available and business_type_service_factory
    ):
        return SmeAdjustmentResult(multiple, [])

    try:
        config = business_type_service_factory().get_business_type(sme_calibration)
        owner_dep = _resolve_owner_dependency(
            config=config,
            business_type=business_type,
            sme_calibration=sme_calibration,
            fallback_resolver=owner_dependency_resolver,
        )
        owner_adjustment = _apply_owner_dependency_adjustment(
            multiple=multiple,
            business_type=business_type,
            owner_dep=owner_dep,
        )
        margin_adjustment = _apply_margin_adjustment(
            multiple=owner_adjustment.multiple,
            business_type=business_type,
            revenue=revenue,
            ebitda=ebitda,
            config=config,
        )
        return SmeAdjustmentResult(
            margin_adjustment.multiple,
            owner_adjustment.rationales + margin_adjustment.rationales,
        )
    except (AttributeError, KeyError, TypeError, ValueError) as exc:
        logger.warning(
            f"Failed to apply business type adjustments for '{business_type}': {exc}",
            exc_info=True,
        )
        return SmeAdjustmentResult(multiple, [])


def build_sme_ebitda_rationale(
    *,
    sme_class: str,
    revenue: Decimal,
    industry_norm: str,
    base_multiple: Decimal,
    source_name: str,
    business_type: Optional[str],
    growth_stage: str,
    adjustment_rationales: list[str],
    multiple: Decimal,
) -> str:
    rationale_parts = [
        f"{sme_class.capitalize()} SME (revenue \u20ac{revenue:,.0f}) "
        f"in {industry_norm} industry: "
        f"{base_multiple}x EBITDA per {source_name}"
    ]

    if business_type:
        rationale_parts.append(f"Business type: {business_type}")

    if growth_stage:
        rationale_parts.append(f"Growth stage: {growth_stage}")

    if adjustment_rationales:
        rationale_parts.extend(adjustment_rationales)
        rationale_parts.append(f"Final adjusted multiple: {multiple:.2f}x")

    return ". ".join(rationale_parts)


def record_ebitda_multiple_provenance(
    *,
    revenue: Decimal,
    industry_norm: str,
    sme_class: str,
    business_type: Optional[str],
    growth_stage: str,
    base_multiple: Decimal,
    adjustment_count: int,
    multiple: Decimal,
    source_name: str,
) -> None:
    try:
        from src.services.academic.calculation_provenance_tracker import get_current_tracker

        tracker = get_current_tracker()
        if tracker is None:
            return

        tracker.record_calculation(
            calculation_id="ebitda_multiple_adjustment",
            inputs={
                "revenue": float(revenue),
                "industry": industry_norm,
                "sme_class": sme_class,
                "business_type": business_type,
                "growth_stage": growth_stage,
                "base_multiple": float(base_multiple),
                "adjustments_applied": adjustment_count,
            },
            outputs={
                "value": float(multiple),
                "source": source_name,
            },
            section_name="Step 2: Industry Benchmarking & Multiple Selection",
            step_number=2,
        )
    except Exception as exc:  # pragma: no cover - defensive only
        logger.debug(
            "Academic provenance: ebitda_multiple_adjustment record failed (non-fatal)",
            error_type=type(exc).__name__,
            error=str(exc),
        )
