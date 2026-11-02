"""Additional section context assembly for main report aggregation."""

from __future__ import annotations

from dataclasses import dataclass

from src.services.reports.report_business_growth_maturity_context import (
    build_business_growth_maturity_report_context,
)
from src.services.reports.report_owner_profiling_cover import build_cover_owner_profiling_cover
from src.services.reports.report_owner_profiling_section import (
    build_owner_profiling_section_context,
    build_post_deal_swap_context,
    build_transferability_v2_context,
)
from src.services.reports.report_sellability_context import build_sellability_section_context
from src.services.reports.report_stage_aware_breakdown_context import (
    build_stage_aware_breakdown_context,
)

JsonMap = dict[str, object]


@dataclass(frozen=True)
class MainReportAdditionalSectionContexts:
    cover_owner_profiling: JsonMap
    owner_profiling_section: JsonMap
    sellability_section: JsonMap
    stage_aware_breakdown: JsonMap
    business_growth_maturity: JsonMap


def build_main_report_additional_section_contexts(
    *,
    response: object,
    translations: object,
    step_data: JsonMap,
    is_owner_dep_methodology: bool,
    is_asset_anchored: bool,
    request: object | None,
    locale: str = "en",
) -> MainReportAdditionalSectionContexts:
    """Build report sections that sit outside the core valuation waterfall."""
    cover_owner_profiling = build_cover_owner_profiling_cover(
        response,
        translations,
        step_data,
    )
    owner_profiling_section = build_owner_profiling_section_context(
        response,
        translations,
        is_owner_dep_methodology=is_owner_dep_methodology,
        build_post_deal_swap_context=build_post_deal_swap_context,
        build_transferability_v2_context=build_transferability_v2_context,
    )
    sellability_section = build_sellability_section_context(
        response,
        translations,
        is_owner_dep_methodology=is_owner_dep_methodology,
        request=request,
    )
    if is_asset_anchored:
        owner_profiling_section = {
            "show_owner_profiling_section": False,
            "owner_profiling": None,
        }
        sellability_section = {
            **sellability_section,
            "show_sellability_section": False,
            "sellability": None,
        }

    return MainReportAdditionalSectionContexts(
        cover_owner_profiling=cover_owner_profiling,
        owner_profiling_section=owner_profiling_section,
        sellability_section=sellability_section,
        stage_aware_breakdown=build_stage_aware_breakdown_context(response, translations),
        business_growth_maturity=build_business_growth_maturity_report_context(
            response,
            request,
            locale=locale,
        ),
    )
