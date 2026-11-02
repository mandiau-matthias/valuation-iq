"""Disclose assumed market references without rewriting a saved calculation."""

from collections.abc import Mapping
from typing import cast

ReportMap = dict[str, object]

_DISCLOSURE = {
    "en": (
        "This indicative valuation uses disclosed market assumptions. The saved calculation "
        "records the pricing earnings basis, company adjustments and method contributions. "
        "The reference multiple and the effective multiple are distinct. The reference is "
        "not evidence of empirical percentiles or comparable transactions."
    ),
    "nl": (
        "Deze indicatieve waardering gebruikt vermelde marktaannames. De opgeslagen berekening "
        "bevat de geprijsde resultaatsbasis, bedrijfsaanpassingen en methodebijdragen. "
        "De referentiemultiple en de effectieve multiple zijn afzonderlijke waarden. "
        "De referentie bewijst geen empirische percentielen of vergelijkbare transacties."
    ),
    "fr": (
        "Cette valorisation indicative utilise des hypothèses de marché explicites. Le calcul "
        "enregistré détaille la base de résultat valorisée, les ajustements propres à l’entreprise "
        "et les contributions des méthodes. Le multiple de référence et le multiple effectif "
        "sont distincts. La référence ne prouve ni des percentiles empiriques ni des transactions comparables."
    ),
}


def canonical_fallback_disclosure(
    multiples: Mapping[str, object], *, language: str, business_label: str, country: str
) -> ReportMap:
    """Return presentation facts only; keep all arithmetic and risk ledgers intact.

    The legacy fallback renderer replaced the saved discount/weight schedules
    with a flat reference multiple. Missing empirical market evidence does not
    imply that the engine priced no adjustments or used only annual EBITDA.
    """
    build_up = multiples.get("multiple_build_up")
    build_up = cast(ReportMap, build_up) if isinstance(build_up, dict) else {}
    reference = multiples.get("disclosed_external_market_reference")
    reference = cast(ReportMap, reference) if isinstance(reference, dict) else {}
    message = _DISCLOSURE.get(language.lower()[:2], _DISCLOSURE["en"])
    business_id = str(multiples.get("business_type_id") or "selected-business-type")
    return {
        "canonical_fallback_disclosure": message,
        "is_disclosed_external_market_fallback": True,
        "has_industry_benchmarks": False,
        "has_benchmark_reference_multiple": False,
        "show_benchmark_reference_without_table": False,
        "benchmark_multiple_mid": None,
        "benchmark_multiple_low": None,
        "benchmark_multiple_high": None,
        "benchmark_sample_size": None,
        "benchmark_contract": None,
        "bridge_contract_resolved": False,
        "multiple_source": "DISCLOSED_EXTERNAL_MARKET_FALLBACK",
        "fallback_business_type_id": business_id,
        "fallback_business_type_label": business_label,
        "industry": business_label,
        "sector": business_label,
        "business_type_title": business_label,
        "cover_sub_line": business_label,
        # Legacy ±20% reference spreads are not post-adjustment multiple bounds.
        # External reference bounds remain separate; saved EV/equity ranges are untouched.
        "multiple_low": None,
        "multiple_high": None,
        "fallback_country_code": country,
        "fallback_market_key": f"{business_id} × {country}",
        "fallback_applied_multiple": build_up.get("effective_multiple"),
        "adaptive_multiple_used": build_up.get("effective_multiple"),
        "disclosed_external_market_reference": reference or None,
        "fallback_reference_title": reference.get("source_title"),
        "fallback_reference_summary": reference.get("evidence_summary"),
        "fallback_reference_range_low": reference.get("range_low_multiple"),
        "fallback_reference_range_high": reference.get("range_high_multiple"),
        "adaptive_methodology_justification": message,
        "methodology_statement": message,
    }
