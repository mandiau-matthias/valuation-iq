"""
Business category selection support for Step 2 benchmarking.
"""

from __future__ import annotations


async def determine_business_category(*, request, business_type_triage, logger):
    business_type_id = getattr(request, "business_type_id", None)
    business_model = getattr(request, "business_model", None)
    industry = getattr(request, "industry", None)
    category_id = getattr(request, "category_id", None)

    business_category = business_type_triage.get_business_type_category(
        business_type_id, business_model, industry, category_id=category_id
    )

    logger.debug(
        "Step 2: Business type category determined",
        extra={
            "business_type_id": business_type_id,
            "business_model": business_model,
            "industry": industry,
            "category": getattr(business_category, "value", "unknown"),
        },
    )

    return business_category, business_type_id
