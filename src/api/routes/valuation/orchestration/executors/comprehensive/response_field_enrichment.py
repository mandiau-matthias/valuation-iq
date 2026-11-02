"""Small response-field enrichment helpers for comprehensive responses."""

from __future__ import annotations

from typing import Optional

from src.services.reports.official_variance_context import (
    official_inputs_all_rejected,
    official_revenue_is_comparable,
)


def _field_value(official_financials: dict[str, object], field_name: str) -> object:
    aliases = {
        "total_assets": ("total_assets", "totalAssets"),
        "equity": ("equity",),
        "revenue": ("revenue",),
        "ebitda": ("ebitda",),
    }
    for alias in aliases[field_name]:
        if alias in official_financials:
            return official_financials.get(alias)
    return None


# Engine field name -> Hermes `field_provenance.field` name. Hermes writes provenance in
# its own vocabulary (see apps/hermes `aggregation_quality.field_value_map`); for these
# four the two vocabularies coincide, but keep the bridge explicit so a rename stays a
# one-liner.
_HERMES_PROVENANCE_FIELD = {
    "revenue": "revenue",
    "ebitda": "ebitda",
    "total_assets": "total_assets",
    "equity": "equity",
}

# A snapshot in one of these states came back from a failed fetch: the source is branded
# but no figure was actually read.
_UNHEALTHY_OFFICIAL_STATES = {"degraded", "unavailable", "disabled", "error", "failed"}


def official_snapshot_is_healthy(official_financials: object) -> bool:
    """Public form of :func:`_official_snapshot_is_healthy` for the presentation
    layer. A non-dict (absent snapshot) is *not* unhealthy — there was nothing to
    cross-check, which is different from a cross-check that failed."""
    if not isinstance(official_financials, dict):
        return True
    return _official_snapshot_is_healthy(official_financials)


def _official_snapshot_is_healthy(official_financials: dict[str, object]) -> bool:
    """False when the official fetch failed and only branded boilerplate came back."""
    data_health = official_financials.get("data_health") or official_financials.get("dataHealth")
    if not isinstance(data_health, dict):
        return True
    # Delphi writes `state`; the report templates read `status` first — accept both.
    states = {
        str(data_health.get(key) or "").strip().lower() for key in ("state", "status")
    }
    return not (states & _UNHEALTHY_OFFICIAL_STATES)


def _live_accounting_provenance(request: object) -> dict[str, dict[str, object]]:
    """Per-field Hermes provenance rows, newest fiscal year wins.

    Reads `business_context._import_quality`, the year-keyed Hermes `import_quality`
    blob Titan forwards from `accountant_customers`. Shape:
    `{"2025": {"field_provenance": [{field, value, source_accounts, mapping_method}, ...]}}`.
    """
    business_context = getattr(request, "business_context", None)
    if not isinstance(business_context, dict):
        return {}
    import_quality = business_context.get("_import_quality")
    if not isinstance(import_quality, dict):
        return {}

    by_field: dict[str, dict[str, object]] = {}
    for year_key in sorted(import_quality.keys(), key=lambda key: str(key)):
        year_payload = import_quality.get(year_key)
        if not isinstance(year_payload, dict):
            continue
        rows = year_payload.get("field_provenance")
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            field_name = row.get("field")
            if not isinstance(field_name, str) or row.get("value") is None:
                continue
            by_field[field_name] = {**row, "fiscal_year": year_key}
    return by_field


def _live_accounting_source_label(request: object) -> str:
    business_context = getattr(request, "business_context", None)
    provider = ""
    if isinstance(business_context, dict):
        raw = business_context.get("_financial_data_source") or business_context.get(
            "_accounting_provider"
        )
        if isinstance(raw, str):
            provider = raw.strip()
    return f"Live accounting ledger ({provider})" if provider else "Live accounting ledger"


def build_official_field_metadata(request: object) -> dict[str, object] | None:
    """Build field metadata naming the source that ACTUALLY supplied each number.

    Precedence per field:
      1. metadata already on the request (never re-derived);
      2. live accounting — Hermes/Silverfin `field_provenance` carrying a value;
      3. the official filing snapshot, but only when it is healthy AND holds a value;
      4. otherwise `missing` with source `unknown` — never a filing whose fetch failed.
    """
    official_financials = getattr(request, "official_financials", None)
    official_financials = official_financials if isinstance(official_financials, dict) else {}
    live_provenance = _live_accounting_provenance(request)
    if not official_financials and not live_provenance:
        return None

    filing_year = official_financials.get("filing_year") or official_financials.get("filingYear")
    source_label = official_financials.get("source_label") or official_financials.get("sourceLabel")
    # A degraded snapshot may still be worth citing elsewhere, but it cannot be the
    # source of a number nobody read.
    official_holds_figures = _official_snapshot_is_healthy(official_financials)
    live_source_label = _live_accounting_source_label(request)
    field_metadata = dict(getattr(request, "field_metadata", None) or {})

    def official_field_metadata(value: object) -> dict[str, object]:
        # A healthy filing that simply does not report this line is still the source we
        # consulted, so it keeps naming itself for the `missing` case.
        return {
            "status": "available" if value is not None else "missing",
            "source": "official_filing",
            "confidence": 0.95 if value is not None else 0.4,
            "originalValue": value,
            "normalizedValue": value,
            "normalizationReason": None,
            "sourceReference": source_label or "Official filing",
            "lastUpdated": filing_year,
        }

    def live_field_metadata(row: dict[str, object]) -> dict[str, object]:
        value = row.get("value")
        source_accounts = row.get("source_accounts")
        mapping_method = str(row.get("mapping_method") or "direct")
        return {
            "status": "available",
            "source": "live_accounting",
            # A derived mapping (a sum, a fallback account) is a weaker claim than a
            # figure read straight off one ledger account.
            "confidence": 0.95 if mapping_method == "direct" else 0.8,
            "originalValue": value,
            "normalizedValue": value,
            "normalizationReason": None,
            "sourceReference": live_source_label,
            "sourceAccounts": source_accounts if isinstance(source_accounts, list) else [],
            "mappingMethod": mapping_method,
            "lastUpdated": row.get("fiscal_year"),
        }

    def unattributed_field_metadata() -> dict[str, object]:
        # No source actually produced this number. Naming a filing we could not read is
        # how "NBB filing via Staatsbladmonitor" ended up stamped on live ledger figures.
        return {
            "status": "missing",
            "source": "unknown",
            "confidence": 0.0,
            "originalValue": None,
            "normalizedValue": None,
            "normalizationReason": None,
            "sourceReference": None,
            "lastUpdated": None,
        }

    for field_name in ("revenue", "ebitda", "total_assets", "equity"):
        if field_name in field_metadata:
            continue

        live_row = live_provenance.get(_HERMES_PROVENANCE_FIELD[field_name])
        if live_row is not None:
            field_metadata[field_name] = live_field_metadata(live_row)
            continue

        # An official row that was retained as evidence but rejected as a valuation input
        # must not be named as the source of that input at all — omitted, not "missing".
        if field_name == "revenue" and not official_revenue_is_comparable(official_financials):
            continue
        if field_name in {"revenue", "ebitda"} and official_inputs_all_rejected(
            official_financials
        ):
            continue

        field_metadata[field_name] = (
            official_field_metadata(_field_value(official_financials, field_name))
            if official_holds_figures
            else unattributed_field_metadata()
        )

    return field_metadata


def resolve_methodology_name(
    *,
    methodology: str,
    dcf_weight: object,
    multiples_weight: object,
    requested_dcf_only: bool,
    raw_dcf_result: object,
) -> str:
    """Return user-facing methodology label for the response payload."""
    if requested_dcf_only and raw_dcf_result is not None:
        return "Discounted Cash Flow (DCF)"
    if methodology == "STARTUP":
        return "Startup Valuation"
    if methodology == "ASSET_BASED":
        return "Asset-Based Valuation (Adjusted NAV)"
    if methodology == "REAL_ESTATE_YIELD":
        return "Real Estate Yield (Income Capitalisation)"
    if dcf_weight > 0.5:
        return "Discounted Cash Flow (DCF)"
    if multiples_weight > 0.5:
        return "Market Multiples"
    return "Hybrid Valuation"
