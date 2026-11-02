"""Report context for business growth maturity stages."""

from __future__ import annotations

from decimal import Decimal

from src.domain.business_growth_maturity import build_business_growth_maturity_context
from src.services.reports.protocol_adapter import _attr
from src.services.reports.report_company_metrics_context import get_employee_count, get_revenue

JsonMap = dict[str, object]

_STAGE_DISPLAY_LABELS: dict[str, dict[str, str]] = {
    "en": {
        "garage": "Micro",
        "family": "Owner-led",
        "village": "Emerging team",
        "town": "Structured SME",
        "city": "Scaled SME",
        "metropolis": "Enterprise-scale",
    },
    "nl": {
        "garage": "Microfase",
        "family": "Eigenaarszaak",
        "village": "Beginnend team",
        "town": "Gestructureerde kmo",
        "city": "Geschaalde kmo",
        "metropolis": "Enterprise-schaal",
    },
    "fr": {
        "garage": "Micro",
        "family": "Petite structure",
        "village": "Equipe emergente",
        "town": "PME structuree",
        "city": "PME a l'echelle",
        "metropolis": "Grande echelle",
    },
}

_REVENUE_BAND_LABELS: dict[str, dict[str, str]] = {
    "en": {
        "garage": "Below EUR 100K revenue",
        "family": "EUR 100K to 500K revenue",
        "village": "EUR 500K to 1M revenue",
        "town": "EUR 1M to 2M revenue",
        "city": "EUR 2M to 5M revenue",
        "metropolis": "EUR 5M+ revenue",
    },
    "nl": {
        "garage": "Minder dan EUR 100K omzet",
        "family": "EUR 100K tot 500K omzet",
        "village": "EUR 500K tot 1M omzet",
        "town": "EUR 1M tot 2M omzet",
        "city": "EUR 2M tot 5M omzet",
        "metropolis": "Meer dan EUR 5M omzet",
    },
    "fr": {
        "garage": "Moins de EUR 100K de chiffre d'affaires",
        "family": "EUR 100K a 500K de chiffre d'affaires",
        "village": "EUR 500K a 1M de chiffre d'affaires",
        "town": "EUR 1M a 2M de chiffre d'affaires",
        "city": "EUR 2M a 5M de chiffre d'affaires",
        "metropolis": "Plus de EUR 5M de chiffre d'affaires",
    },
}

_TEAM_BAND_LABELS: dict[str, dict[str, str]] = {
    "en": {
        "garage": "0 to 1 FTE",
        "family": "2 to 5 FTE",
        "village": "6 to 15 FTE",
        "town": "16 to 50 FTE",
        "city": "51 to 200 FTE",
        "metropolis": "201+ FTE",
    },
    "nl": {
        "garage": "0 tot 1 FTE",
        "family": "2 tot 5 FTE",
        "village": "6 tot 15 FTE",
        "town": "16 tot 50 FTE",
        "city": "51 tot 200 FTE",
        "metropolis": "201+ FTE",
    },
    "fr": {
        "garage": "0 a 1 ETP",
        "family": "2 a 5 ETP",
        "village": "6 a 15 ETP",
        "town": "16 a 50 ETP",
        "city": "51 a 200 ETP",
        "metropolis": "201+ ETP",
    },
}

_ROLE_LABELS: dict[str, dict[str, str]] = {
    "en": {
        "current": "Current",
        "next": "Next",
        "revenue": "Revenue",
        "team": "Team",
    },
    "nl": {
        "current": "Huidig",
        "next": "Volgende",
        "revenue": "Omzet",
        "team": "Team",
    },
    "fr": {
        "current": "Actuel",
        "next": "Suivant",
        "revenue": "CA",
        "team": "Equipe",
    },
}

_ALIGNMENT_LABELS: dict[str, dict[str, str]] = {
    "en": {
        "balanced": "Revenue and team capacity are aligned",
        "revenue_ahead_of_team": "Revenue is ahead of team capacity",
        "team_ahead_of_revenue": "Team capacity is ahead of revenue",
        "partial_data": "Partial maturity data",
    },
    "nl": {
        "balanced": "Omzet en teamcapaciteit zijn in balans",
        "revenue_ahead_of_team": "Omzet loopt voor op teamcapaciteit",
        "team_ahead_of_revenue": "Teamcapaciteit loopt voor op omzet",
        "partial_data": "Onvolledige maturiteitsdata",
    },
    "fr": {
        "balanced": "Chiffre d'affaires et equipe sont alignes",
        "revenue_ahead_of_team": "Le chiffre d'affaires devance la capacite de l'equipe",
        "team_ahead_of_revenue": "La capacite de l'equipe devance le chiffre d'affaires",
        "partial_data": "Donnees de maturite partielles",
    },
}

_ALIGNMENT_SUMMARIES: dict[str, dict[str, str]] = {
    "en": {
        "balanced": (
            "Revenue scale and team capacity point to the same operating stage; "
            "focus on proving the next-stage routines."
        ),
        "revenue_ahead_of_team": (
            "The revenue base fits a larger operating model than the current team. "
            "Strengthen delegation, hiring capacity, and cadence before adding complexity."
        ),
        "team_ahead_of_revenue": (
            "The team footprint is ahead of the current revenue base. Tighten pipeline "
            "conversion, utilization, and margin recovery before adding headcount."
        ),
        "partial_data": "Confirm both revenue and team size before treating this roadmap as complete.",
    },
    "nl": {
        "balanced": (
            "Omzetniveau en teamcapaciteit wijzen naar dezelfde operationele fase. "
            "Focus nu op routines die de volgende fase bewijsbaar maken."
        ),
        "revenue_ahead_of_team": (
            "De omzetbasis past bij een groter operationeel model dan het huidige team. "
            "Versterk delegatie, aanwervingscapaciteit en ritme voordat extra complexiteit wordt toegevoegd."
        ),
        "team_ahead_of_revenue": (
            "De teamstructuur is zwaarder dan de huidige omzetbasis. Versterk pipelineconversie, "
            "bezetting en margeherstel voordat extra capaciteit wordt toegevoegd."
        ),
        "partial_data": "Bevestig zowel omzet als teamgrootte voordat u deze roadmap als volledig behandelt.",
    },
    "fr": {
        "balanced": (
            "Le niveau de chiffre d'affaires et la capacite d'equipe pointent vers le meme stade. "
            "Concentrez-vous sur les routines du stade suivant."
        ),
        "revenue_ahead_of_team": (
            "La base de chiffre d'affaires correspond a un modele operationnel plus grand que l'equipe actuelle. "
            "Renforcez delegation, recrutement et cadence avant d'ajouter de la complexite."
        ),
        "team_ahead_of_revenue": (
            "La structure d'equipe est en avance sur la base de chiffre d'affaires. "
            "Renforcez conversion, utilisation et marge avant d'ajouter de la capacite."
        ),
        "partial_data": "Confirmez chiffre d'affaires et taille d'equipe avant de finaliser cette feuille de route.",
    },
}


def _json_ready(value: object) -> object:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, list):
        return [_json_ready(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    return value


def _locale_key(locale: str) -> str:
    raw = str(locale or "en").strip().lower()
    if raw.startswith("nl"):
        return "nl"
    if raw.startswith("fr"):
        return "fr"
    return "en"


def _localized_stage_label(stage: object, *, locale: str = "en") -> str | None:
    if not stage:
        return None
    key = str(stage)
    return _STAGE_DISPLAY_LABELS[_locale_key(locale)].get(key, key.replace("_", " ").title())


def _localized_band_label(
    stage: object,
    *,
    labels: dict[str, dict[str, str]],
    locale: str,
    fallback: object,
) -> str | None:
    if not stage:
        return str(fallback) if fallback else None
    return labels[_locale_key(locale)].get(str(stage), str(fallback) if fallback else None)


def _decorate_stage_ladder(maturity: JsonMap, *, locale: str) -> None:
    role_labels = _ROLE_LABELS[_locale_key(locale)]
    decorated: list[JsonMap] = []
    for raw_stage in maturity.get("stage_ladder") or []:
        if not isinstance(raw_stage, dict):
            continue
        stage = dict(raw_stage)
        roles: list[str] = []
        if stage.get("is_effective_stage"):
            roles.append(role_labels["current"])
        if stage.get("is_next_stage"):
            roles.append(role_labels["next"])
        if stage.get("is_revenue_stage"):
            roles.append(role_labels["revenue"])
        if stage.get("is_team_stage"):
            roles.append(role_labels["team"])
        stage["display_label"] = _localized_stage_label(stage.get("stage"), locale=locale)
        stage["role_labels"] = roles
        decorated.append(stage)
    maturity["stage_ladder"] = decorated


def _guidance_cards(maturity: JsonMap, *, locale: str) -> list[JsonMap]:
    loc = _locale_key(locale)
    next_stage = _localized_stage_label(maturity.get("next_stage"), locale=locale) or ""
    alignment = str(maturity.get("alignment") or "partial_data")

    if loc == "nl":
        alignment_cards = {
            "revenue_ahead_of_team": {
                "title": "Capaciteit voor complexiteit",
                "body": "Leg eigenaarschap, planning en backup-capaciteit vast voordat de omzetgroei extra complexiteit toevoegt.",
            },
            "team_ahead_of_revenue": {
                "title": "Commerciele focus aanscherpen",
                "body": "Richt rollen op pipelineconversie, bezetting en margeherstel voordat extra teamcapaciteit wordt toegevoegd.",
            },
            "balanced": {
                "title": "Volgende routines bewijzen",
                "body": "Maak de routines van de volgende fase aantoonbaar in sales, uitvoering en maandelijkse opvolging.",
            },
            "partial_data": {
                "title": "Databasis vervolledigen",
                "body": "Bevestig omzet en FTE voordat deze maturiteitsroadmap als beslissingsbasis wordt gebruikt.",
            },
        }
        next_body = (
            f"Bouw overdraagbare routines die {next_stage}-capaciteit aantonen."
            if next_stage
            else "Behoud discipline in rollen, rapportering en overdraagbare routines."
        )
        return [
            alignment_cards.get(alignment, alignment_cards["partial_data"]),
            {"title": "Volgende stap", "body": next_body},
            {
                "title": "Bewijs in het dossier",
                "body": "Documenteer verantwoordelijkheden, maandelijkse KPI's en afhankelijkheden die een koper kan controleren.",
            },
        ]

    if loc == "fr":
        alignment_cards = {
            "revenue_ahead_of_team": {
                "title": "Capacite avant complexite",
                "body": "Clarifiez responsabilites, planning et capacite de relais avant d'ajouter de la complexite.",
            },
            "team_ahead_of_revenue": {
                "title": "Resserrer le moteur commercial",
                "body": "Orientez les roles vers conversion, utilisation et marge avant d'ajouter de la capacite.",
            },
            "balanced": {
                "title": "Prouver les routines suivantes",
                "body": "Rendez les routines du prochain stade mesurables en vente, execution et suivi mensuel.",
            },
            "partial_data": {
                "title": "Completer la base de donnees",
                "body": "Confirmez chiffre d'affaires et ETP avant d'utiliser cette feuille de route comme base de decision.",
            },
        }
        next_body = (
            f"Construisez les routines transferables qui prouvent la capacite {next_stage}."
            if next_stage
            else "Maintenez la discipline sur les roles, le reporting et les routines transferables."
        )
        return [
            alignment_cards.get(alignment, alignment_cards["partial_data"]),
            {"title": "Prochaine etape", "body": next_body},
            {
                "title": "Preuves au dossier",
                "body": "Documentez responsabilites, KPI mensuels et dependances verifiables par un acheteur.",
            },
        ]

    alignment_cards = {
        "revenue_ahead_of_team": {
            "title": "Capacity before complexity",
            "body": "Lock ownership, planning, and backup capacity before revenue growth adds more operating complexity.",
        },
        "team_ahead_of_revenue": {
            "title": "Tighten commercial focus",
            "body": "Aim roles at pipeline conversion, utilization, and margin recovery before adding more capacity.",
        },
        "balanced": {
            "title": "Prove the next routines",
            "body": "Make the next-stage routines measurable across sales, delivery, and monthly management cadence.",
        },
        "partial_data": {
            "title": "Complete the evidence base",
            "body": "Confirm revenue and FTE before using this maturity roadmap as a decision basis.",
        },
    }
    next_body = (
        f"Build transferable routines that prove {next_stage} capacity."
        if next_stage
        else "Keep discipline around roles, reporting, and transferable routines."
    )
    return [
        alignment_cards.get(alignment, alignment_cards["partial_data"]),
        {"title": "Next step", "body": next_body},
        {
            "title": "Evidence for the file",
            "body": "Document responsibilities, monthly KPIs, and dependencies a buyer can verify.",
        },
    ]


def _localize_maturity_context(maturity: JsonMap, *, locale: str) -> JsonMap:
    localized = dict(maturity)
    loc = _locale_key(locale)
    alignment = str(localized.get("alignment") or "partial_data")

    localized["revenue_stage_label"] = _localized_stage_label(
        localized.get("revenue_stage"), locale=locale
    )
    localized["team_stage_label"] = _localized_stage_label(
        localized.get("team_stage"), locale=locale
    )
    localized["effective_stage_label"] = _localized_stage_label(
        localized.get("effective_stage"), locale=locale
    )
    localized["next_stage_label"] = _localized_stage_label(
        localized.get("next_stage"), locale=locale
    )
    localized["revenue_band_label"] = _localized_band_label(
        localized.get("revenue_stage"),
        labels=_REVENUE_BAND_LABELS,
        locale=locale,
        fallback=localized.get("revenue_band_label"),
    )
    localized["team_band_label"] = _localized_band_label(
        localized.get("team_stage"),
        labels=_TEAM_BAND_LABELS,
        locale=locale,
        fallback=localized.get("team_band_label"),
    )
    localized["alignment_label"] = _ALIGNMENT_LABELS[loc].get(
        alignment, _ALIGNMENT_LABELS[loc]["partial_data"]
    )
    localized["alignment_summary"] = _ALIGNMENT_SUMMARIES[loc].get(
        alignment, _ALIGNMENT_SUMMARIES[loc]["partial_data"]
    )
    _decorate_stage_ladder(localized, locale=locale)
    localized["guidance_cards"] = _guidance_cards(localized, locale=locale)
    return localized


def _has_revenue_input(response: object, request: object | None) -> bool:
    response_current_year = _attr(response, "current_year_data", None)
    request_current_year = _attr(request, "current_year_data", None)
    return any(
        raw is not None and raw != ""
        for raw in (
            _attr(response_current_year, "revenue", None),
            _attr(request_current_year, "revenue", None),
        )
    )


def build_business_growth_maturity_report_context(
    response: object,
    request: object | None,
    locale: str = "en",
) -> JsonMap:
    """Build the growth maturity section context."""
    revenue = get_revenue(response, request) if _has_revenue_input(response, request) else None
    maturity = build_business_growth_maturity_context(
        revenue=revenue,
        team_size=get_employee_count(response, request),
    )
    if not maturity.get("effective_stage"):
        return {
            "show_business_growth_maturity_section": False,
            "business_growth_maturity": None,
        }
    localized_maturity = _localize_maturity_context(maturity, locale=locale)
    return {
        "show_business_growth_maturity_section": True,
        "business_growth_maturity": _json_ready(localized_maturity),
    }
