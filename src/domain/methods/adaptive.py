"""UpSwitch Adaptive method — headline equity whose semantics depend on primary_basis."""

import math
from decimal import Decimal
from typing import Literal, Optional

from src.api.schemas.method_details import build_adaptive_details
from src.api.schemas.stateless_api import MethodResult
from src.domain.saas_valuation_adjuster import SaasAdjustmentResult

from ._shared import default_methodology_justification


def calculate_adaptive_result(
    *,
    primary_basis: Literal["hybrid", "asset_based"],
    equity_value_mid: Decimal,
    adaptive_multiple_used: Optional[float],
    ev_ebitda_multiple: float,
    equity_value_low: Optional[Decimal],
    equity_value_high: Optional[Decimal],
    saas_adjustment: Optional[SaasAdjustmentResult],
    methodology_justification: Optional[str],
    enterprise_value_mid: Optional[Decimal] = None,
    enterprise_value_low: Optional[Decimal] = None,
    enterprise_value_high: Optional[Decimal] = None,
) -> MethodResult:
    """UpSwitch Adaptive headline equity — the engine's blended valuation.

    Semantics depend on ``primary_basis``: a hybrid market-multiple/DCF blend
    for going-concern SMEs, or the asset-based NAV route when the company is
    balance-sheet driven. The numeric blend itself is computed upstream; this
    adapter packages it as a ``MethodResult`` with the matching detail payload.
    """
    if equity_value_mid is None or equity_value_mid <= 0:
        return MethodResult(
            value=None,
            method_key="upswitch_adaptive",
            label="UpSwitch Adaptive",
            available=False,
            unavailable_reason="Berekende aandelenwaarde is nul of negatief.",
        )

    range_low: Optional[float] = None
    range_high: Optional[float] = None
    if (
        equity_value_low is not None
        and equity_value_high is not None
        and equity_value_low > 0
        and equity_value_high > 0
    ):
        lo = float(equity_value_low)
        hi = float(equity_value_high)
        range_low = round(min(lo, hi), 2)
        range_high = round(max(lo, hi), 2)

    saas_metrics = saas_adjustment.computed_metrics if saas_adjustment else None
    saas_breakdown = saas_adjustment.adjustment_breakdown if saas_adjustment else None
    # Only advertise the ARR multiple as a secondary method when the SaaS
    # lens is *eligible* — otherwise the report would suggest triangulating
    # against a method we just disqualified.
    saas_eligible = bool(
        saas_adjustment
        and getattr(saas_adjustment, "eligibility", None) is not None
        and saas_adjustment.eligibility.eligible
    )
    sec_key = "arr_multiple" if saas_eligible else None
    sec_label = "ARR multiple" if saas_eligible else None

    if primary_basis == "asset_based":
        details = build_adaptive_details(
            description=(
                "Hoofdwaardering volgt de gecorrigeerde netto actiefwaarde (NAV); "
                "niet op gewogen marktmultiples of DCF."
            ),
            primary_basis="asset_based",
            methodology_justification=methodology_justification
            or default_methodology_justification(primary_basis),
            primary_method_key="adjusted_nav",
            equity_range_low=range_low,
            equity_range_high=range_high,
            saas_metrics=saas_metrics,
            saas_adjustment_breakdown=saas_breakdown,
            secondary_method_key=sec_key,
            secondary_method_label=sec_label,
        )
        label = "UpSwitch Adaptive (balans primair)"
        multiple = None
    else:
        details = build_adaptive_details(
            description="Gewogen combinatie van marktmultiples en DCF, afgestemd op bedrijfstype.",
            primary_basis="hybrid",
            methodology_justification=methodology_justification
            or default_methodology_justification(primary_basis),
            equity_range_low=range_low,
            equity_range_high=range_high,
            saas_metrics=saas_metrics,
            saas_adjustment_breakdown=saas_breakdown,
            secondary_method_key=sec_key,
            secondary_method_label=sec_label,
        )
        label = "UpSwitch Adaptive"
        raw = adaptive_multiple_used if adaptive_multiple_used is not None else ev_ebitda_multiple
        multiple = Decimal(str(round(raw, 4))) if raw is not None and math.isfinite(raw) else None

    return MethodResult(
        value=equity_value_mid,
        enterprise_value=enterprise_value_mid if primary_basis != "asset_based" else None,
        enterprise_value_low=enterprise_value_low if primary_basis != "asset_based" else None,
        enterprise_value_high=enterprise_value_high if primary_basis != "asset_based" else None,
        value_low=Decimal(str(range_low)) if range_low is not None else None,
        value_high=Decimal(str(range_high)) if range_high is not None else None,
        method_key="upswitch_adaptive",
        label=label,
        multiple_used=multiple,
        available=True,
        details=details,
    )
