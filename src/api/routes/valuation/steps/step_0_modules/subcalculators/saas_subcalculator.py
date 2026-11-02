"""SaaS sub-calculation in the Step-0 pipeline.

Always returns a payload (never ``None``) when the SaaS path is open at all,
so downstream layers see *why* the path was inactive — eligibility verdict,
validation flags, and suggested alternative — rather than a silent miss.
"""

from decimal import Decimal
from typing import Any, Dict, Optional

from src.domain.asset_based_support import normalize_business_model
from src.domain.saas_valuation_adjuster import compute_saas_adjustment
from src.utils.adaptive_input_helpers import (
    get_business_context,
    get_recurring_revenue_override,
    is_saas_context,
)


class SaaSSubcalculator:
    key = "saas_analysis"

    def applies(self, request: Any) -> bool:
        raw_model = getattr(request, "business_model", None)
        normalized_model = normalize_business_model(raw_model).value if raw_model else None
        return is_saas_context(
            business_context=get_business_context(request),
            business_type_id=getattr(request, "business_type_id", None),
            business_model=normalized_model,
            industry=getattr(request, "industry", None),
        )

    def calculate(self, request: Any) -> Optional[Dict[str, Any]]:
        if not self.applies(request):
            return None

        current_year = getattr(request, "current_year_data", None)
        revenue = getattr(current_year, "revenue", Decimal("0")) if current_year else Decimal("0")
        revenue_decimal = Decimal(str(revenue or 0))
        recurring_revenue_percentage = get_recurring_revenue_override(request)
        adjustment = compute_saas_adjustment(
            revenue=revenue_decimal,
            recurring_revenue_percentage=recurring_revenue_percentage,
            business_context=get_business_context(request),
            country_code=str(getattr(request, "country_code", "BE") or "BE"),
            business_type_id=getattr(request, "business_type_id", None),
        )

        eligibility_payload = (
            adjustment.eligibility.as_dict() if adjustment.eligibility is not None else None
        )
        validation_payload = (
            adjustment.validation.to_payload()
            if adjustment.validation is not None and adjustment.validation.flags
            else []
        )

        # Ineligible / missing-ARR path — surface diagnostics instead of
        # returning None. Downstream sees `applicable=False` plus the
        # blocking reasons, suggested alternative, and validation flags.
        if not adjustment.is_saas or adjustment.arr_multiple is None or not adjustment.is_eligible:
            payload: Dict[str, Any] = {
                "applicable": False,
                "arr_multiple": (
                    float(adjustment.arr_multiple)
                    if adjustment.arr_multiple is not None
                    else None
                ),
                "ebitda_adjustment_factor": float(adjustment.ebitda_adjustment_factor),
                "metrics": adjustment.computed_metrics or {},
                "adjustment_breakdown": adjustment.adjustment_breakdown or [],
                "eligibility": eligibility_payload,
                "validation_flags": validation_payload,
            }
            return payload

        metrics = adjustment.computed_metrics
        arr_growth_pct = metrics.get("arr_growth_pct") or 0
        nrr_pct = metrics.get("nrr_pct") or 0
        high_growth = arr_growth_pct >= 30 or nrr_pct >= 110
        revenue_threshold = 1_000_000 if high_growth else 5_000_000

        return {
            "applicable": True,
            "arr_multiple": float(adjustment.arr_multiple),
            "ebitda_adjustment_factor": float(adjustment.ebitda_adjustment_factor),
            "metrics": metrics,
            "adjustment_breakdown": adjustment.adjustment_breakdown,
            "eligibility": eligibility_payload,
            "validation_flags": validation_payload,
            "signals": {
                "high_growth": high_growth,
                "arr_growth_pct": arr_growth_pct,
                "nrr_pct": nrr_pct,
                "rule_of_40": metrics.get("rule_of_40"),
            },
            "dcf_context": {
                "revenue_threshold": revenue_threshold,
                "arr_projection_basis": metrics.get("arr"),
                "nrr_pct": nrr_pct,
                "high_growth": high_growth,
            },
        }
