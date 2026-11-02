"""Localized benchmark source labels for report contexts."""

from __future__ import annotations

from typing import Optional

from src.services.reports.report_benchmark_context import _ENGINE_SECTOR_ANCHOR_SOURCE

# Raw internal keys that are never meaningful to a report reader.
_OPAQUE_INTERNAL_SOURCES = frozenset(
    {"titan_enrichment", "hardcoded_default", "cache_hit", "synced_db"}
)


def _localized_upswitch_index_label(locale: str) -> str:
    loc = str(locale or "nl").lower()
    if loc.startswith("fr"):
        return "Contrat de reference Upswitch Index"
    return "Upswitch Index benchmark contract"


def _is_internal_delphi_source(data_source: object) -> bool:
    value = str(data_source or "").strip().lower()
    return "delphi" in value


def localized_benchmark_data_source_label(data_source: object, locale: str) -> object:
    """Localize the engine sector-anchor provenance token for display."""
    if _is_internal_delphi_source(data_source):
        return _localized_upswitch_index_label(locale)
    if data_source != _ENGINE_SECTOR_ANCHOR_SOURCE:
        return data_source
    loc = str(locale or "nl").lower()
    if loc.startswith("fr"):
        return "Benchmark sectoriel Upswitch (ancre base de données)"
    if loc.startswith("en"):
        return data_source
    return "Upswitch sectorbenchmark (database-anker)"


def is_country_baseline_contract(benchmark_contract: object) -> bool:
    """True when the contract is a Damodaran/country-average fallback, not real sector data.

    Detection is deliberately broad because the country-baseline marker lands
    in different fields depending on the resolution path:
    - ``source`` / ``benchmark_kind`` / ``benchmark_scope`` carry the literal
      ``country_baseline`` token on the engine fast-path; and
    - ``evidence_summary.fallback_reason`` is populated whenever the index walked
      to a country-level fallback (this is what the appendix already keys on);
    - the free-text ``multiples_source`` opens with "Country baseline fallback".
    Any one of these is sufficient.
    """
    if not benchmark_contract or not isinstance(benchmark_contract, dict):
        return False
    for field in ("source", "benchmark_kind", "benchmark_scope"):
        value = str(benchmark_contract.get(field) or "").strip().lower()
        if "country_baseline" in value:
            return True
    multiples_source = str(benchmark_contract.get("multiples_source") or "").strip().lower()
    if multiples_source.startswith("country baseline"):
        return True
    evidence_summary = benchmark_contract.get("evidence_summary")
    if isinstance(evidence_summary, dict) and evidence_summary.get("fallback_reason"):
        return True
    return False


# Minimum comparables a benchmark must rest on to defensibly support a
# false-precision POINT headline. At or below this, surfaces lead with the
# low–high range instead. Mirrors the ``thin_benchmark`` (n≤3) signal used in
# report_audience_context so the floor and the limited-scope panel agree.
MIN_COMPARABLES_FOR_POINT_HEADLINE = 3


def should_force_range_for_thin_benchmark(
    *,
    sample_size: object,
    benchmark_contract: Optional[dict],
) -> bool:
    """True when the benchmark is too thin to headline a point estimate.

    Thin means EITHER ≤ ``MIN_COMPARABLES_FOR_POINT_HEADLINE`` real comparables
    OR a Damodaran country-baseline proxy (inherently n≈1). A ``sample_size`` of
    0/None/unparseable is treated as "unknown, not thin" — the country-baseline
    check still catches the proxy case, and we never force a range purely on a
    missing count (that is the band-meaningfulness gate's job).
    """
    try:
        n = int(sample_size) if sample_size is not None else 0
    except (TypeError, ValueError):
        n = 0
    if 1 <= n <= MIN_COMPARABLES_FOR_POINT_HEADLINE:
        return True
    return is_country_baseline_contract(benchmark_contract)


def localized_honest_benchmark_source_label(
    data_source: object,
    benchmark_contract: Optional[dict],
    locale: str,
) -> object:
    """Return a user-facing benchmark source label.

    When the contract is a Damodaran/country-average fallback (no real sector
    transactions available), we surface an honest label instead of the raw
    internal key — e.g. "Country baseline fallback (BE, native country,
    Damodaran European)" or "titan_enrichment" — so a reader can understand
    the quality of the data behind the multiple.
    """
    # Country-baseline (Damodaran) takes priority — most important disclosure.
    if is_country_baseline_contract(benchmark_contract):
        loc = str(locale or "nl").lower()
        if loc.startswith("fr"):
            return "Damodaran / Moyenne pays (aucune transaction sectorielle disponible)"
        if loc.startswith("en"):
            return "Damodaran / Country baseline (no sector-specific transactions available)"
        return "Damodaran / Landgemiddelde (geen sectorspecifieke transacties beschikbaar)"

    # Sector-anchor sentinel from the engine's own anchor fallback path.
    if data_source == _ENGINE_SECTOR_ANCHOR_SOURCE:
        return localized_benchmark_data_source_label(data_source, locale)

    # Raw internal keys and old saved benchmark labels are not meaningful to a
    # report reader; present the client-facing index name instead.
    if data_source in _OPAQUE_INTERNAL_SOURCES or _is_internal_delphi_source(data_source):
        return _localized_upswitch_index_label(locale)

    # Readable strings from the engine (e.g. "Country baseline fallback …")
    # pass through so existing informative labels are preserved.
    return data_source
