"""Post-build enrichment and arithmetic integrity for main report contexts."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Callable, Mapping, Protocol, TypeAlias

from src.services.infrastructure.translations import ReportTranslations
from src.services.reports.advisor_multiple_transparency_context import (
    enrich_advisor_multiple_transparency_context,
)
from src.services.reports.report_bridge_helpers import (
    build_bridge_residual_context,
    compute_ev_equity_bridge_residual,
)
from src.services.reports.report_calibration_waterfall import build_valuation_waterfall_steps
from src.services.reports.report_sections.advisor_analysis_section import (
    build_advisor_analysis_context,
)
from src.services.reports.report_track_context import apply_methodology_report_context
from src.services.reports.weighted_synthesis_context import (
    promote_weighted_synthesis_headline_context,
)
from src.utils.decimal_helpers import safe_decimal_or_zero, safe_float

JsonMap: TypeAlias = dict[str, object]


class LoggerLike(Protocol):
    def warning(self, msg: str, *args: object, **kwargs: object) -> object: ...


@dataclass(frozen=True)
class MainReportMethodologyContext:
    request_metadata: Mapping[str, object] | None
    dcf_data: JsonMap
    sde_data: JsonMap
    sde_cross_check: JsonMap
    hybrid_data: JsonMap
    report_intelligence: JsonMap
    promote_upswitch_adaptive: Callable[[], None] | None = None


@dataclass(frozen=True)
class BridgeCashSplitContext:
    show_bridge_cash_split: bool
    bridge_cash_total: Decimal
    bridge_operating_cash_held: Decimal
    bridge_excess_cash: Decimal
    bridge_ib_debt: Decimal


def apply_main_report_post_build_context(
    context: JsonMap,
    *,
    response: object,
    request: object | None,
    locale: str,
    report_locale: str,
    translations: ReportTranslations,
    methodology: MainReportMethodologyContext,
    bridge_cash_split: BridgeCashSplitContext,
    logger: LoggerLike,
) -> None:
    """Apply post-build report sections and final arithmetic context mutations."""
    # Enrichment builds display captions before final validation stamps locale.
    # Set it now so bridge and multiple labels use the requested report language.
    context["locale"] = report_locale
    apply_main_report_methodology_context(
        context,
        response=response,
        request=request,
        locale=locale,
        report_locale=report_locale,
        translations=translations,
        methodology=methodology,
        logger=logger,
    )
    apply_final_report_math_context(
        context,
        request=request,
        translations=translations,
        bridge_cash_split=bridge_cash_split,
        logger=logger,
    )


def apply_main_report_methodology_context(
    context: JsonMap,
    *,
    response: object,
    request: object | None,
    locale: str,
    report_locale: str,
    translations: ReportTranslations,
    methodology: MainReportMethodologyContext,
    logger: LoggerLike,
) -> None:
    """Apply methodology pages, weighted synthesis promotion, and advisor sections."""
    apply_methodology_report_context(
        context,
        response=response,
        request=request,
        locale=locale,
        report_locale=report_locale,
        translations=translations,
        request_metadata=methodology.request_metadata,
        dcf_data=methodology.dcf_data,
        sde_data=methodology.sde_data,
        sde_cross_check=methodology.sde_cross_check,
        hybrid_data=methodology.hybrid_data,
        report_intelligence=methodology.report_intelligence,
        promote_upswitch_adaptive=methodology.promote_upswitch_adaptive,
        logger=logger,
    )

    # Promote before advisor analysis: advisor sections read the canonical
    # headline equity/EV and must not anchor on the pre-synthesis hybrid stage.
    promote_weighted_synthesis_headline_context(context)
    build_advisor_analysis_context(context, response=response, request=request, locale=locale)


def apply_final_report_math_context(
    context: JsonMap,
    *,
    request: object | None,
    translations: ReportTranslations,
    bridge_cash_split: BridgeCashSplitContext,
    logger: LoggerLike,
) -> None:
    """Finalize post-build arithmetic fields that must match rendered rows."""
    _apply_bridge_cash_split_context(context, bridge_cash_split)
    if context.get("equity_value") is None:
        context.update(
            {
                "show_ev_equity_bridge": False,
                "show_enterprise_to_equity_bridge": False,
                "has_net_debt_adjustment": False,
                "has_bridge_residual": False,
                "bridge_residual": None,
                "recommended_asking_price": None,
            }
        )
        transparency = context.get("advisor_multiple_transparency")
        if isinstance(transparency, dict):
            transparency.pop("equity_bridge", None)
        return
    final_eq, final_ev, final_net_debt = _recompute_final_bridge_residual(context)
    _apply_minority_interest_context(context, request=request, final_eq=final_eq)
    _rebuild_weighted_synthesis_waterfall(
        context,
        translations=translations,
        final_eq=final_eq,
        final_ev=final_ev,
        final_net_debt=final_net_debt,
        logger=logger,
    )
    enrich_advisor_multiple_transparency_context(context)


def _apply_bridge_cash_split_context(
    context: JsonMap,
    bridge_cash_split: BridgeCashSplitContext,
) -> None:
    context["show_bridge_cash_split"] = bridge_cash_split.show_bridge_cash_split
    context["bridge_cash_total"] = bridge_cash_split.bridge_cash_total
    context["bridge_operating_cash_held"] = bridge_cash_split.bridge_operating_cash_held
    context["bridge_excess_cash"] = bridge_cash_split.bridge_excess_cash
    context["bridge_ib_debt"] = bridge_cash_split.bridge_ib_debt


def _recompute_final_bridge_residual(context: JsonMap) -> tuple[Decimal, Decimal, Decimal]:
    final_eq = safe_decimal_or_zero(context.get("equity_value"))
    final_ev = safe_decimal_or_zero(context.get("enterprise_value_mid"))
    final_bridge_amount = safe_decimal_or_zero(context.get("bridge_net_debt_amount"))
    final_net_debt = (
        (
            -final_bridge_amount
            if str(context.get("bridge_net_debt_operator") or "") == "+"
            else final_bridge_amount
        )
        if context.get("has_net_debt_adjustment")
        else Decimal("0")
    )

    context.update(
        build_bridge_residual_context(
            compute_ev_equity_bridge_residual(
                enterprise_value_mid=final_ev,
                equity_value=final_eq,
                net_debt=final_net_debt,
                tax_latency_net_impact=safe_decimal_or_zero(
                    context.get("tax_latency_net_impact") or 0
                ),
                balance_sheet_adjustments=list(context.get("balance_sheet_adjustments") or []),
                nwc_surplus_deficit=safe_decimal_or_zero(context.get("bridge_nwc_adjustment") or 0),
            ),
            enterprise_value_mid=final_ev,
        )
    )
    return final_eq, final_ev, final_net_debt


def _apply_minority_interest_context(
    context: JsonMap,
    *,
    request: object | None,
    final_eq: Decimal,
) -> None:
    current_year_data = getattr(request, "current_year_data", None) if request is not None else None
    minority_booked = safe_decimal_or_zero(
        getattr(current_year_data, "minority_interest_result_share", None) or 0
    )
    if minority_booked <= 0:
        return

    context["has_minority_interest"] = True
    seller_eq = final_eq - minority_booked
    if final_eq <= 0 or seller_eq <= 0:
        return

    context["minority_interest_amount"] = safe_float(minority_booked)
    context["minority_seller_equity"] = safe_float(seller_eq)
    context["minority_interest_pending"] = True

    ask_now = safe_decimal_or_zero(context.get("recommended_asking_price") or 0)
    ask_post = min(ask_now, seller_eq) if ask_now > 0 else seller_eq
    context["recommended_asking_price"] = safe_float(ask_post)
    context["asking_price_reflects_minority"] = True
    context["recommended_asking_price_buffer_suppressed"] = True


def _rebuild_weighted_synthesis_waterfall(
    context: JsonMap,
    *,
    translations: ReportTranslations,
    final_eq: Decimal,
    final_ev: Decimal,
    final_net_debt: Decimal,
    logger: LoggerLike,
) -> None:
    if not _should_rebuild_weighted_synthesis_waterfall(
        context, final_ev=final_ev, final_eq=final_eq
    ):
        return

    try:
        context["valuation_waterfall_steps"] = build_valuation_waterfall_steps(
            **_weighted_synthesis_waterfall_kwargs(
                context,
                translations=translations,
                final_eq=final_eq,
                final_ev=final_ev,
                final_net_debt=final_net_debt,
            )
        )
    except Exception:
        logger.warning("synthesis_waterfall_rebuild_failed", exc_info=True)


def _should_rebuild_weighted_synthesis_waterfall(
    context: JsonMap,
    *,
    final_ev: Decimal,
    final_eq: Decimal,
) -> bool:
    return bool(context.get("has_weighted_synthesis")) and final_ev > 0 and final_eq > 0


def _weighted_synthesis_waterfall_kwargs(
    context: JsonMap,
    *,
    translations: ReportTranslations,
    final_eq: Decimal,
    final_ev: Decimal,
    final_net_debt: Decimal,
) -> JsonMap:
    return {
        "valuation_basis_value": _context_decimal(context, "valuation_basis_value"),
        "metric_type": str(context.get("multiple_metric_type") or "EBITDA"),
        "applied_multiple": _context_decimal(context, "applied_multiple"),
        "enterprise_value_mid": final_ev,
        "total_debt": _context_decimal(context, "total_debt"),
        "cash_balance": _context_decimal(context, "cash_balance"),
        "excess_cash": _context_decimal(context, "excess_cash"),
        "exemption_applied": bool(context.get("exemption_applied")),
        "net_debt": final_net_debt,
        "tax_latency_net_impact": _context_decimal(context, "tax_latency_net_impact"),
        "balance_sheet_adjustments": _context_list(context, "balance_sheet_adjustments"),
        "nwc_surplus_deficit": _context_decimal(context, "bridge_nwc_adjustment"),
        "equity_value": final_eq,
        "include_metric_bridge": False,
        "t": translations,
    }


def _context_decimal(context: JsonMap, key: str) -> Decimal:
    return safe_decimal_or_zero(context.get(key) or 0)


def _context_list(context: JsonMap, key: str) -> list[object]:
    value = context.get(key)
    return list(value) if isinstance(value, list) else []
