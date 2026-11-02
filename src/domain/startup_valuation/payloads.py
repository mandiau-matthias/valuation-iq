"""Per-leg JSON payload helpers (engine ↔ report context boundary).

The synthesis blender is the sole consumer of these helpers — they
exist so :mod:`.synthesis` doesn't carry 100+ lines of serialization
boilerplate inline (KISS / DRY).  Decimals are converted to floats
*here* and only here; the engine itself never produces a float.
"""

from __future__ import annotations

from typing import Any, Dict

from .berkus import BerkusOutput
from .money import safe_float
from .saas_forward import SaasForwardOutput
from .scorecard import ScorecardOutput
from .vc_method import VcOutput


def berkus_payload(berkus: BerkusOutput) -> Dict[str, Any]:
    return {
        "pre_money": safe_float(berkus.pre_money),
        "max_per_milestone": safe_float(berkus.max_per_milestone),
        "max_total": safe_float(berkus.max_total),
        "contributions": [
            {
                "key": c.key,
                "label": c.label,
                "score_pct": c.score_pct,
                "max_value": safe_float(c.max_value),
                "value": safe_float(c.value),
            }
            for c in berkus.contributions
        ],
    }


def scorecard_payload(scorecard: ScorecardOutput) -> Dict[str, Any]:
    return {
        "pre_money": safe_float(scorecard.pre_money),
        "average_pre_money": safe_float(scorecard.average_pre_money),
        "blended_multiplier": safe_float(scorecard.blended_multiplier),
        "factors": [
            {
                "key": f.key,
                "label": f.label,
                "score_pct": f.score_pct,
                "weight": safe_float(f.weight),
                "multiplier": safe_float(f.multiplier),
                "weighted_multiplier": safe_float(f.weighted_multiplier),
            }
            for f in scorecard.factors
        ],
    }


def vc_payload(vc: VcOutput) -> Dict[str, Any]:
    return {
        "pre_money": safe_float(vc.pre_money),
        "post_money": safe_float(vc.post_money),
        "terminal_value": safe_float(vc.terminal_value),
        "year5_revenue": safe_float(vc.year5_revenue),
        "exit_revenue_multiple": safe_float(vc.exit_revenue_multiple),
        "target_roi_x": safe_float(vc.target_roi_x),
        "dilution_pct": safe_float(vc.dilution_pct),
        "used_year5_projection": vc.used_year5_projection,
        # Consortium-spec additions: surface the founder's ask + the
        # implied next-round dilution so the report's cap-table
        # simulator (and the screen-side defensibility list) can render
        # the "if you raise €X you dilute Y%" line.
        "investment_amount_sought": safe_float(vc.investment_amount_sought),
        "used_investment_amount": vc.used_investment_amount,
        "next_round_dilution_pct": safe_float(vc.next_round_dilution_pct),
    }


def saas_forward_payload(sf: SaasForwardOutput) -> Dict[str, Any]:
    return {
        "pre_money": safe_float(sf.pre_money),
        "current_arr": safe_float(sf.current_arr),
        "forward_arr": safe_float(sf.forward_arr),
        "forward_mom_growth_pct": safe_float(sf.forward_mom_growth_pct),
        "forward_months": int(sf.forward_months),
        "base_multiple": safe_float(sf.base_multiple),
        "applied_multiple": safe_float(sf.applied_multiple),
        "risk_discount": safe_float(sf.risk_discount),
        "churn_drag": safe_float(sf.churn_drag),
        "available": bool(sf.available),
        "unavailable_reason": sf.unavailable_reason,
    }
