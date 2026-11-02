"""Keep derived activity mixes out of empirical transaction-count labels."""


def apply_business_mix_report_disclosure(context: dict[str, object], locale: str) -> None:
    mix = context.get("benchmark_source_mix")
    if not isinstance(mix, dict) or mix.get("strategy") != "weighted_business_type_mix":
        return
    count = context.get("benchmark_component_min_sample_size", context.get("benchmark_sample_size"))
    labels = {
        "en": "Activity-weighted reference multiple",
        "nl": "Referentiemultiple gewogen naar activiteiten",
        "fr": "Multiple de référence pondéré par activité",
    }
    notes = {
        "en": "Derived business mix: smallest contributing cohort n={count}. Unique transaction coverage is unknown. The range is not pooled empirical percentiles or a sum-of-the-parts valuation.",
        "nl": "Afgeleide activiteitenmix: kleinste bijdragende steekproef n={count}. Het aantal unieke transacties is onbekend. De bandbreedte bevat geen gepoolde empirische percentielen en is geen som-der-delenwaardering.",
        "fr": "Mix d’activités dérivé : plus petit échantillon contributeur n={count}. Le nombre de transactions uniques est inconnu. La fourchette ne représente ni des percentiles empiriques regroupés ni une valorisation par somme des parties.",
    }
    language = locale.lower()[:2]
    label = labels.get(language, labels["en"])
    note = notes.get(language, notes["en"]).format(count=count if count is not None else "?")
    # Raw provenance remains in benchmark_contract / benchmark_provenance. These
    # aliases feed legacy templates that explicitly call sample_size transactions.
    context.update(
        benchmark_component_min_sample_size=count,
        benchmark_sample_size=None,
        benchmark_sample_size_basis="minimum_component_sample_not_unique_transactions",
        benchmark_multiple_label=label,
        benchmark_data_source=note,
        benchmark_mix_disclosure=note,
    )
    transparency = context.get("advisor_multiple_transparency")
    if isinstance(transparency, dict):
        evidence = transparency.get("benchmark_evidence")
        if isinstance(evidence, dict):
            evidence.update(
                sample_size=None,
                component_min_sample_size=count,
                basis_label=label,
                data_source=note,
            )
    existing = context.get("advisor_judgment_notes")
    notes_list = list(existing) if isinstance(existing, list) else []
    if note not in notes_list:
        notes_list.append(note)
    context["advisor_judgment_notes"] = notes_list
