"""Keep auxiliary report panels within their saved monetary/evidence premises."""

from collections.abc import Mapping
from decimal import localcontext

from src.domain.financial_arithmetic import money
from src.services.reports.report_value_admission import report_decimal


def apply_canonical_auxiliary_disclosures(context: dict[str, object]) -> None:
    run = context.get("valuation_run")
    if not isinstance(run, Mapping):
        return
    annual = context.get("multi_year_ebitda")
    if isinstance(annual, list):
        context["limited_scope_years"] = len(annual)
    if not context.get("has_nwc_normalization"):
        context["nwc_disclosure_text"] = {
            "en": "Working-capital normalization unavailable: complete compatible working-capital evidence was not supplied.",
            "nl": "Werkkapitaalnormalisatie niet beschikbaar: volledig en vergelijkbaar werkkapitaalbewijs ontbreekt.",
            "fr": "Normalisation du fonds de roulement indisponible : les preuves complètes et compatibles n’ont pas été fournies.",
        }.get(str(context.get("locale") or "nl"), "Working-capital normalization unavailable.")
    appendix = context.get("advisor_multiple_transparency")
    if isinstance(appendix, dict):
        appendix = dict(appendix)
        # These legacy projections mix pre-adjustment reference EVs and
        # multiples with final prices. They are not the saved synthesis.
        # Keep the source rows for legacy reads and audit provenance. The
        # templates withhold these tables with an explicit reason, rather
        # than erasing the underlying reference assumptions.
        appendix["unpriced_reference_tables_excluded"] = True
        # The legacy enrichment multiplies final discounted EV by factor
        # deltas. Its euro impacts have no admitted pre-adjustment base and
        # are not sealed adjustment amounts. Retain those audit rows, but
        # require the published report to withhold their monetary projection.
        # The immutable adjustment register remains the priced authority.
        appendix["unbound_discount_impacts_excluded"] = True
        context["advisor_multiple_transparency"] = appendix
    if not context.get("benchmark_provenance") and not context.get(
        "is_governed_external_market_reference"
    ):
        context["benchmark_data_source"] = None
        context["benchmark_sample_size"] = None

    # A display-generated owner-compensation add-back is not an admitted SDE
    # result. Only an available saved method with exact pricing facts may be
    # disclosed as a cross-check; never invent an owner salary or a multiple.
    context["show_sde_cross_check"] = False
    context["suppress_sde_cross_check"] = True
    context["sde_cross_check_value"] = None
    context["sde_cross_check_multiple"] = None
    context["sde_cross_check_ev"] = None
    context["sde_cross_check_source_run_id"] = None
    context["sde_cross_check_source_run_hash"] = None
    context["sde_cross_check_exclusion_reason"] = (
        "available saved method with compatible exact pricing inputs required"
    )
    if not all(
        isinstance(run.get(key), str) and run.get(key)
        for key in ("run_id", "run_hash", "currency", "valuation_lens_date")
    ):
        return
    methods = run.get("method_results")
    method = methods.get("sde_multiple") if isinstance(methods, Mapping) else None
    details = method.get("details") if isinstance(method, Mapping) else None
    if (
        not isinstance(method, Mapping)
        or method.get("available") is not True
        or not isinstance(details, Mapping)
    ):
        return
    values = (
        details.get("pricing_metric"),
        details.get("pricing_multiple"),
        method.get("enterprise_value"),
    )
    if any(value is None for value in values):
        return
    metric, multiple, enterprise = (
        report_decimal(value, "saved SDE pricing fact") for value in values
    )
    with localcontext() as arithmetic:
        arithmetic.prec = 100
        if metric <= 0 or multiple <= 0 or money(metric * multiple) != money(enterprise):
            return
    context.update(
        {
            "show_sde_cross_check": True,
            "suppress_sde_cross_check": False,
            "sde_cross_check_value": metric,
            "sde_cross_check_multiple": multiple,
            "sde_cross_check_ev": enterprise,
            "sde_cross_check_source_run_id": run.get("run_id"),
            "sde_cross_check_source_run_hash": run.get("run_hash"),
            "sde_cross_check_exclusion_reason": None,
        }
    )
