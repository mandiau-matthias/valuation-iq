"""Localize committed range provenance without recomputing any valuation."""

from collections.abc import Mapping

from .range_provenance import RangeProvenance
from .source_method_disclosures import METHOD_LABELS, exclusion_requirement

COPY = {
    "en": {
        "title": "Range basis and validation",
        "model_band": "Calculated model band",
        "benchmark_percentile_band": "Benchmark percentile band",
        "simulation_interval": "Simulation interval",
        "unverified": "Transaction-price accuracy and interval coverage are unverified: no eligible completed-deal holdout observations are available.",
        "exclusions": "Excluded methods",
    },
    "nl": {
        "title": "Basis en validatie van de bandbreedte",
        "model_band": "Berekende modelbandbreedte",
        "benchmark_percentile_band": "Percentielband van de benchmark",
        "simulation_interval": "Simulatie-interval",
        "unverified": "De nauwkeurigheid ten opzichte van transactieprijzen en de dekking van de bandbreedte zijn niet geverifieerd: er zijn geen geschikte afgeronde transacties in een onafhankelijke toetsingssteekproef.",
        "exclusions": "Uitgesloten methoden",
    },
    "fr": {
        "title": "Base et validation de la fourchette",
        "model_band": "Fourchette calculée du modèle",
        "benchmark_percentile_band": "Fourchette des percentiles du benchmark",
        "simulation_interval": "Intervalle de simulation",
        "unverified": "La précision par rapport aux prix de transaction et la couverture de la fourchette ne sont pas vérifiées : aucune transaction réalisée admissible n’est disponible dans un échantillon de validation indépendant.",
        "exclusions": "Méthodes exclues",
    },
}


def project_range_provenance(run: object, locale: str) -> dict[str, object] | None:
    lineage = (
        run.get("calculation_lineage")
        if isinstance(run, Mapping)
        else getattr(run, "calculation_lineage", None)
    )
    raw = lineage.get("range_provenance") if isinstance(lineage, Mapping) else None
    if raw is None:
        return None  # Historical reports keep their original contract.
    provenance = RangeProvenance.model_validate(raw)
    copy = COPY.get(locale[:2].lower(), COPY["en"])
    return {
        "contract": provenance.model_dump(mode="json"),
        "title": copy["title"],
        "kind_label": copy[provenance.kind],
        "calibration_disclosure": copy["unverified"],
        "exclusions_label": copy["exclusions"],
        "excluded_methods": {
            method: exclusion_requirement(method, reason, locale)
            for method, reason in provenance.excluded_methods.items()
        },
        "excluded_method_labels": METHOD_LABELS.get(locale[:2].lower(), METHOD_LABELS["en"]),
    }
