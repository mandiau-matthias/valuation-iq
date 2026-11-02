"""Publication-safe valuation audit snapshot.

The public company surface needs to explain the *calculation that actually ran*,
not reconstruct it later from whichever benchmark happens to be current.  This
module projects the stateless result into a deliberately bounded disclosure:
enough to reconcile inputs, benchmark, method and EV/equity basis, without
exposing source-blend weights, model thresholds or calibration coefficients.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping

_PUBLIC_SOURCE_ALIASES = {
    "australian_business_register_bulk_extract": "australian_business_register",
    "cbso_bulk": "cbso",
    "cbe": "kbo",
    "cbe_open_data": "kbo",
    "companies_house_free_company_data": "companies_house",
    "companies_house_profile": "companies_house",
    "corporations_canada_active_cbca_open_data": "corporations_canada",
    "dk_cvr": "cvr",
    "finland_prh_digital_financials": "finland_prh_open_data",
    "finland_prh_ytj_daily_trade_register": "finland_prh_open_data",
    "fr_sirene": "sirene",
    "kvk_open_dataset": "kvk",
    "fr_inpi_accounts": "inpi",
    "fr_inpi_rne": "inpi",
    # The sealed source-native France V2 bundle uses this exact authority for
    # public RNE annual accounts.  It is the same official INPI source as the
    # older aliases above, not a new evidence provider.
    "fr_inpi_rne_comptes_annuels": "inpi",
    "fss_opendart_disclosing_company_codes": "opendart",
    "ireland_cro_open_data": "ireland_cro",
    "japan_gbizinfo_financials": "japan_gbizinfo",
    "japan_nta_corporate_number_bulk": "japan_nta",
    "kbo_open_data": "kbo",
    "nz_companies_office_monthly_core_data": "nz_companies_office",
    "prh": "finland_prh_open_data",
    "sec_companyfacts": "sec_edgar",
    "sec_edgar_exchange_reporting_subset": "sec_edgar",
    "staatsbladmonitor": "staatsbladmonitor",
}
_PUBLIC_SOURCE_IDS = {
    "australian_business_register",
    "bolagsverket",
    "brreg",
    "cbso",
    "companies_house",
    "corporations_canada",
    "cvr",
    "estonia_ariregister_open_data",
    "finland_prh_open_data",
    "inpi",
    "ireland_cro",
    "japan_gbizinfo",
    "japan_nta",
    "kbo",
    "kvk",
    "lithuania_rc_financial_statements",
    "nz_companies_office",
    "opendart",
    "sec_edgar",
    "sirene",
    "slovakia_ruz_open_api",
    "staatsbladmonitor",
}
_INTERNAL_DISCLOSURE_TEXT = re.compile(
    r"\b(?:athena|delphi|titan)\b|raw_company_filings|"
    r"source[_ -]?mix|provider[_ -]?weight|threshold|coefficient",
    re.IGNORECASE,
)
_BASIS_CURRENCY = re.compile(
    r"(?:filed_amount_|period_end_fx_to_)([a-z]{3})(?:\b|_)", re.IGNORECASE
)


def _mapping(value: object) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    dump = getattr(value, "model_dump", None)
    if callable(dump):
        dumped = dump(mode="python")
        return dumped if isinstance(dumped, Mapping) else {}
    return {}


def _decimal(value: object) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    return parsed if parsed.is_finite() else None


def _number(value: object) -> float | int | None:
    parsed = _decimal(value)
    if parsed is None:
        return None
    integral = parsed.to_integral_value()
    if parsed == integral:
        return int(integral)
    return float(parsed)


def _confidence_level(value: object, *, lower: bool) -> str:
    normalized = str(value or "LOW").strip().lower()
    if normalized not in {"low", "medium", "high"}:
        normalized = "low"
    if not lower:
        return normalized
    return {"high": "medium", "medium": "low", "low": "low"}[normalized]


def _timestamp(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _text(value: object, *, limit: int = 240) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    return cleaned[:limit] if cleaned else None


def _public_text(value: object, *, limit: int = 240) -> str | None:
    candidate = _text(value, limit=limit)
    return candidate if candidate and _INTERNAL_DISCLOSURE_TEXT.search(candidate) is None else None


def _https_url(value: object) -> str | None:
    candidate = _text(value, limit=500)
    return candidate if candidate and candidate.lower().startswith("https://") else None


def _public_source_identifier(value: object) -> str | None:
    candidate = _text(value, limit=80)
    if not candidate:
        return None
    canonical = _PUBLIC_SOURCE_ALIASES.get(candidate.lower(), candidate.lower())
    return canonical if canonical in _PUBLIC_SOURCE_IDS else None


def _band(low: Decimal, mid: Decimal, high: Decimal) -> dict[str, float | int]:
    return {
        "low": _number(low) or 0,
        "mid": _number(mid) or 0,
        "high": _number(high) or 0,
    }


def _canonical_hash(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def _verified_modeled_dcf_resolution(
    metadata: Mapping[str, Any],
    *,
    failure_reasons: list[str] | None = None,
) -> dict[str, object] | None:
    profile = _mapping(metadata.get("public_adaptive_resolution"))
    resolution = dict(_mapping(profile.get("modeled_dcf_resolution")))
    if (
        resolution.get("schema_version") != "public_modeled_dcf_resolution.v1"
        or resolution.get("authority") != "valuation_iq"
        or resolution.get("policy_version")
        not in {
            "valuation_iq_public_dcf_defaults.v1",
            "valuation_iq_public_dcf_defaults.v2",
            "valuation_iq_public_dcf_defaults.v3",
            "valuation_iq_public_dcf_defaults.v4",
        }
        or resolution.get("status") != "available"
    ):
        if failure_reasons is not None:
            failure_reasons.append("modeled_dcf_resolution_not_available")
        return None
    claimed = resolution.pop("resolution_hash", None)
    if not isinstance(claimed, str) or claimed != _canonical_hash(resolution):
        if failure_reasons is not None:
            failure_reasons.append("modeled_dcf_resolution_hash_invalid")
        return None
    return {**resolution, "resolution_hash": claimed}


def _modeled_dcf_wacc_reconciles(
    modeled_dcf: Mapping[str, Any],
    dcf_results: object,
) -> bool:
    """Fail closed when the applied WACC contradicts the v3/v4 sealed policy."""

    if modeled_dcf.get("policy_version") not in {
        "valuation_iq_public_dcf_defaults.v3",
        "valuation_iq_public_dcf_defaults.v4",
    }:
        # Immutable v1/v2 artifacts remain replay-compatible. All new profile
        # resolutions are v4 and must carry the stricter component proof.
        return True
    policy = _mapping(modeled_dcf.get("wacc_policy"))
    dcf_payload = _mapping(dcf_results)
    buildup = _mapping(dcf_payload.get("wacc_buildup"))
    evidence = _mapping(buildup.get("wacc_evidence"))
    if (
        policy.get("authority") != "valuation_iq"
        or policy.get("rate_model") != "country_sector_capm"
        or not buildup
        or not evidence
    ):
        return False

    resolved_wacc = _decimal(dcf_payload.get("wacc"))
    cost_of_equity = _decimal(buildup.get("cost_of_equity"))
    cost_of_debt = _decimal(buildup.get("cost_of_debt"))
    equity_weight = _decimal(buildup.get("equity_weight"))
    debt_weight = _decimal(buildup.get("debt_weight"))
    tax_rate = _decimal(buildup.get("tax_rate"))
    if any(
        value is None
        for value in (
            resolved_wacc,
            cost_of_equity,
            cost_of_debt,
            equity_weight,
            debt_weight,
            tax_rate,
        )
    ):
        return False
    assert resolved_wacc is not None
    assert cost_of_equity is not None
    assert cost_of_debt is not None
    assert equity_weight is not None
    assert debt_weight is not None
    assert tax_rate is not None
    if (
        resolved_wacc <= 0
        or cost_of_equity < 0
        or cost_of_debt < 0
        or equity_weight < 0
        or debt_weight < 0
        or tax_rate < 0
        or tax_rate > 1
        or abs(equity_weight + debt_weight - Decimal("1")) > Decimal("0.000001")
    ):
        return False
    component_wacc = equity_weight * cost_of_equity + debt_weight * cost_of_debt * (
        Decimal("1") - tax_rate
    )
    expected_wacc = min(Decimal("0.30"), max(Decimal("0.05"), component_wacc))
    if abs(resolved_wacc - expected_wacc) > Decimal("0.00001"):
        return False

    fallback = policy.get("capital_structure_fallback") is True
    if fallback:
        policy_equity_weight = _decimal(policy.get("equity_weight"))
        policy_debt_weight = _decimal(policy.get("debt_weight"))
        return bool(
            policy.get("capital_structure_source") == "valuation_iq_public_default_70_30"
            and evidence.get("capital_structure_source") == "fallback_70_30_equity_debt"
            and evidence.get("capital_structure_fallback") is True
            and policy_equity_weight == equity_weight
            and policy_debt_weight == debt_weight
        )
    return bool(
        policy.get("capital_structure_source") == "source_bound_balance_sheet"
        and evidence.get("capital_structure_source")
        in {"observed_balance_sheet", "observed_no_debt_balance_sheet"}
        and evidence.get("capital_structure_fallback") is False
    )


def _weighted_contributions(value: object) -> list[dict[str, object]]:
    result = _mapping(value)
    raw = result.get("contributions")
    if not isinstance(raw, list):
        return []
    contributions: list[dict[str, object]] = []
    for entry in raw:
        row = dict(_mapping(entry))
        key = _text(row.get("method_key"), limit=80)
        weight = _decimal(row.get("weight"))
        ev_mid = _decimal(row.get("enterprise_value"))
        if (
            key not in {"dcf", "ebitda_multiple", "omzet_multiple"}
            or weight is None
            or weight <= 0
            or ev_mid is None
            or ev_mid <= 0
        ):
            continue
        ev_low = _decimal(row.get("enterprise_value_low")) or ev_mid
        ev_high = _decimal(row.get("enterprise_value_high")) or ev_mid
        if ev_low < 0 or not ev_low <= ev_mid <= ev_high:
            continue
        contributions.append(
            {
                "method_key": key,
                "weight": weight,
                "enterprise_value_low": ev_low,
                "enterprise_value_mid": ev_mid,
                "enterprise_value_high": ev_high,
            }
        )
    return contributions


def _public_financial_inputs(request: object) -> list[dict[str, object]]:
    metadata = _mapping(getattr(request, "metadata", None))
    raw_inputs = metadata.get("public_financial_inputs")
    if not isinstance(raw_inputs, list):
        return []

    allowed_metrics = {
        "revenue",
        "gross_margin",
        "ebitda",
        "total_assets",
        "total_liabilities",
        "equity",
        "total_debt",
        "lease_liabilities",
        "cash",
    }
    inputs: list[dict[str, object]] = []
    for raw in raw_inputs[:12]:
        row = _mapping(raw)
        metric = _text(row.get("metric"), limit=40)
        fiscal_year = _number(row.get("fiscal_year"))
        if metric not in allowed_metrics or not isinstance(fiscal_year, int):
            continue
        amount = _number(row.get("amount"))
        inputs.append(
            {
                "metric": metric,
                "amount": amount,
                "fiscal_year": fiscal_year,
                "source_identifier": _public_source_identifier(row.get("source_identifier")),
                "source_record_id": _public_text(row.get("source_record_id"), limit=160),
                "source_parser_version": _public_text(row.get("source_parser_version"), limit=80),
                "basis": _public_text(row.get("basis"), limit=120),
                "currency": (
                    str(row.get("currency")).strip().upper()
                    if isinstance(row.get("currency"), str)
                    and re.fullmatch(r"[A-Za-z]{3}", str(row.get("currency")).strip())
                    else None
                ),
                "used": row.get("used") is True,
                "exclusion_reason": _public_text(row.get("exclusion_reason"), limit=120),
            }
        )
    return inputs


def _historical_inputs_are_source_bound(
    inputs: list[dict[str, object]],
    *,
    fiscal_year: int,
) -> bool:
    """Accept immutable official filing lineage without inventing parser data.

    Older corpus rows sometimes predate parser-version persistence. Their
    canonical public source, immutable filing record id, fiscal year, and
    metric/currency basis still trace the fact to official evidence. A parser
    version remains disclosed when present, but absence alone cannot turn that
    filing into modeled or anonymous data.
    """
    return bool(inputs) and all(
        row.get("fiscal_year") == fiscal_year
        and isinstance(row.get("source_identifier"), str)
        and bool(str(row.get("source_identifier")).strip())
        and isinstance(row.get("source_record_id"), str)
        and bool(str(row.get("source_record_id")).strip())
        and isinstance(row.get("basis"), str)
        and bool(str(row.get("basis")).strip())
        for row in inputs
    )


def _resolve_public_currency(
    request: object,
    used_inputs: list[dict[str, object]],
) -> tuple[str | None, bool]:
    explicit = getattr(request, "currency", None)
    explicit_currency = (
        str(explicit).strip().upper()
        if isinstance(explicit, str) and re.fullmatch(r"[A-Za-z]{3}", explicit.strip())
        else None
    )
    observed: set[str] = set()
    for row in used_inputs:
        row_currency = row.get("currency")
        if isinstance(row_currency, str):
            observed.add(row_currency.upper())
            continue
        basis = row.get("basis")
        if isinstance(basis, str):
            match = _BASIS_CURRENCY.search(basis)
            if match:
                observed.add(match.group(1).upper())
    if explicit_currency is not None:
        return explicit_currency, not observed or observed == {explicit_currency}
    if len(observed) == 1:
        return next(iter(observed)), True
    return None, False


def _input_amount(
    inputs: list[dict[str, object]],
    metric: str,
) -> Decimal | None:
    for row in inputs:
        if row.get("metric") == metric:
            return _decimal(row.get("amount"))
    return None


def _align_financial_input_usage(
    inputs: list[dict[str, object]],
    *,
    approach: str,
    earnings_basis: str | None,
    dcf_source_metric: str | None = None,
) -> list[dict[str, object]]:
    """Mark only lines that materially fed the calculation as used.

    Titan cannot know which earnings basis the adaptive engine ultimately
    selects when it assembles the request. The immutable response snapshot can,
    so it owns this final usage classification.
    """

    selected_earnings_metric = None
    if approach in {"market", "hybrid"}:
        normalized_basis = str(earnings_basis or "").strip().upper()
        selected_earnings_metric = {
            "EBITDA": "ebitda",
            "REVENUE": "revenue",
        }.get(normalized_basis)
        if selected_earnings_metric is None and approach == "market":
            return []

    dcf_metrics = {
        "revenue": {"revenue"},
        "ebitda": {"ebitda"},
        "revenue_and_ebitda": {"revenue", "ebitda"},
    }.get(str(dcf_source_metric or ""), set())

    aligned: list[dict[str, object]] = []
    for raw in inputs:
        row = dict(raw)
        metric = row.get("metric")
        if metric in {"ebitda", "revenue"}:
            selected = metric == selected_earnings_metric or metric in dcf_metrics
            row["used"] = selected
            if selected:
                row["exclusion_reason"] = None
            elif approach in {"market", "hybrid"} and row.get("exclusion_reason") is None:
                row["exclusion_reason"] = "not_selected_earnings_basis"
        aligned.append(row)
    return aligned


def _submitted_source_identifier(
    request: object,
    *,
    metric: object,
    fiscal_year: object,
) -> str | None:
    """Return the producer's own source label for one filing line.

    ``_public_financial_inputs`` deliberately drops any label that is not a
    governed official registry, so the published audit can never cite it. A
    refusal still has to tell the producer which label it sent. The value is
    diagnostics for the caller only and never enters an audit snapshot.
    """
    metadata = _mapping(getattr(request, "metadata", None))
    raw_inputs = metadata.get("public_financial_inputs")
    if not isinstance(raw_inputs, list):
        return None
    for raw in raw_inputs[:12]:
        row = _mapping(raw)
        if (
            _text(row.get("metric"), limit=40) == metric
            and _number(row.get("fiscal_year")) == fiscal_year
        ):
            return _text(row.get("source_identifier"), limit=80)
    return None


def _financial_semantics_failures(
    request: object,
    used_inputs: list[dict[str, object]],
) -> list[dict[str, object]]:
    """Explain why the ``financial_semantics`` control fails; empty means it passes.

    Every filing line that fed the published value must carry an amount and a
    governed official-registry source, and gross margin must never stand in for
    revenue or EBITDA. The control alone cannot say which of these a request
    broke, or on which line.
    """

    if not used_inputs:
        return [{"control": "financial_semantics", "reason": "no_used_financial_input"}]
    failures: list[dict[str, object]] = []
    for row in used_inputs:
        line = {
            "control": "financial_semantics",
            "metric": row.get("metric"),
            "fiscal_year": row.get("fiscal_year"),
        }
        if row.get("amount") is None:
            failures.append({**line, "reason": "amount_missing"})
        if row.get("source_identifier") is None:
            submitted = _submitted_source_identifier(
                request,
                metric=row.get("metric"),
                fiscal_year=row.get("fiscal_year"),
            )
            failures.append(
                {
                    **line,
                    "reason": (
                        "source_not_official_public_registry"
                        if submitted is not None
                        else "source_identifier_missing"
                    ),
                    "submitted_source_identifier": submitted,
                }
            )
        if (
            row.get("metric") == "gross_margin"
            or row.get("basis") == "gross_margin"
            or row.get("basis") == "filed_gross_margin"
        ):
            failures.append({**line, "reason": "gross_margin_used_as_earnings"})
    return failures


def _benchmark_snapshot(
    benchmark_contract: Mapping[str, Any],
) -> dict[str, object] | None:
    if benchmark_contract.get("status") != "resolved":
        return None
    primary_metric = _text(benchmark_contract.get("primary_metric"), limit=40)
    metrics = _mapping(benchmark_contract.get("metrics"))
    metric = _mapping(metrics.get(primary_metric)) if primary_metric else {}
    if not metric and metrics:
        first_key, first_value = next(iter(metrics.items()))
        primary_metric = _text(first_key, limit=40)
        metric = _mapping(first_value)
    if not primary_metric or not metric:
        return None

    is_borrowed = bool(metric.get("is_borrowed", benchmark_contract.get("is_borrowed", False)))
    return {
        "metric": primary_metric,
        "business_type_id": _public_text(
            metric.get(
                "source_business_type_id",
                benchmark_contract.get("source_business_type_id"),
            ),
            limit=120,
        ),
        "business_type_title": _public_text(
            metric.get(
                "source_business_type_title",
                benchmark_contract.get("source_business_type_title"),
            ),
            limit=160,
        ),
        "p25": _number(metric.get("p25")),
        "median": _number(metric.get("median")),
        "p75": _number(metric.get("p75")),
        "sample_size": _number(metric.get("sample_size", benchmark_contract.get("sample_size"))),
        "tier": _text(metric.get("tier", benchmark_contract.get("tier")), limit=4),
        "country_code": _text(
            metric.get("country_code", benchmark_contract.get("country_code")), limit=2
        ),
        "region_key": _text(
            metric.get("region_key", benchmark_contract.get("region_key")), limit=40
        ),
        "match_type": "borrowed" if is_borrowed else "direct",
        # The direct/borrowed outcome is reviewable; the internal fallback walk
        # used to resolve it is part of the proprietary benchmark blend.
        "walk_step": None,
        "borrowed_from_country": _text(
            metric.get(
                "borrowed_from_country",
                benchmark_contract.get("borrowed_from_country"),
            ),
            limit=2,
        ),
        "dataset_version_id": _public_text(
            metric.get(
                "dataset_version_id",
                benchmark_contract.get("dataset_version_id"),
            ),
            limit=160,
        ),
        "methodology_version": _public_text(
            metric.get(
                "methodology_version",
                benchmark_contract.get("methodology_version"),
            ),
            limit=120,
        ),
        "published_at": _text(
            metric.get("published_at", benchmark_contract.get("published_at")),
            limit=40,
        ),
        "benchmark_scope": _public_text(
            metric.get(
                "benchmark_scope",
                benchmark_contract.get("benchmark_scope"),
            ),
            limit=80,
        ),
        "benchmark_kind": _public_text(
            metric.get("benchmark_kind", benchmark_contract.get("benchmark_kind")),
            limit=80,
        ),
        # Never invent a vintage URL. Preserve it only when the resolved Index
        # contract explicitly carries a safe public HTTPS location.
        "vintage_url": _https_url(metric.get("vintage_url", benchmark_contract.get("vintage_url"))),
    }


def _modeled_prior_snapshot(
    metadata: Mapping[str, Any],
    *,
    preferred_metric: str | None = None,
) -> dict[str, object] | None:
    """Project a verified Business Types prior without calling it transaction data."""

    resolution = _mapping(metadata.get("public_adaptive_resolution"))
    raw_contracts = metadata.get("public_modeled_prior_contracts")
    contracts = (
        [_mapping(value) for value in raw_contracts]
        if isinstance(raw_contracts, list)
        else [_mapping(metadata.get("public_modeled_prior_contract"))]
    )
    contract = next(
        (value for value in contracts if value.get("metric") == preferred_metric),
        contracts[0] if contracts else {},
    )
    schema_version = contract.get("schema_version")
    is_v2 = schema_version == "public_modeled_prior_contract.v2"
    contract_hash = contract.get("contract_hash")
    resolved_hashes = _mapping(resolution.get("modeled_prior_contract_hashes"))
    resolved_bands = _mapping(resolution.get("resolved_multiple_bands"))
    metric_name = _text(contract.get("metric"), limit=40)
    resolved_hash = (
        resolved_hashes.get(metric_name)
        if is_v2 and metric_name
        else resolution.get("modeled_prior_contract_hash")
    )
    distribution = (
        _mapping(resolved_bands.get(metric_name))
        if is_v2 and metric_name
        else _mapping(resolution.get("resolved_multiple_band"))
    )
    max_public_grade = contract.get("max_public_grade")
    if (
        schema_version
        not in {
            "public_modeled_prior_contract.v1",
            "public_modeled_prior_contract.v2",
        }
        or contract.get("authority") != "business_types_modeled_prior"
        or contract.get("confidence") != "low"
        or max_public_grade not in {"T2-M", "T3-M"}
        or resolved_hash != contract_hash
    ):
        return None
    low = _number(distribution.get("low"))
    median = _number(distribution.get("mid"))
    high = _number(distribution.get("high"))
    if low is None or median is None or high is None:
        return None
    return {
        "metric": metric_name,
        "business_type_id": _public_text(contract.get("business_type_id"), limit=120),
        "business_type_title": _public_text(contract.get("business_type_title"), limit=160),
        "p25": low,
        "median": median,
        "p75": high,
        "sample_size": 0,
        "tier": None,
        "country_code": _text(contract.get("country_code"), limit=2),
        "region_key": None,
        "match_type": "inferred",
        "walk_step": None,
        "borrowed_from_country": None,
        "dataset_version_id": _public_text(contract.get("dataset_version_id"), limit=160),
        "methodology_version": _public_text(contract.get("methodology_version"), limit=120),
        "published_at": _text(contract.get("published_at"), limit=40),
        "benchmark_scope": "business_type_modeled_prior",
        "benchmark_kind": "modeled_prior",
        "range_derivation": _mapping(resolution.get("multiple_band_derivation")) or None,
        "vintage_url": None,
        "contract_hash": _public_text(contract_hash, limit=80),
        "max_public_grade": max_public_grade,
    }


def _bridge_snapshot(
    *,
    request: object,
    equity_low: Decimal,
    equity_mid: Decimal,
    equity_high: Decimal,
    approach: str,
    financial_inputs: list[dict[str, object]],
) -> tuple[str, dict[str, object], Decimal, Decimal, Decimal]:
    current = getattr(request, "current_year", None)
    engine_debt = _decimal(getattr(current, "total_debt", None))
    engine_cash = _decimal(getattr(current, "cash", None))
    filed_debt = _input_amount(financial_inputs, "total_debt")
    filed_leases = _input_amount(financial_inputs, "lease_liabilities")
    filed_cash = _input_amount(financial_inputs, "cash")

    if approach == "asset":
        bridge = {
            "status": "not_applicable",
            "enterprise_value": None,
            "total_debt": None,
            "lease_liabilities": None,
            "cash": None,
            "net_debt": None,
            "net_debt_source": "not_applicable",
            "equity_value": _band(equity_low, equity_mid, equity_high),
            "assumption": None,
        }
        return "net_asset_reference", bridge, equity_low, equity_mid, equity_high

    # Titan sends debt including explicitly reported lease liabilities to the
    # engine. Reconstruct the exact market EV from the engine's equity result
    # even when one public bridge component is unavailable.
    engine_net_debt = (engine_debt or Decimal("0")) - (engine_cash or Decimal("0"))
    ev_low = equity_low + engine_net_debt
    ev_mid = equity_mid + engine_net_debt
    ev_high = equity_high + engine_net_debt
    complete_bridge = (
        filed_debt is not None
        and filed_leases is not None
        and filed_cash is not None
        and engine_debt is not None
        and engine_cash is not None
        and abs(engine_debt - filed_debt - filed_leases) <= Decimal("1")
        and abs(engine_cash - filed_cash) <= Decimal("1")
    )
    if complete_bridge:
        net_debt = filed_debt + filed_leases - filed_cash
        bridge = {
            "status": "complete",
            "enterprise_value": _band(ev_low, ev_mid, ev_high),
            "total_debt": _number(filed_debt),
            "lease_liabilities": _number(filed_leases),
            "cash": _number(filed_cash),
            "net_debt": _number(net_debt),
            "net_debt_source": "filed_inputs",
            "equity_value": _band(equity_low, equity_mid, equity_high),
            "assumption": None,
        }
        return "equity_value", bridge, ev_low, ev_mid, ev_high

    # Do not launder missing lease/debt/cash data into a complete equity bridge.
    # The engine's own EV can still be reconciled from the exact request/result,
    # but only that enterprise-value band is publication-grade.
    all_bridge_inputs_missing = filed_debt is None and filed_leases is None and filed_cash is None
    bridge = {
        "status": "assumed" if all_bridge_inputs_missing else "unavailable",
        "enterprise_value": _band(ev_low, ev_mid, ev_high),
        "total_debt": _number(filed_debt),
        "lease_liabilities": _number(filed_leases),
        "cash": _number(filed_cash),
        "net_debt": None,
        "net_debt_source": "assumed_zero" if all_bridge_inputs_missing else "unavailable",
        "equity_value": None,
        "assumption": "net_debt_and_lease_inputs_unavailable",
    }
    return "enterprise_value", bridge, ev_low, ev_mid, ev_high


def build_public_valuation_audit(
    *,
    request: object,
    calculation_timestamp: str,
    equity_value_low: object,
    equity_value_mid: object,
    equity_value_high: object,
    methodology_used: str,
    dcf_weight: object,
    multiples_weight: object,
    dcf_exclusion_reason: str | None,
    earnings_basis: str | None,
    recommended_multiple: object,
    multiple_build_up: object,
    confidence_level: str,
    size_discount: object,
    liquidity_discount: object,
    country_adjustment: object,
    failure_reasons: list[str] | None = None,
    enterprise_value_low: object = None,
    enterprise_value_mid: object = None,
    enterprise_value_high: object = None,
    dcf_results: object = None,
    weighted_valuation_result: object = None,
    failure_diagnostics: list[dict[str, object]] | None = None,
) -> dict[str, object] | None:
    """Build the immutable, bounded snapshot requested by Titan.

    The snapshot is emitted only for the public-indicative route.  All values
    come from this request/result pair; no external state is read here.

    ``failure_reasons`` receives the failed control keys. ``failure_diagnostics``
    receives one machine-readable entry per filing line that failed
    ``financial_semantics`` (which line, and why), so a refusal names what the
    producer must correct instead of only the control it tripped.
    """

    metadata = _mapping(getattr(request, "metadata", None))
    public_adaptive_v2 = metadata.get("public_adaptive_profile_v2") is True
    if metadata.get("public_valuation_audit") is not True:
        if failure_reasons is not None:
            failure_reasons.append("audit_not_requested")
        return None

    low = _decimal(equity_value_low)
    mid = _decimal(equity_value_mid)
    high = _decimal(equity_value_high)
    if low is None or mid is None or high is None or low < 0 or high < low:
        if failure_reasons is not None:
            failure_reasons.append("invalid_equity_band")
        return None

    benchmark_contract = _mapping(getattr(request, "benchmark_contract", None))
    if not benchmark_contract:
        calibration = getattr(request, "business_type_calibration", None)
        benchmark_contract = _mapping(getattr(calibration, "benchmark_contract", None))
    benchmark = _benchmark_snapshot(benchmark_contract)
    contributions = _weighted_contributions(weighted_valuation_result)
    contribution_keys = {str(row["method_key"]) for row in contributions}
    preferred_metric = {
        "EBITDA": "ev_ebitda",
        "REVENUE": "ev_revenue",
    }.get(str(earnings_basis or "").strip().upper())
    if public_adaptive_v2:
        # The generic headline build-up can retain an EBITDA display basis
        # even when the final Adaptive synthesis excluded that unavailable leg
        # and priced only the source-bound revenue multiple. Select the prior
        # that actually contributed to the value; otherwise the audit looks
        # for a filed EBITDA line that was neither available nor priced.
        has_ebitda_contribution = "ebitda_multiple" in contribution_keys
        has_revenue_contribution = "omzet_multiple" in contribution_keys
        if has_revenue_contribution and not has_ebitda_contribution:
            preferred_metric = "ev_revenue"
        elif has_ebitda_contribution and not has_revenue_contribution:
            preferred_metric = "ev_ebitda"
    modeled_prior = _modeled_prior_snapshot(
        metadata,
        preferred_metric=preferred_metric,
    )
    if modeled_prior is not None:
        benchmark = modeled_prior
    effective_earnings_basis = str(earnings_basis or "").strip().upper()
    if public_adaptive_v2 and isinstance(benchmark, Mapping):
        effective_earnings_basis = {
            "ev_ebitda": "EBITDA",
            "ev_revenue": "REVENUE",
        }.get(str(benchmark.get("metric") or "").strip().lower(), effective_earnings_basis)

    weighted_payload = _mapping(weighted_valuation_result)
    uncertainty_factor = max(
        Decimal("1"),
        _decimal(weighted_payload.get("uncertainty_inflation_factor")) or Decimal("1"),
    )
    has_dcf_contribution = "dcf" in contribution_keys
    has_market_contribution = bool(
        contribution_keys.intersection({"ebitda_multiple", "omzet_multiple"})
    )
    resolved_modeled_dcf = (
        _verified_modeled_dcf_resolution(
            metadata,
            # A missing DCF contribution is a valid Adaptive outcome when the
            # modeled leg does not produce a positive enterprise value.  Only
            # make an unavailable resolution fatal when the published value
            # actually claims a DCF contribution.
            failure_reasons=failure_reasons if has_dcf_contribution else None,
        )
        if has_dcf_contribution or public_adaptive_v2
        else None
    )
    modeled_dcf = resolved_modeled_dcf if has_dcf_contribution else None
    if (
        has_dcf_contribution
        and modeled_dcf is not None
        and not _modeled_dcf_wacc_reconciles(
            modeled_dcf,
            dcf_results,
        )
    ):
        if failure_reasons is not None:
            failure_reasons.append("modeled_dcf_wacc_unreconciled")
        return None
    method_upper = str(methodology_used or "").upper()
    approach = (
        "asset"
        if method_upper == "ASSET_BASED"
        else (
            "hybrid"
            if has_dcf_contribution and has_market_contribution
            else (
                "income"
                if has_dcf_contribution
                or (
                    _decimal(dcf_weight) not in (None, Decimal("0"))
                    and _decimal(multiples_weight) in (None, Decimal("0"))
                )
                else "market"
            )
        )
    )
    inputs = _align_financial_input_usage(
        _public_financial_inputs(request),
        approach=approach,
        earnings_basis=effective_earnings_basis,
        dcf_source_metric=(
            str(modeled_dcf.get("source_metric")) if modeled_dcf is not None else None
        ),
    )
    if not inputs:
        if failure_reasons is not None:
            failure_reasons.append("earnings_basis_not_bound_to_public_input")
        return None
    value_basis, bridge, ev_low, ev_mid, ev_high = _bridge_snapshot(
        request=request,
        equity_low=low,
        equity_mid=mid,
        equity_high=high,
        approach=approach,
        financial_inputs=inputs,
    )

    methods: list[dict[str, object]] = []
    method_legs: list[dict[str, object]] = []
    dcf = _decimal(dcf_weight) or Decimal("0")
    multiples = _decimal(multiples_weight) or Decimal("0")
    if dcf > 0 and not has_dcf_contribution:
        if public_adaptive_v2 and has_market_contribution and contributions:
            # Adaptive weights describe the eligible capability set, while the
            # weighted synthesis records the methods that produced a valid
            # positive result for this exact checkpoint. A historical DCF may
            # be unavailable (for example because projected FCF is non-positive)
            # and the canonical synthesis then renormalizes the remaining
            # source-backed market legs to 100%. Audit the exact contributions;
            # never require a method that did not enter the published value.
            dcf = Decimal("0")
            multiples = Decimal("1")
        else:
            # A weight alone cannot prove a DCF leg. Public Adaptive must
            # provide either the exact DCF contribution or an exact, normalized
            # fallback contribution set before the audit can attest the result.
            if failure_reasons is not None:
                failure_reasons.append("unverified_public_dcf_leg")
            return None
    if has_dcf_contribution:
        dcf_payload = _mapping(dcf_results)
        assumptions = _mapping(modeled_dcf.get("assumptions")) if modeled_dcf else {}
        wacc = _decimal(dcf_payload.get("wacc"))
        terminal_growth_rate = _decimal(dcf_payload.get("terminal_growth_rate"))
        cash_flows = dcf_payload.get("fcf_projections_5y")
        dcf_contract_valid = bool(
            modeled_dcf is not None
            and wacc is not None
            and terminal_growth_rate is not None
            and wacc > terminal_growth_rate >= 0
            and isinstance(cash_flows, list)
            and len(cash_flows) >= 3
            and all(_decimal(value) is not None for value in cash_flows)
            and all(
                assumptions.get(key) is not None
                for key in (
                    "base_revenue",
                    "base_ebitda",
                    "revenue_growth",
                    "ebitda_margin",
                    "capex_ratio",
                    "depreciation_amortization_ratio",
                    "nwc_ratio",
                    "tax_rate",
                    "terminal_growth",
                )
            )
        )
        if not dcf_contract_valid:
            if failure_reasons is not None:
                failure_reasons.append("modeled_public_dcf_unreconciled")
            return None
    active_count = int(dcf > 0) + int(multiples > 0)
    if multiples > 0 and not contributions:
        methods.append(
            {
                "key": "market_approach",
                "approach": "market",
                "metric": (benchmark.get("metric") if isinstance(benchmark, dict) else None),
                "weight": _number(multiples) if active_count > 1 else None,
            }
        )
    if dcf > 0 and not contributions:
        methods.append(
            {
                "key": "dcf",
                "approach": "income",
                "metric": "free_cash_flow",
                "weight": _number(dcf) if active_count > 1 else None,
            }
        )
    if contributions:
        for contribution in contributions:
            method_key = str(contribution["method_key"])
            metric = {
                "ebitda_multiple": "ev_ebitda",
                "omzet_multiple": "ev_revenue",
                "dcf": "free_cash_flow",
            }[method_key]
            method = {
                "key": method_key,
                "approach": "income" if method_key == "dcf" else "market",
                "metric": metric,
                "weight": _number(contribution["weight"]),
            }
            methods.append(method)
            method_legs.append(
                {
                    **method,
                    "enterprise_value": _band(
                        contribution["enterprise_value_low"],
                        contribution["enterprise_value_mid"],
                        contribution["enterprise_value_high"],
                    ),
                }
            )
    if approach == "asset":
        methods = [
            {
                "key": "adjusted_nav",
                "approach": "asset",
                "metric": "net_assets",
                "weight": None,
            }
        ]

    excluded_methods: list[dict[str, object]] = []
    if not any(method["key"] == "dcf" for method in methods):
        excluded_methods.append(
            {
                "key": "dcf",
                # Never publish the engine's detailed exclusion text here: it
                # can contain confidential eligibility thresholds. The public
                # audit needs the decision, not the internal rule.
                "reason": (
                    "modeled_dcf_did_not_produce_positive_enterprise_value"
                    if resolved_modeled_dcf is not None
                    else "public_forecasts_and_cash_flows_unverified"
                ),
            }
        )

    build_up = _mapping(multiple_build_up)
    earnings = _decimal(build_up.get("adjusted_earnings"))
    if earnings is None or earnings <= 0:
        current = getattr(request, "current_year", None)
        basis = effective_earnings_basis
        earnings = _decimal(
            getattr(current, "revenue", None)
            if basis == "REVENUE"
            else getattr(current, "ebitda", None)
        )
    if approach in {"market", "hybrid"}:
        selected_metric = {
            "EBITDA": "ebitda",
            "REVENUE": "revenue",
        }.get(effective_earnings_basis)
        used_earnings_inputs = [
            row
            for row in inputs
            if row.get("used") is True and row.get("metric") == selected_metric
        ]
        public_earnings = (
            _decimal(used_earnings_inputs[0].get("amount"))
            if len(used_earnings_inputs) == 1
            else None
        )
        # V1 has no separate public contract for normalised earnings. If the
        # engine priced a figure that differs from the contributed filing
        # line, publishing the filed amount beside that value would produce a
        # plausible-looking but non-reproducible bridge. Withhold instead.
        engine_earnings_reconciles = (
            earnings is not None
            and public_earnings is not None
            and public_earnings > 0
            and abs(earnings - public_earnings) <= Decimal("1")
        )
        # Public Adaptive V2 already forbids private or unbound
        # normalizations. Its public calculation contract selects the filed
        # revenue/EBITDA metric, while the generic report build-up can retain
        # an internal cross-method earnings label. Reconcile disclosure to the
        # actual filed input and the final EV band; do not let that presentation
        # label veto an otherwise reproducible valuation.
        if (
            public_earnings is None
            or public_earnings <= 0
            or (not public_adaptive_v2 and not engine_earnings_reconciles)
        ):
            if failure_reasons is not None:
                failure_reasons.append("filed_earnings_do_not_reconcile")
            return None
        earnings = public_earnings
    effective_multiple_band = None
    market_leg_band: Mapping[str, Any] = {}
    if approach in {"market", "hybrid"} and earnings is not None and earnings > 0:
        market_leg = next(
            (
                leg
                for leg in method_legs
                if leg.get("metric")
                == ("ev_revenue" if effective_earnings_basis == "REVENUE" else "ev_ebitda")
            ),
            None,
        )
        market_leg_band = _mapping(market_leg.get("enterprise_value")) if market_leg else {}
        multiple_ev_low = _decimal(market_leg_band.get("low")) or ev_low
        multiple_ev_mid = _decimal(market_leg_band.get("mid")) or ev_mid
        multiple_ev_high = _decimal(market_leg_band.get("high")) or ev_high
        effective_multiple_band = {
            "metric": (
                benchmark.get("metric")
                if isinstance(benchmark, dict)
                else ("ev_revenue" if effective_earnings_basis == "REVENUE" else "ev_ebitda")
            ),
            "low": _number(multiple_ev_low / earnings),
            # This is the multiple that reconciles to the value actually
            # published after calibration, not the pre-calibration recommendation.
            "mid": _number(multiple_ev_mid / earnings),
            "high": _number(multiple_ev_high / earnings),
        }

    adjustments: list[dict[str, str]] = []
    for category, raw in (
        ("company_size", size_discount),
        ("private_company_liquidity", liquidity_discount),
        ("country_context", country_adjustment),
    ):
        value = _decimal(raw)
        if value is None or value == 0:
            continue
        # The stateless headline exposes these fields as positive discount
        # rates. Their public direction is therefore down, while the magnitude
        # and composition remain confidential.
        adjustments.append({"category": category, "direction": "down"})
    if high > low:
        adjustments.append({"category": "range_uncertainty", "direction": "widen"})

    used_inputs = [row for row in inputs if row.get("used") is True]
    # One evaluation yields both the verdict and the refusal reasons, so the
    # control and the diagnostics a caller receives can never disagree.
    semantic_failures = _financial_semantics_failures(request, used_inputs)
    semantic_inputs_valid = not semantic_failures
    resolved_currency, currency_inputs_valid = _resolve_public_currency(request, used_inputs)
    currency_inputs_valid = bool(used_inputs) and currency_inputs_valid
    fiscal_year = getattr(getattr(request, "current_year", None), "year", None)
    fiscal_year_valid = isinstance(fiscal_year, int) and 1900 <= fiscal_year <= 2100
    valuation_timestamp = _timestamp(calculation_timestamp)
    valuation_year = valuation_timestamp.year if valuation_timestamp is not None else None
    has_market_method = any(method.get("approach") == "market" for method in methods)
    # Sector evidence belongs only to a market leg. Never attach a convenient
    # resolved benchmark to an asset- or income-only audit.
    if not has_market_method:
        benchmark = None
    benchmark_timestamp = (
        _timestamp(benchmark.get("published_at")) if isinstance(benchmark, dict) else None
    )
    modeled_prior_valid = (
        isinstance(benchmark, dict)
        and benchmark.get("benchmark_kind") == "modeled_prior"
        and benchmark.get("max_public_grade") in {"T2-M", "T3-M"}
        and _decimal(benchmark.get("p25")) is not None
        and _decimal(benchmark.get("median")) is not None
        and _decimal(benchmark.get("p75")) is not None
        and (_decimal(benchmark.get("p25")) or Decimal("0")) > 0
        and _decimal(benchmark.get("p25"))
        <= _decimal(benchmark.get("median"))
        <= _decimal(benchmark.get("p75"))
        and benchmark.get("contract_hash") is not None
    )
    benchmark_distribution_valid = modeled_prior_valid or (
        isinstance(benchmark, dict)
        and _decimal(benchmark.get("p25")) is not None
        and _decimal(benchmark.get("median")) is not None
        and _decimal(benchmark.get("p75")) is not None
        and (_decimal(benchmark.get("p25")) or Decimal("0")) > 0
        and _decimal(benchmark.get("p25"))
        <= _decimal(benchmark.get("median"))
        <= _decimal(benchmark.get("p75"))
        and isinstance(benchmark.get("sample_size"), int)
        and not isinstance(benchmark.get("sample_size"), bool)
        and int(benchmark.get("sample_size") or 0) > 0
        and benchmark.get("dataset_version_id") is not None
        and benchmark_timestamp is not None
        and valuation_timestamp is not None
        and benchmark_timestamp <= valuation_timestamp
    )
    market_arithmetic_valid = not has_market_method or (
        earnings is not None
        and effective_multiple_band is not None
        and _decimal(effective_multiple_band.get("low")) is not None
        and _decimal(effective_multiple_band.get("mid")) is not None
        and _decimal(effective_multiple_band.get("high")) is not None
        and abs(
            earnings * (_decimal(effective_multiple_band.get("low")) or Decimal("0"))
            - ((_decimal(market_leg_band.get("low")) or Decimal("0")) if method_legs else ev_low)
        )
        <= Decimal("1")
        and abs(
            earnings * (_decimal(effective_multiple_band.get("mid")) or Decimal("0"))
            - ((_decimal(market_leg_band.get("mid")) or Decimal("0")) if method_legs else ev_mid)
        )
        <= Decimal("1")
        and abs(
            earnings * (_decimal(effective_multiple_band.get("high")) or Decimal("0"))
            - ((_decimal(market_leg_band.get("high")) or Decimal("0")) if method_legs else ev_high)
        )
        <= Decimal("1")
    )
    explicit_ev_band = (
        _decimal(enterprise_value_low),
        _decimal(enterprise_value_mid),
        _decimal(enterprise_value_high),
    )
    explicit_ev_valid = all(value is not None for value in explicit_ev_band)
    if explicit_ev_valid:
        explicit_low, explicit_mid, explicit_high = explicit_ev_band
        assert explicit_low is not None and explicit_mid is not None and explicit_high is not None
        explicit_ev_valid = (
            explicit_low >= 0
            and explicit_low <= explicit_mid <= explicit_high
            and abs(explicit_low - ev_low) <= Decimal("1")
            and abs(explicit_mid - ev_mid) <= Decimal("1")
            and abs(explicit_high - ev_high) <= Decimal("1")
        )
    weighted_arithmetic_valid = True
    if method_legs:
        total_weight = sum((_decimal(leg.get("weight")) or Decimal("0")) for leg in method_legs)
        weighted_values = []
        for point in ("low", "mid", "high"):
            weighted_values.append(
                sum(
                    (
                        (_decimal(leg.get("weight")) or Decimal("0"))
                        * (
                            _decimal(_mapping(leg.get("enterprise_value")).get(point))
                            or Decimal("0")
                        )
                    )
                    for leg in method_legs
                )
            )
        # When Adaptive excludes an unavailable authorized capability, the
        # synthesis widens the surviving range to disclose the lost method
        # diversity. Method legs remain their exact uninflated values; replay
        # the deterministic range widening before comparing them to the
        # published EV band.
        if uncertainty_factor > 1:
            weighted_values[0] = max(
                Decimal("0"),
                weighted_values[1] - (weighted_values[1] - weighted_values[0]) * uncertainty_factor,
            )
            weighted_values[2] = (
                weighted_values[1] + (weighted_values[2] - weighted_values[1]) * uncertainty_factor
            )
        weighted_arithmetic_valid = (
            abs(total_weight - Decimal("1")) <= Decimal("0.0001")
            and abs(weighted_values[0] - ev_low) <= Decimal("1")
            and abs(weighted_values[1] - ev_mid) <= Decimal("1")
            and abs(weighted_values[2] - ev_high) <= Decimal("1")
        )
    arithmetic_valid = (
        market_arithmetic_valid
        and weighted_arithmetic_valid
        and (explicit_ev_valid or all(value is None for value in explicit_ev_band))
    )
    range_valid = low >= 0 and low <= mid <= high
    historical_lineage_valid = (
        _historical_inputs_are_source_bound(used_inputs, fiscal_year=fiscal_year)
        if isinstance(fiscal_year, int)
        else False
    )
    fiscal_age = (
        valuation_year - fiscal_year if fiscal_year_valid and valuation_year is not None else None
    )
    # Historical timeline checkpoints are current-lens restatements of
    # immutable filed facts. Their age is a disclosure property, not a reason
    # to erase an otherwise source-bound actual from a T2/T3 curve. That rule
    # also applies when the latest available actual is itself historical: the
    # headline is still reproducible from the exact fiscal-year lineage and is
    # explicitly disclosed below as outside the normal recency window.
    historical_point = bool(
        isinstance(request.metadata, Mapping)
        and request.metadata.get("public_valuation_historical_point") is True
    )
    freshness_valid = (
        fiscal_age is not None and fiscal_age >= 0 and (fiscal_age <= 2 or historical_lineage_valid)
    )
    bridge_status = str(bridge.get("status") or "")
    # A modeled Business Types prior is explicitly a low-confidence public
    # benchmark contract. Do not expose the engine's broader headline score
    # (or merely lower it by one level) as if the public evidence upgraded that
    # prior. A missing EV-to-equity bridge still lowers ordinary observed
    # benchmark confidence by one level.
    disclosed_confidence = (
        "low"
        if modeled_prior_valid
        else _confidence_level(
            confidence_level,
            lower=bridge_status not in {"complete", "not_applicable"},
        )
    )
    controls = [
        {
            "key": "entity_identity",
            "status": (
                "passed"
                if _text(getattr(request, "registration_number", None), limit=50)
                else "not_applicable"
            ),
        },
        {"key": "fiscal_year", "status": "passed" if fiscal_year_valid else "failed"},
        {
            "key": "financial_semantics",
            "status": "passed" if semantic_inputs_valid else "failed",
        },
        {
            "key": "benchmark_resolution",
            "status": (
                "passed"
                if has_market_method and benchmark_distribution_valid
                else "failed" if has_market_method else "not_applicable"
            ),
        },
        {
            "key": "currency",
            "status": "passed" if currency_inputs_valid else "failed",
        },
        {
            "key": "arithmetic_reconciliation",
            "status": "passed" if arithmetic_valid else "failed",
        },
        {
            "key": "range_plausibility",
            "status": "passed" if range_valid else "failed",
        },
        {
            "key": "freshness",
            "status": "passed" if freshness_valid else "failed",
        },
    ]
    control_statuses = {control["key"]: control["status"] for control in controls}
    critical_control_keys = {
        "entity_identity",
        "fiscal_year",
        "financial_semantics",
        "currency",
        "arithmetic_reconciliation",
        "range_plausibility",
        "freshness",
    }
    if any(control_statuses.get(key) != "passed" for key in critical_control_keys):
        if failure_reasons is not None:
            failure_reasons.extend(
                sorted(
                    key for key in critical_control_keys if control_statuses.get(key) != "passed"
                )
            )
        if failure_diagnostics is not None:
            failure_diagnostics.extend(semantic_failures)
        return None
    if has_market_method and control_statuses.get("benchmark_resolution") != "passed":
        if failure_reasons is not None:
            failure_reasons.append("benchmark_resolution")
        return None
    if not has_market_method and control_statuses.get("benchmark_resolution") not in {
        "passed",
        "not_applicable",
    }:
        if failure_reasons is not None:
            failure_reasons.append("benchmark_resolution")
        return None

    reasons = ["public_filed_accounts", "private_normalisations_unverified"]
    limitations = [
        "owner_compensation_unverified",
        "one_off_adjustments_unverified",
        "working_capital_unverified",
        "customer_concentration_unverified",
        "contract_quality_unverified",
    ]
    if (
        not historical_point
        and fiscal_age is not None
        and fiscal_age > 2
        and historical_lineage_valid
    ):
        limitations.append("latest_actual_outside_recency_window")
    if metadata.get("public_forecasts_verified") is not True:
        limitations.append("forecasts_unverified")
    if bridge_status != "complete" and bridge_status != "not_applicable":
        reasons.append("net_debt_bridge_assumed")
        limitations.append("net_debt_unverified")
        limitations.append("leases_unverified")
    if isinstance(benchmark, dict) and benchmark.get("match_type") == "borrowed":
        reasons.append("borrowed_benchmark")
    if modeled_prior_valid:
        reasons.append("modeled_benchmark_prior")
        limitations.extend(
            [
                "modeled_benchmark_prior",
                "transaction_sample_unavailable",
                "public_band_minimum_30_percent",
            ]
        )
    modeled_dcf_audit: dict[str, object] | None = None
    if has_dcf_contribution and modeled_dcf is not None:
        dcf_payload = _mapping(dcf_results)
        dcf_assumptions = _mapping(modeled_dcf.get("assumptions"))
        modeled_dcf_audit = {
            "schema_version": modeled_dcf.get("schema_version"),
            "authority": "valuation_iq",
            "policy_version": modeled_dcf.get("policy_version"),
            "resolution_hash": modeled_dcf.get("resolution_hash"),
            "source_metric": modeled_dcf.get("source_metric"),
            "margin_source": modeled_dcf.get("margin_source"),
            "growth_source": modeled_dcf.get("growth_source"),
            "historical_revenue_years_used": modeled_dcf.get("historical_revenue_years_used"),
            "forecast_classification": modeled_dcf.get("forecast_classification"),
            "wacc_policy": dict(_mapping(modeled_dcf.get("wacc_policy"))),
            "assumptions": dict(dcf_assumptions),
            "resolved_wacc": _number(dcf_payload.get("wacc")),
            "wacc_buildup": dict(_mapping(dcf_payload.get("wacc_buildup"))),
            "resolved_terminal_growth": _number(dcf_payload.get("terminal_growth_rate")),
            "projection_years": _number(dcf_payload.get("projection_years")),
            "free_cash_flow_projection": [
                _number(value) for value in (dcf_payload.get("fcf_projections_5y") or [])
            ],
            "market_assumptions": _mapping(dcf_payload.get("market_assumptions")),
        }
        reasons.append("valuation_iq_modeled_dcf")
        limitations.extend(
            [
                "modeled_dcf_assumptions",
                "forecast_assumptions_not_actuals",
            ]
        )

    return {
        "schema_version": (
            "public_valuation_audit.v3" if has_dcf_contribution else "public_valuation_audit.v1"
        ),
        "valuation_date": calculation_timestamp,
        "fiscal_year": int(fiscal_year) if isinstance(fiscal_year, int) else None,
        "currency": resolved_currency,
        "value_basis": value_basis,
        "approach": approach,
        "financial_inputs": inputs,
        "methods": methods,
        "method_legs": method_legs,
        "excluded_methods": excluded_methods,
        "benchmark": benchmark,
        "effective_multiple_band": effective_multiple_band,
        "value_bridge": bridge,
        # Signed replay input for downstream authority verifiers. This is an
        # engine output, not downstream valuation logic: consumers use it only
        # to prove that the published band reconciles with the immutable method
        # legs after Adaptive widens a range for lost method diversity.
        "range_uncertainty_factor": _number(uncertainty_factor),
        "adjustments": adjustments,
        "controls": controls,
        "confidence": {
            "level": disclosed_confidence,
            "reasons": reasons,
        },
        "limitations": sorted(set(limitations)),
        "modeled_dcf": modeled_dcf_audit,
        "public_graph_policy": {
            "max_grade": (
                benchmark.get("max_public_grade")
                if modeled_prior_valid and isinstance(benchmark, dict)
                else None
            ),
            "maturity_basis": "official_fiscal_periods",
        },
    }
