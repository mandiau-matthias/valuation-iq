"""Recovery report presentation from committed recovery outcomes."""

from __future__ import annotations

from src.api.schemas.stateless_report_schemas import GenerateReportRequest

from .report_context_types import ReportMap


def _apply_negative_ebitda_recovery_context(
    context: ReportMap,
    request: GenerateReportRequest,
    *,
    locale: str,
) -> None:
    resolution_model = request.valuation_result.negative_ebitda_resolution
    if resolution_model is None:
        context["has_negative_ebitda_recovery"] = False
        return

    resolution = resolution_model.model_dump(mode="python")
    language = (locale or "nl").lower().split("-")[0]
    copy = {
        "nl": {
            "title": "Herstelwaardering bij negatieve EBITDA",
            "subtitle": "Een voorwaardelijke beoordeling van herstelpad, financiering en bewijs.",
            "no_range": "Nog geen verdedigbare waarderingsrange vastgesteld",
            "conclusion": "Conclusie",
            "position": "Huidige positie en oorzaken",
            "causes": "Oorzaak- en risicosignalen",
            "normalization_bridge": "Normalisatiebrug",
            "accepted_adjustments": "Aanvaarde aanpassingen",
            "break_even_bridge": "Break-evenbrug (basisscenario)",
            "scenarios": "Herstelscenario’s",
            "funding": "Financiering en aandeelhoudersbrug",
            "evidence": "Vereist bewijs",
            "limitations": "Beperkingen",
            "actions": "Waardeopbouwende acties",
            "reported_ebitda": "Gerapporteerde EBITDA",
            "normalized_ebitda": "Genormaliseerde EBITDA",
            "operating_trajectory": "Operationele richting",
            "scenario": "Scenario",
            "probability": "Waarschijnlijkheid",
            "break_even": "Break-even",
            "funding_need": "Financieringsbehoefte",
            "equity_midpoint": "Middenwaarde eigen vermogen",
            "enterprise_midpoint": "Middenwaarde onderneming",
            "revenue_at_break_even": "Omzet bij break-even",
            "ebitda_at_break_even": "EBITDA bij break-even",
            "fcff_at_break_even": "FCFF bij break-even",
            "current_cash": "Huidige cash",
            "minimum_cash": "Minimale operationele cash",
            "excess_cash": "Overtollige cash",
            "current_debt": "Huidige schuld",
            "shareholder_basis": "Basis aandeelhouderswaarde",
            "terminal_value_share": "Aandeel eindwaarde",
            "cross_checks": "Kruiscontroles",
            "no_cross_check": "Geen verdedigbare kruiscontrole aanvaard.",
            "confidence": "betrouwbaarheid",
            "limitations_copy": "Scenariokansen omvatten het overlevingsrisico al; er wordt geen extra overlevingskorting toegepast. De financieringsbehoefte wordt afzonderlijk getoond en niet nogmaals van de ondernemingswaarde afgetrokken.",
        },
        "en": {
            "title": "Negative-EBITDA recovery valuation",
            "subtitle": "A conditional assessment of the recovery path, funding and evidence.",
            "no_range": "No defensible range established yet",
            "conclusion": "Conclusion",
            "position": "Current position and causes",
            "causes": "Cause and risk signals",
            "normalization_bridge": "Normalization bridge",
            "accepted_adjustments": "Accepted adjustments",
            "break_even_bridge": "Break-even bridge (base scenario)",
            "scenarios": "Recovery scenarios",
            "funding": "Funding and shareholder bridge",
            "evidence": "Required evidence",
            "limitations": "Limitations",
            "actions": "Value-building actions",
            "reported_ebitda": "Reported EBITDA",
            "normalized_ebitda": "Normalized EBITDA",
            "operating_trajectory": "Operating trajectory",
            "scenario": "Scenario",
            "probability": "Probability",
            "break_even": "Break-even",
            "funding_need": "Funding need",
            "equity_midpoint": "Equity midpoint",
            "enterprise_midpoint": "Enterprise midpoint",
            "revenue_at_break_even": "Revenue at break-even",
            "ebitda_at_break_even": "EBITDA at break-even",
            "fcff_at_break_even": "FCFF at break-even",
            "current_cash": "Current cash",
            "minimum_cash": "Minimum operating cash",
            "excess_cash": "Excess cash",
            "current_debt": "Current debt",
            "shareholder_basis": "Shareholder-value basis",
            "terminal_value_share": "Terminal-value share",
            "cross_checks": "Cross-checks",
            "no_cross_check": "No defensible cross-check accepted.",
            "confidence": "confidence",
            "limitations_copy": "Scenario probabilities already incorporate survival risk; no additional survival haircut is applied. Funding need is disclosed separately and is not deducted a second time from enterprise value.",
        },
        "fr": {
            "title": "Valorisation de redressement avec EBITDA négatif",
            "subtitle": "Une évaluation conditionnelle de la trajectoire, du financement et des preuves.",
            "no_range": "Aucune fourchette défendable établie à ce stade",
            "conclusion": "Conclusion",
            "position": "Situation actuelle et causes",
            "causes": "Signaux de cause et de risque",
            "normalization_bridge": "Pont de normalisation",
            "accepted_adjustments": "Ajustements acceptés",
            "break_even_bridge": "Pont vers le seuil de rentabilité (scénario de base)",
            "scenarios": "Scénarios de redressement",
            "funding": "Financement et pont actionnarial",
            "evidence": "Preuves requises",
            "limitations": "Limites",
            "actions": "Actions de création de valeur",
            "reported_ebitda": "EBITDA déclaré",
            "normalized_ebitda": "EBITDA normalisé",
            "operating_trajectory": "Trajectoire opérationnelle",
            "scenario": "Scénario",
            "probability": "Probabilité",
            "break_even": "Seuil de rentabilité",
            "funding_need": "Besoin de financement",
            "equity_midpoint": "Valeur médiane des fonds propres",
            "enterprise_midpoint": "Valeur médiane de l’entreprise",
            "revenue_at_break_even": "Chiffre d’affaires au seuil",
            "ebitda_at_break_even": "EBITDA au seuil",
            "fcff_at_break_even": "FCFF au seuil",
            "current_cash": "Trésorerie actuelle",
            "minimum_cash": "Trésorerie opérationnelle minimale",
            "excess_cash": "Trésorerie excédentaire",
            "current_debt": "Dette actuelle",
            "shareholder_basis": "Base de valeur actionnariale",
            "terminal_value_share": "Part de la valeur terminale",
            "cross_checks": "Recoupements",
            "no_cross_check": "Aucun recoupement défendable accepté.",
            "confidence": "fiabilité",
            "limitations_copy": "Les probabilités des scénarios intègrent déjà le risque de survie ; aucune décote de survie supplémentaire n’est appliquée. Le besoin de financement est présenté séparément et n’est pas déduit une seconde fois de la valeur d’entreprise.",
        },
    }.get(language, {})
    no_range = resolution.get("primary_method") is None
    reported_ebitda = resolution_model.reported_ebitda
    normalized_ebitda = resolution_model.normalized_ebitda
    normalization_bridge = resolution.get("normalization_bridge") or {
        "reported_ebitda": resolution.get("reported_ebitda"),
        "accepted_adjustments": (
            normalized_ebitda - reported_ebitda
            if normalized_ebitda is not None and reported_ebitda is not None
            else None
        ),
        "normalized_ebitda": resolution.get("normalized_ebitda"),
    }
    context.update(
        {
            "has_negative_ebitda_recovery": True,
            "negative_ebitda_resolution": resolution,
            "negative_ebitda_recovery_copy": copy,
            "negative_ebitda_no_range": no_range,
            "negative_ebitda_conclusion": (
                copy.get("no_range")
                if no_range
                else str(resolution.get("primary_method") or "")
                .replace("_", " ")
                .title()
                .replace("Dcf", "DCF")
                .replace("Nav", "NAV")
                .replace("Arr", "ARR")
            ),
            "negative_ebitda_scenarios": resolution.get("scenario_results") or [],
            "negative_ebitda_trajectory": resolution.get("operating_trajectory") or {},
            "negative_ebitda_required_evidence": resolution.get("required_evidence") or [],
            "negative_ebitda_blockers": resolution.get("blockers") or [],
            "negative_ebitda_actions": resolution.get("value_building_actions") or [],
            "negative_ebitda_causes": resolution.get("cause_codes") or [],
            # Older persisted recovery snapshots predate the explicit bridge.
            # Reconstruct it from canonical reported/normalized fields so
            # report regeneration remains useful and never formats Undefined.
            "negative_ebitda_normalization_bridge": normalization_bridge,
            "negative_ebitda_break_even_bridge": resolution.get("break_even_bridge") or {},
            "negative_ebitda_equity_bridge": resolution.get("equity_bridge") or {},
        }
    )
    if no_range:
        # The assessment is complete but not numeric. Keep every report surface
        # on the same null conclusion; do not let legacy formatting turn it into €0.
        context.update(
            {
                "valuation": None,
                "valuation_low": None,
                "valuation_high": None,
                "equity_value": None,
                "equity_value_low": None,
                "equity_value_mid": None,
                "equity_value_high": None,
                "enterprise_value": None,
                "enterprise_value_low": None,
                "enterprise_value_mid": None,
                "enterprise_value_high": None,
                "recommended_asking_price": None,
                "headline_value_basis": None,
                "primary_method_label": copy.get("no_range"),
                "show_ev_equity_bridge": False,
                "show_enterprise_to_equity_bridge": False,
                "valuation_band_is_meaningful": False,
                "equity_value_band_is_meaningful": False,
                "has_upswitch_adaptive_page": False,
                "has_dcf": False,
                "show_dcf_before_calibration": False,
                "has_ebitda_multiple_page": False,
                "has_sde_page": False,
                "has_revenue_multiple_page": False,
                "has_weighted_synthesis": False,
                "show_advisor_multiple_transparency_appendix": False,
                "show_multiple_evidence_appendix": False,
                "show_discount_methodology_appendix": False,
            }
        )
    else:
        # The immutable recovery resolution is the sole report authority. A
        # regenerated report must not inherit an older top-level band or render
        # a parallel legacy method chapter whose numbers are not bound by the
        # recovery resolution hash.
        equity_low = resolution.get("headline_equity_value_low")
        equity_mid = resolution.get("headline_equity_value_mid")
        equity_high = resolution.get("headline_equity_value_high")
        enterprise_low = resolution.get("headline_enterprise_value_low")
        enterprise_mid = resolution.get("headline_enterprise_value_mid")
        enterprise_high = resolution.get("headline_enterprise_value_high")
        headline_low = equity_low if equity_low is not None else enterprise_low
        headline_mid = equity_mid if equity_mid is not None else enterprise_mid
        headline_high = equity_high if equity_high is not None else enterprise_high
        has_equity_bridge = equity_mid is not None and enterprise_mid is not None
        context.update(
            {
                "valuation": headline_mid,
                "valuation_low": headline_low,
                "valuation_high": headline_high,
                "equity_value": equity_mid,
                "equity_value_low": equity_low,
                "equity_value_mid": equity_mid,
                "equity_value_high": equity_high,
                "enterprise_value": enterprise_mid,
                "enterprise_value_low": enterprise_low,
                "enterprise_value_mid": enterprise_mid,
                "enterprise_value_high": enterprise_high,
                "recommended_asking_price": None,
                "headline_value_basis": (
                    "equity_value" if equity_mid is not None else "enterprise_value"
                ),
                "primary_method_label": context["negative_ebitda_conclusion"],
                "show_ev_equity_bridge": has_equity_bridge,
                "show_enterprise_to_equity_bridge": has_equity_bridge,
                "valuation_band_is_meaningful": headline_mid is not None,
                "equity_value_band_is_meaningful": equity_mid is not None,
                "has_upswitch_adaptive_page": False,
                "has_dcf": False,
                "show_dcf_before_calibration": False,
                "has_ebitda_multiple_page": False,
                "has_sde_page": False,
                "has_revenue_multiple_page": False,
                "has_weighted_synthesis": False,
                "show_advisor_multiple_transparency_appendix": False,
                "show_multiple_evidence_appendix": False,
                "show_discount_methodology_appendix": False,
            }
        )
