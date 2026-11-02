"""Bind method-page scenarios to immutable method pricing inputs."""

from collections.abc import Mapping

from src.services.reports.multiple_sensitivity import compute_multiple_sensitivity_matrix_2d

_METHODS = (
    ("ebitda_multiple", "ebitda_sensitivity_matrix_2d"),
    ("sde_multiple", "sde_sensitivity_matrix_2d"),
    ("omzet_multiple", "revenue_sensitivity_matrix_2d"),
)


def apply_saved_method_sensitivities(context: dict[str, object]) -> None:
    """Old runs lacking exact pricing inputs remain readable without new grids.

    No annual financial observation or displayed headline is substituted for a
    method's priced metric. The illustrative ±15% / ±20% scenario is separate
    from the method's saved range and market-evidence distributions.
    """
    for _, slot in _METHODS:
        context[slot] = None
    run = context.get("valuation_run")
    if not isinstance(run, Mapping):
        return
    run_id, run_hash = run.get("run_id"), run.get("run_hash")
    currency, date = run.get("currency"), run.get("valuation_lens_date")
    if not all(isinstance(v, str) and v for v in (run_id, run_hash, currency, date)):
        return
    methods = run.get("method_results")
    if not isinstance(methods, Mapping):
        return
    for key, slot in _METHODS:
        method = methods.get(key)
        if method is None and key == "omzet_multiple":
            method = methods.get("revenue_multiple")
        if not isinstance(method, Mapping) or method.get("available") is not True:
            continue
        details = method.get("details")
        if not isinstance(details, Mapping):
            continue
        # New producers persist these unrounded facts. Do not back-solve them
        # from EV, a rounded multiple or a different year's financial lines.
        metric, multiple = details.get("pricing_metric"), details.get("pricing_multiple")
        saved_ev = method.get("enterprise_value")
        if metric is None or multiple is None or saved_ev is None:
            continue
        context[slot] = compute_multiple_sensitivity_matrix_2d(
            metric_base=metric,
            multiple_base=multiple,
            saved_enterprise_value=saved_ev,
            source_run_id=str(run_id),
            source_run_hash=str(run_hash),
            method_key=key,
            currency=str(currency),
            valuation_date=str(date),
        )
