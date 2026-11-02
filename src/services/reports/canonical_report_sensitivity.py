"""Explicit report-only sensitivity scenarios tied to a saved valuation run.

The saved conclusion is never recalculated or replaced. Each illustrative
matrix carries its own content identity and all varied/held assumptions.
"""

import hashlib
import json
from decimal import Decimal, localcontext

from src.domain.financial_arithmetic import money
from src.services.reports.report_value_admission import admitted_band, report_decimal


def multiple_report_sensitivity(
    *,
    run_id: str,
    run_hash: str,
    metric: object,
    multiple: object,
    enterprise_value: object,
    metric_type: str,
    currency: str,
    valuation_date: str,
) -> dict[str, object] | None:
    if metric is None or multiple is None or enterprise_value is None:
        return None
    basis = report_decimal(metric, "pricing metric")
    applied = report_decimal(multiple, "effective multiple")
    saved_ev = report_decimal(enterprise_value, "saved enterprise value")
    if basis <= 0 or applied <= 0:
        return None
    with localcontext() as context:
        context.prec = 100
        # A blended, asset or DCF conclusion must not acquire an EBITDA grid
        # merely because a secondary multiple happens to be present.
        if money(basis * applied) != money(saved_ev):
            return None
        factors = (Decimal(".8"), Decimal("1"), Decimal("1.2"))
        columns = [{"factor": str(factor), "multiple": str(applied * factor)} for factor in factors]
        rows = [
            {
                "factor": str(factor),
                "metric": str(basis * factor),
                "values": [
                    str(money(basis * factor * applied * multiple_factor))
                    for multiple_factor in factors
                ],
            }
            for factor in factors
        ]
    scenario: dict[str, object] = {
        "schema_version": "report_multiple_sensitivity.v1",
        "source_run_id": run_id,
        "source_run_hash": run_hash,
        "value_basis": "enterprise_value",
        "kind": "illustrative_sensitivity",
        "currency": currency,
        "valuation_date": valuation_date,
        "metric_type": metric_type,
        "pricing_metric": str(basis),
        "effective_multiple": str(applied),
        "saved_enterprise_value": str(saved_ev),
        "metric_factors": ["0.8", "1", "1.2"],
        "multiple_factors": ["0.8", "1", "1.2"],
        "held_assumptions": "All other saved model assumptions; no new EV-to-equity bridge",
        "statistical_coverage": None,
        "columns": columns,
        "rows": rows,
    }
    encoded = json.dumps(scenario, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    scenario["calculation_id"] = hashlib.sha256(encoded.encode()).hexdigest()
    return scenario


def apply_multiple_report_sensitivity(context: dict[str, object], run: object | None) -> None:
    if run is None:
        return
    # Reference cohort bounds are not the adjusted multiple bounds. Keep
    # reference evidence in its own table, not beside the effective multiple.
    context["multiple_low"] = None
    context["multiple_high"] = None
    context["canonical_multiple_sensitivity"] = None
    context["canonical_sensitivity_headline_range"] = None
    run_id, run_hash = getattr(run, "run_id", None), getattr(run, "run_hash", None)
    currency, valuation_date = getattr(run, "currency", None), getattr(
        run, "valuation_lens_date", None
    )
    if not all(
        isinstance(value, str) and value for value in (run_id, run_hash, currency, valuation_date)
    ):
        return
    headline = getattr(run, "valuation_range", None)
    basis = getattr(headline, "value_basis", None)
    if (
        basis in {"enterprise_value", "equity_value"}
        and getattr(headline, "currency", None) == currency
    ):
        low, mid, high = admitted_band(
            getattr(headline, "low", None),
            getattr(headline, "mid", None),
            getattr(headline, "high", None),
        )
        context["canonical_sensitivity_headline_range"] = {
            "low": str(low),
            "mid": str(mid),
            "high": str(high),
            "value_basis": basis,
            "currency": currency,
            "source_run_hash": run_hash,
        }
    context["canonical_multiple_sensitivity"] = multiple_report_sensitivity(
        run_id=str(run_id),
        run_hash=str(run_hash),
        currency=str(currency),
        valuation_date=str(valuation_date),
        metric=context.get("sensitivity_pricing_metric"),
        multiple=context.get("sensitivity_pricing_multiple"),
        enterprise_value=getattr(getattr(run, "enterprise_value_range", None), "mid", None),
        metric_type=str(context.get("multiple_metric_type") or "EBITDA"),
    )
