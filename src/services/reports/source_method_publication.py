"""Ensure report diagnostics cannot resurrect methods excluded by the sealed run."""

from collections.abc import Mapping
from decimal import Decimal


def apply_sealed_earnings_display(context: dict[str, object], run: object) -> None:
    lineage = getattr(run, "calculation_lineage", None)
    eligibility = lineage.get("method_eligibility") if isinstance(lineage, Mapping) else None
    if (
        not isinstance(eligibility, Mapping)
        or eligibility.get("policy_version") != "source-evidence-required.v1"
    ):
        return
    if context.get("multiple_metric_type") != "EBITDA":
        return
    multiples = getattr(run, "multiples_results", None)
    build_up = multiples.get("multiple_build_up") if isinstance(multiples, Mapping) else None
    basis = build_up.get("earnings_basis") if isinstance(build_up, Mapping) else None
    if not isinstance(basis, Mapping):
        return
    amount = basis.get("adjusted_earnings")
    if amount is None:
        return
    exact = Decimal(str(amount))
    if not exact.is_finite():
        raise ValueError("sealed report earnings basis must be finite")
    context["sustainable_ebitda"] = exact
    context["valuation_basis_value"] = exact
    context["formula_uses_sealed_earnings"] = True
    context["bridge_applied_multiple"] = context.get("applied_multiple")


def apply_source_method_publication(
    context: dict[str, object], run: object, *, locale: str = "nl"
) -> None:
    lineage = getattr(run, "calculation_lineage", None)
    eligibility = lineage.get("method_eligibility") if isinstance(lineage, Mapping) else None
    if (
        not isinstance(eligibility, Mapping)
        or eligibility.get("policy_version") != "source-evidence-required.v1"
    ):
        return
    methods = eligibility.get("methods", {})
    context["source_policy_report"] = True
    copy = {
        "en": (
            "observations",
            "Financial source evidence • benchmark reference",
            "Calculation uses the sealed earnings basis. Displayed amounts and multiples are rounded.",
            "Equity value is unavailable until cash, debt, leases, working capital and completion accounts are evidenced and reconciled.",
            "Valuation earnings basis",
        ),
        "nl": (
            "waarnemingen",
            "Financieel bronbewijs • benchmarkreferentie",
            "De berekening gebruikt de verzegelde winstbasis. Getoonde bedragen en multiples zijn afgerond.",
            "De aandelenwaarde is niet beschikbaar totdat cash, schuld, leases, werkkapitaal en completion accounts met bronbewijs zijn gereconcilieerd.",
            "Winstbasis waardering",
        ),
        "fr": (
            "observations",
            "Preuves financières sources • référence du benchmark",
            "Le calcul utilise la base de résultat scellée. Les montants et multiples affichés sont arrondis.",
            "La valeur des capitaux propres est indisponible jusqu’à justification et rapprochement de la trésorerie, de la dette, des contrats de location, du fonds de roulement et des comptes de clôture.",
            "Base de résultat retenue",
        ),
    }[locale.lower()[:2] if locale.lower()[:2] in {"en", "nl", "fr"} else "nl"]
    for key, value in zip(
        (
            "source_policy_observations_label",
            "source_policy_data_inputs_caption",
            "source_policy_earnings_caption",
            "source_policy_equity_deficiency",
            "source_policy_earnings_label",
        ),
        copy,
    ):
        context[key] = value
    context["equity_value_unavailable"] = (
        eligibility.get("equity_status") == "unavailable_incomplete_bridge"
    )
    sde = methods.get("sde_multiple", {}) if isinstance(methods, Mapping) else {}
    if not isinstance(sde, Mapping) or sde.get("eligible") is not True:
        context.update(
            {
                "show_sde_cross_check": False,
                "suppress_sde_cross_check": True,
                "has_sde_page": False,
                "sde_cross_check_value": None,
                "sde_cross_check_multiple": None,
                "sde_cross_check_ev": None,
            }
        )
    dcf = methods.get("dcf", {}) if isinstance(methods, Mapping) else {}
    if not isinstance(dcf, Mapping) or dcf.get("eligible") is not True:
        context["show_dcf_crosscheck"] = False
    # The legacy sensitivity component calculates scenarios in Jinja from
    # unsealed percentile aliases. Suppress it for this policy until a sealed
    # scenario matrix is supplied by the calculation producer.
    context["suppress_unsealed_sensitivity"] = True
