"""Pure methodology decision policy for the comprehensive valuation executor."""

from dataclasses import dataclass
from typing import Optional

from src.domain.asset_based_support import (
    has_sufficient_asset_inputs,
    is_ambiguous_head_office_activity,
    is_asset_heavy_by_balance_sheet,
    is_asset_heavy_holding_activity,
    is_holding_company_activity,
    is_net_asset_dominant,
)
from src.domain.valuation_contract import normalize_method_key

_ACTIVITY_CODE_KEYS = ("canonical_nace_code", "nace_code", "activity_code")
_MULTIPLES_METHOD_KEYS = frozenset(
    (
        "ebitda_multiple",
        "multiples",
        "ev_ebitda",
        "sde_multiple",
        "omzet_multiple",
        "revenue_multiple",
        "arr_multiple",
    )
)
_HYBRID_OVERLAY_METHOD_KEYS = frozenset(("upswitch_adaptive", "fiscal_4x"))


@dataclass(frozen=True)
class MethodologyPreference:
    use_dcf: object
    use_multiples: object
    request_methodology: object
    selected_method: object
    selected_method_key: str
    user_weights: object
    is_single_method_override: bool
    path_log_message: str
    path_log_extra: Optional[dict[str, object]] = None


@dataclass(frozen=True)
class MethodologyFinancialContext:
    activity_code: str
    revenue: float
    balance_sheet: Optional[dict[str, object]]
    current_year_ebitda: object
    request_industry: object
    business_type_id: Optional[str] = None


@dataclass(frozen=True)
class RoutingLog:
    message: str
    extra: dict[str, object]


@dataclass(frozen=True)
class MethodologyDecision:
    methodology: object
    downgrade_reason: Optional[str]
    log_message: str
    log_extra: dict[str, object]


@dataclass(frozen=True)
class AssetRoutingOutcome:
    decision: Optional[MethodologyDecision]
    passthrough_log: Optional[RoutingLog] = None


@dataclass(frozen=True)
class FinalMethodologyDecision:
    methodology: object
    downgrade_reason: Optional[str]
    branch: str


def normalize_methodology_token(methodology: Optional[object]) -> str:
    """Normalize methodology input for parity checks without changing public labels."""
    if methodology is None:
        return ""
    if isinstance(methodology, str):
        raw = methodology.strip()
    else:
        raw = (
            getattr(methodology, "value", None)
            or getattr(methodology, "name", None)
            or str(methodology)
        )
        raw = str(raw).strip()
    if not raw:
        return ""
    return "_".join(raw.replace("-", "_").upper().split())


def normalize_activity_code(code: Optional[object]) -> str:
    """Normalize NACE/activity codes for prefix checks such as 64.20 holdings."""
    if code is None:
        return ""
    raw = str(code).strip()
    if not raw:
        return ""
    return raw.replace(" ", "")


def extract_activity_code(request: object, context: Optional[dict[str, object]] = None) -> str:
    """Prefer canonical activity codes when available, then fall back to market aliases."""
    if context:
        for key in _ACTIVITY_CODE_KEYS:
            normalized = normalize_activity_code(context.get(key))
            if normalized:
                return normalized

    for attr in _ACTIVITY_CODE_KEYS:
        normalized = normalize_activity_code(getattr(request, attr, None))
        if normalized:
            return normalized

    business_context = getattr(request, "business_context", None)
    if isinstance(business_context, dict):
        for key in _ACTIVITY_CODE_KEYS:
            normalized = normalize_activity_code(business_context.get(key))
            if normalized:
                return normalized

    return ""


def build_methodology_preference(request: object) -> MethodologyPreference:
    """Apply product-path selected_method semantics before methodology routing."""
    use_dcf = getattr(request, "use_dcf", True)
    use_multiples = getattr(request, "use_multiples", True)
    request_methodology = getattr(request, "methodology", None)
    selected_method = getattr(request, "selected_method", None)
    user_weights = getattr(request, "user_weights", None)
    selected_method_key = normalize_method_key(selected_method)
    is_startup_only_weight = (
        selected_method_key == "startup_valuation"
        and isinstance(user_weights, dict)
        and set(user_weights.keys()) == {"startup_valuation"}
        and float(user_weights.get("startup_valuation") or 0) > 0
    )
    is_single_method_override = bool(
        selected_method_key
        and (not user_weights or is_startup_only_weight)
        and selected_method_key not in _HYBRID_OVERLAY_METHOD_KEYS
    )

    if is_single_method_override:
        if selected_method_key == "dcf":
            use_dcf, use_multiples = True, False
            request_methodology = "DCF"
        elif selected_method_key in _MULTIPLES_METHOD_KEYS:
            use_dcf, use_multiples = False, True
            request_methodology = "MULTIPLES"
        elif selected_method_key in ("adjusted_nav", "asset_based"):
            request_methodology = "ASSET_BASED"
        elif selected_method_key == "startup_valuation":
            use_dcf, use_multiples = False, False
            request_methodology = "STARTUP"
        return MethodologyPreference(
            use_dcf=use_dcf,
            use_multiples=use_multiples,
            request_methodology=request_methodology,
            selected_method=selected_method,
            selected_method_key=selected_method_key,
            user_weights=user_weights,
            is_single_method_override=True,
            path_log_message="📌 Path 2: single-method selection",
            path_log_extra={
                "selected_method": selected_method,
                "override_use_dcf": use_dcf,
                "override_use_multiples": use_multiples,
            },
        )

    if user_weights:
        weight_keys = list(user_weights.keys()) if isinstance(user_weights, dict) else []
        return MethodologyPreference(
            use_dcf=use_dcf,
            use_multiples=use_multiples,
            request_methodology=request_methodology,
            selected_method=selected_method,
            selected_method_key=selected_method_key,
            user_weights=user_weights,
            is_single_method_override=False,
            path_log_message="📌 Path 3: multi-method custom weighted",
            path_log_extra={"user_weights_keys": weight_keys},
        )

    if selected_method_key == "fiscal_4x":
        return MethodologyPreference(
            use_dcf=use_dcf,
            use_multiples=use_multiples,
            request_methodology=request_methodology,
            selected_method=selected_method,
            selected_method_key=selected_method_key,
            user_weights=user_weights,
            is_single_method_override=False,
            path_log_message="📌 Path 4: fiscal reference (HYBRID base, Omni-Calc overlay)",
        )

    return MethodologyPreference(
        use_dcf=use_dcf,
        use_multiples=use_multiples,
        request_methodology=request_methodology,
        selected_method=selected_method,
        selected_method_key=selected_method_key,
        user_weights=user_weights,
        is_single_method_override=False,
        path_log_message="📌 Path 1: Upswitch Adaptive (preset weighting)",
        path_log_extra={"selected_method": selected_method},
    )


def build_financial_context(
    request: object, context: Optional[dict[str, object]] = None
) -> MethodologyFinancialContext:
    current_year_data = getattr(request, "current_year_data", None)
    balance_sheet = _balance_sheet_from_current_year(current_year_data)
    revenue = (
        float(getattr(current_year_data, "revenue", 0) or 0)
        if current_year_data is not None
        else 0.0
    )
    current_year_ebitda = (
        getattr(current_year_data, "ebitda", None) if current_year_data is not None else None
    )
    return MethodologyFinancialContext(
        activity_code=extract_activity_code(request, context),
        revenue=revenue,
        balance_sheet=balance_sheet,
        current_year_ebitda=current_year_ebitda,
        request_industry=getattr(request, "industry", None),
        business_type_id=getattr(request, "business_type_id", None),
    )


#: Catalogue business types that mean "the company IS the property", as opposed
#: to operating businesses that merely share the "Real Estate" industry tag
#: (hotel, bed-breakfast, campground, vacation-rental, property-management).
_PROPERTY_BUSINESS_TYPES = frozenset({"realestate", "real-estate", "real_estate"})
_PROPERTY_FIXED_ASSETS_TO_REVENUE = 3.0


def _is_property_business_type(business_type_id: Optional[str]) -> bool:
    return str(business_type_id or "").strip().lower() in _PROPERTY_BUSINESS_TYPES


def _balance_sheet_reads_as_property(
    balance_sheet: Optional[dict[str, object]],
    revenue: float,
    current_year_ebitda: object,
) -> bool:
    """True when the balance sheet, not just the label, says property: net
    assets dwarf earnings (the existing ≥5× test) or non-current assets are at
    least 3× revenue. Either alone is enough; neither means the label was wrong."""
    if not balance_sheet:
        return False
    if is_net_asset_dominant(balance_sheet, current_year_ebitda):
        return True
    if revenue <= 0:
        return False
    try:
        fixed = balance_sheet.get("fixed_assets")
        if fixed is None:
            total = balance_sheet.get("total_assets")
            current = balance_sheet.get("current_assets")
            if total is None or current is None:
                return False
            fixed = float(total) - float(current)
        return float(fixed) >= revenue * _PROPERTY_FIXED_ASSETS_TO_REVENUE
    except (TypeError, ValueError):
        return False


def _balance_sheet_from_current_year(current_year_data: object) -> Optional[dict[str, object]]:
    if current_year_data is None:
        return None
    return {
        "total_assets": getattr(current_year_data, "total_assets", None),
        "current_assets": getattr(current_year_data, "current_assets", None),
        "fixed_assets": getattr(current_year_data, "fixed_assets", None),
        "cash": getattr(current_year_data, "cash", None),
        "accounts_receivable": getattr(current_year_data, "accounts_receivable", None),
        "inventory": getattr(current_year_data, "inventory", None),
        "total_liabilities": getattr(current_year_data, "total_liabilities", None),
        "current_liabilities": getattr(current_year_data, "current_liabilities", None),
        "total_debt": getattr(current_year_data, "total_debt", None),
        "total_equity": getattr(current_year_data, "total_equity", None),
    }


def resolve_asset_routing(
    financial: MethodologyFinancialContext,
    *,
    requested_methodology_token: str,
    context_methodology_token: str,
) -> AssetRoutingOutcome:
    """Resolve asset-heavy, real-estate, and explicit asset-based routing before DCF policy."""
    activity_code = financial.activity_code
    request_industry = financial.request_industry
    balance_sheet = financial.balance_sheet
    revenue = financial.revenue
    current_year_ebitda = financial.current_year_ebitda

    if is_asset_heavy_holding_activity(activity_code, industry=request_industry):
        return AssetRoutingOutcome(
            decision=_asset_heavy_holding_decision(
                activity_code,
                request_industry,
                requested_methodology_token=requested_methodology_token,
            )
        )

    # A property company whose registered NACE is not 68.1x/68.2x (the first
    # paying advisor's DEBAETS REAL ESTATE is registered 43240 — construction
    # installation) never reaches the real-estate branch above: routing keys on
    # NACE or on holding/patrimony industry tags, and the catalogue's "Real
    # Estate" industry is shared with hotels and B&Bs, so the tag alone cannot
    # route. The explicit property business type CAN — but only when the balance
    # sheet agrees, so an agency an advisor mis-files as "Real Estate" keeps its
    # operating multiple.
    if _is_property_business_type(financial.business_type_id) and _balance_sheet_reads_as_property(
        balance_sheet, revenue, current_year_ebitda
    ):
        return AssetRoutingOutcome(
            decision=_asset_heavy_holding_decision(
                activity_code,
                "vastgoed",
                requested_methodology_token=requested_methodology_token,
            )
        )

    if is_ambiguous_head_office_activity(activity_code, industry=request_industry):
        if is_net_asset_dominant(balance_sheet, current_year_ebitda) or (
            revenue <= 0 and has_sufficient_asset_inputs(balance_sheet)
        ):
            return AssetRoutingOutcome(
                decision=_ambiguous_head_office_asset_decision(
                    activity_code,
                    request_industry,
                    requested_methodology_token=requested_methodology_token,
                )
            )
        return AssetRoutingOutcome(
            decision=None,
            passthrough_log=RoutingLog(
                message="📊 Head-office/holding routed to operating multiples (earnings dominate NAV)",
                extra={
                    "reason": "ambiguous_head_office_earnings_dominant",
                    "activity_code": activity_code,
                    "industry": request_industry,
                },
            ),
        )

    if is_asset_heavy_by_balance_sheet(balance_sheet, current_year_ebitda):
        return AssetRoutingOutcome(
            decision=_asset_based_decision(
                reason="asset_heavy_balance_sheet_heuristic",
                downgrade_reason=(
                    "Asset-heavy balance sheet detected: book equity is at least 5× the "
                    "current-year EBITDA and fixed assets exceed 60% of total assets. "
                    "We used Asset-Based methodology because the value flows from the "
                    "underlying NAV rather than operating multiples."
                    if requested_methodology_token not in ("", "ASSET_BASED")
                    else None
                ),
            )
        )

    if revenue <= 0 and has_sufficient_asset_inputs(balance_sheet):
        return AssetRoutingOutcome(
            decision=_asset_based_decision(
                reason="zero_revenue_balance_sheet_fallback",
                downgrade_reason=(
                    "Revenue is zero while sufficient balance-sheet data is available. "
                    "We used Asset-Based methodology because revenue multiples are not applicable "
                    "and adjusted net asset value is the academically appropriate primary method."
                    if requested_methodology_token not in ("", "ASSET_BASED")
                    else None
                ),
            )
        )

    if context_methodology_token == "ASSET_BASED" or requested_methodology_token == "ASSET_BASED":
        return AssetRoutingOutcome(
            decision=_asset_based_decision(
                reason="explicit_or_context_asset_based_selection",
                downgrade_reason=None,
            )
        )

    return AssetRoutingOutcome(decision=None)


def _asset_heavy_holding_decision(
    activity_code: str,
    request_industry: object,
    *,
    requested_methodology_token: str,
) -> MethodologyDecision:
    normalized_digits = (activity_code or "").replace(".", "").replace(" ", "")
    industry_token = str(request_industry or "").strip().lower().replace("-", "_").replace(" ", "_")
    is_financial_holding = is_holding_company_activity(activity_code or "")
    is_real_estate = (not is_financial_holding) and (
        normalized_digits.startswith(("6810", "6820"))
        or industry_token in ("real_estate_holding", "patrimony", "patrimonium", "vastgoed")
    )
    if is_real_estate:
        activity_suffix = f" (activiteitscode {activity_code})" if activity_code else ""
        return MethodologyDecision(
            methodology="REAL_ESTATE_YIELD",
            downgrade_reason=(
                f"Vastgoedvennootschap gedetecteerd{activity_suffix}. "
                "We hanteren de income-capitalisation methode — duurzame nettohuur gedeeld "
                "door een marktconforme cap-rate, met de boekwaarde-NAV als vloer — omdat "
                "voor een vastgoedvennootschap het huurrendement de primaire waardedriver "
                "is, niet operationele EBITDA-multiples."
            ),
            log_message="📊 Methodology: REAL_ESTATE_YIELD",
            log_extra={
                "determined_methodology": "REAL_ESTATE_YIELD",
                "reason": "real_estate_holding_yield_routing",
                "activity_code": activity_code,
                "industry": request_industry,
            },
        )

    return MethodologyDecision(
        methodology="ASSET_BASED",
        downgrade_reason=(
            f"Financial holding activity detected via NACE/activity code {activity_code}. "
            "We used Asset-Based methodology because financial holdings are primarily "
            "valued on their underlying balance sheet rather than operating multiples."
            if requested_methodology_token not in ("", "ASSET_BASED")
            else None
        ),
        log_message="📊 Methodology: ASSET_BASED",
        log_extra={
            "determined_methodology": "ASSET_BASED",
            "reason": "asset_heavy_holding_activity_routing",
            "activity_code": activity_code,
            "industry": request_industry,
        },
    )


def _ambiguous_head_office_asset_decision(
    activity_code: str,
    request_industry: object,
    *,
    requested_methodology_token: str,
) -> MethodologyDecision:
    subject = activity_code or f"industry tag '{request_industry}'"
    return MethodologyDecision(
        methodology="ASSET_BASED",
        downgrade_reason=(
            f"Head-office / holding activity ({subject}) whose net assets dwarf its "
            "earnings stream. We used Asset-Based methodology because the value is "
            "stored in the balance sheet (participations, cash), not in a thin "
            "management-fee P&L."
            if requested_methodology_token not in ("", "ASSET_BASED")
            else None
        ),
        log_message="📊 Methodology: ASSET_BASED",
        log_extra={
            "determined_methodology": "ASSET_BASED",
            "reason": "ambiguous_head_office_net_asset_dominant",
            "activity_code": activity_code,
            "industry": request_industry,
        },
    )


def _asset_based_decision(reason: str, downgrade_reason: Optional[str]) -> MethodologyDecision:
    return MethodologyDecision(
        methodology="ASSET_BASED",
        downgrade_reason=downgrade_reason,
        log_message="📊 Methodology: ASSET_BASED",
        log_extra={
            "determined_methodology": "ASSET_BASED",
            "reason": reason,
        },
    )


def resolve_final_methodology(
    preference: MethodologyPreference,
    *,
    context_methodology: object,
    requested_methodology_token: str,
    should_calculate_dcf: bool,
    dcf_exclusion_reason: Optional[str],
) -> FinalMethodologyDecision:
    """Resolve the final DCF/multiples methodology after asset routing has passed."""
    if preference.use_dcf and preference.use_multiples and should_calculate_dcf:
        return FinalMethodologyDecision(
            methodology="HYBRID",
            downgrade_reason=None,
            branch="forced_hybrid",
        )

    if preference.use_dcf and preference.use_multiples and not should_calculate_dcf:
        downgrade_reason = (
            f"HYBRID methodology was requested, but DCF was excluded. {dcf_exclusion_reason}. "
            "We used Market Multiples methodology only. This approach is more reliable "
            "for small businesses and aligns with Big 4 and NACVA valuation standards."
            if requested_methodology_token == "HYBRID"
            else None
        )
        return FinalMethodologyDecision(
            methodology="MULTIPLES",
            downgrade_reason=downgrade_reason,
            branch="dcf_excluded_to_multiples",
        )

    if context_methodology:
        methodology = (
            context_methodology.upper()
            if isinstance(context_methodology, str)
            else context_methodology
        )
        return FinalMethodologyDecision(
            methodology=methodology,
            downgrade_reason=None,
            branch="context_methodology",
        )

    if preference.request_methodology:
        request_methodology = preference.request_methodology
        methodology = (
            request_methodology.upper()
            if isinstance(request_methodology, str)
            else request_methodology
        )
        return FinalMethodologyDecision(
            methodology=methodology,
            downgrade_reason=None,
            branch="request_methodology",
        )

    if preference.use_dcf:
        methodology = "DCF"
    elif preference.use_multiples:
        methodology = "MULTIPLES"
    else:
        methodology = "HYBRID"
    return FinalMethodologyDecision(
        methodology=methodology,
        downgrade_reason=None,
        branch="inferred_from_flags",
    )
