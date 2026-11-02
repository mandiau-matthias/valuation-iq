"""
Primary valuation method selection support for Step 2 benchmarking.
"""

from __future__ import annotations

from decimal import Decimal

from src.api.routes.valuation.triage.business_type_triage import BusinessTypeCategory


async def determine_primary_method_for_request(
    *,
    request,
    ebitda,
    ebitda_margin,
    revenue,
    business_type_id: str | None,
    business_category: BusinessTypeCategory | None,
    data_quality_coordinator,
    multiples_calculator,
    logger,
) -> str:
    growth_rate = data_quality_coordinator.calculate_growth_rate(request)
    valuation_preferences = getattr(request, "valuation_preferences", None)
    user_selected_method = getattr(request, "selected_method", None)
    effective_ebitda = ebitda
    effective_margin = ebitda_margin

    current_year = getattr(request, "current_year_data", None)
    current_revenue = getattr(current_year, "revenue", None) if current_year else None
    current_ebitda = getattr(current_year, "ebitda", None) if current_year else None
    if current_revenue and current_revenue > 0 and current_ebitda is not None:
        current_margin = (current_ebitda / current_revenue) * Decimal("100")
        if current_ebitda > 0 and current_margin >= Decimal("3"):
            effective_ebitda = current_ebitda
            effective_margin = current_margin

    primary_method = multiples_calculator.determine_primary_method(
        effective_ebitda,
        effective_margin,
        revenue=revenue,
        business_type_id=business_type_id,
        business_category=business_category,
        growth_rate=growth_rate,
        valuation_preferences=valuation_preferences,
        user_selected_method=user_selected_method,
    )

    logger.debug(
        "Step 2: Primary method determined",
        extra={
            "step_number": 2,
            "primary_method": primary_method,
            "user_selected_method": user_selected_method,
            "business_type_id": business_type_id,
            "growth_rate": str(growth_rate) if growth_rate else None,
            "effective_ebitda": (
                str(effective_ebitda) if effective_ebitda is not None else None
            ),
            "effective_margin": (
                str(effective_margin) if effective_margin is not None else None
            ),
        },
    )

    return primary_method
