"""Report intelligence context: anomalies, NWC normalization, and market provenance."""

from dataclasses import dataclass
from typing import Protocol, TypeAlias, cast

from src.services.reports.protocol_adapter import (
    _attr,
    _sanitize_market_data_source_display,
    _unwrap,
)
from src.utils.decimal_helpers import safe_float

ReportMap: TypeAlias = dict[str, object]


class TranslationsLike(Protocol):
    anomaly_summary_template: str
    market_provenance_source_managed_dataset: str


@dataclass(frozen=True)
class _AnomalyContext:
    data: ReportMap | None
    has_anomalies: bool
    primary_flag: ReportMap | None
    summary: str | None


@dataclass(frozen=True)
class _NwcContext:
    data: ReportMap | None
    has_normalization: bool


@dataclass(frozen=True)
class _MarketSources:
    risk_free_rate_source: object
    equity_risk_premium_source: object
    gdp_growth_source: object


@dataclass(frozen=True)
class _MarketProvenanceContext:
    provenance: ReportMap | None
    has_provenance: bool


def _mapping_or_none(value: object) -> ReportMap | None:
    unwrapped = _unwrap(value)
    return cast(ReportMap, unwrapped) if isinstance(unwrapped, dict) else None


def _serialize_date(value: object) -> object:
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def _first_present(*values: object) -> object | None:
    for value in values:
        if value is not None:
            return value
    return None


def _market_data_from_transparency(market_data: object) -> ReportMap | None:
    if market_data is None:
        return None
    market_data_dict = _unwrap(market_data)
    if isinstance(market_data_dict, dict):
        return {
            "risk_free_rate": market_data_dict.get("risk_free_rate"),
            "risk_free_rate_source": market_data_dict.get("risk_free_rate_source"),
            "equity_risk_premium": market_data_dict.get("market_risk_premium"),
            "equity_risk_premium_source": market_data_dict.get("market_risk_premium_source"),
            "gdp_growth_rate": market_data_dict.get("gdp_growth_rate"),
            "gdp_growth_source": market_data_dict.get("gdp_growth_source"),
            "valuation_date": _first_present(
                market_data_dict.get("valuation_date"),
                market_data_dict.get("as_of_date"),
                market_data_dict.get("multiples_date"),
                market_data_dict.get("risk_free_rate_date"),
            ),
        }
    return {
        "risk_free_rate": _attr(market_data, "risk_free_rate", None),
        "risk_free_rate_source": _attr(market_data, "risk_free_rate_source", None),
        "equity_risk_premium": _attr(market_data, "market_risk_premium", None),
        "equity_risk_premium_source": _attr(market_data, "market_risk_premium_source", None),
        "gdp_growth_rate": _attr(market_data, "gdp_growth_rate", None),
        "gdp_growth_source": _attr(market_data, "gdp_growth_source", None),
        "valuation_date": _first_present(
            _attr(market_data, "valuation_date", None),
            _attr(market_data, "as_of_date", None),
            _attr(market_data, "multiples_date", None),
            _attr(market_data, "risk_free_rate_date", None),
        ),
    }


def _market_data_from_fallbacks(response: object, request: object) -> ReportMap:
    dcf_market_assumptions = (
        _mapping_or_none(_attr(_attr(response, "dcf_valuation", None), "market_assumptions", None))
        or {}
    )
    economic_context = _mapping_or_none(_attr(request, "economic_context", None)) or {}

    return {
        "risk_free_rate": _first_present(
            dcf_market_assumptions.get("risk_free_rate"),
            economic_context.get("risk_free_rate"),
        ),
        "risk_free_rate_source": _first_present(
            dcf_market_assumptions.get("risk_free_rate_source"),
            economic_context.get("risk_free_rate_source"),
        ),
        "equity_risk_premium": _first_present(
            dcf_market_assumptions.get("equity_risk_premium"),
            economic_context.get("equity_risk_premium"),
            economic_context.get("market_risk_premium"),
            economic_context.get("erp"),
        ),
        "equity_risk_premium_source": _first_present(
            dcf_market_assumptions.get("equity_risk_premium_source"),
            economic_context.get("source"),
        ),
        "gdp_growth_rate": _first_present(
            dcf_market_assumptions.get("gdp_growth_rate"),
            economic_context.get("gdp_growth_rate"),
            economic_context.get("terminal_growth_rate"),
        ),
        "gdp_growth_source": _first_present(
            dcf_market_assumptions.get("gdp_growth_source"),
            economic_context.get("source"),
        ),
        "valuation_date": dcf_market_assumptions.get("valuation_date"),
        "risk_free_rate_observed_at": dcf_market_assumptions.get("risk_free_rate_observed_at"),
    }


def _build_anomaly_context(
    response: object,
    request: object,
    t: TranslationsLike,
) -> _AnomalyContext:
    anomaly_data = _mapping_or_none(
        _attr(response, "trial_balance_anomalies", None)
        or _attr(request, "trial_balance_anomalies", None)
    )
    raw_anomaly_flags = anomaly_data.get("anomaly_flags", []) if anomaly_data else []
    anomaly_flags = raw_anomaly_flags if isinstance(raw_anomaly_flags, list) else []
    primary_flag = _mapping_or_none(anomaly_flags[0]) if anomaly_flags else None
    has_trial_balance_anomalies = bool(
        anomaly_data
        and (
            anomaly_data.get("has_anomalies")
            or anomaly_data.get("anomaly_detected")
            or bool(anomaly_flags)
        )
    )

    anomaly_summary = None
    if primary_flag:
        account = primary_flag.get("account_label") or primary_flag.get("account")
        year = primary_flag.get("year")
        direction = primary_flag.get("direction")
        direction_clause = f" ({direction})" if direction else ""
        anomaly_summary = t.anomaly_summary_template.format(
            account=account,
            year=year,
            direction_clause=direction_clause,
        )
    return _AnomalyContext(
        data=anomaly_data,
        has_anomalies=has_trial_balance_anomalies,
        primary_flag=primary_flag,
        summary=anomaly_summary,
    )


def _build_nwc_context(response: object, request: object) -> _NwcContext:
    nwc_data = _mapping_or_none(
        _attr(response, "nwc_normalization", None) or _attr(request, "nwc_normalization", None)
    )
    has_nwc_normalization = bool(
        nwc_data and ("surplus_deficit" in nwc_data or "error" in nwc_data)
    )
    return _NwcContext(data=nwc_data, has_normalization=has_nwc_normalization)


def _market_fields(response: object, request: object) -> ReportMap:
    transparency = _attr(response, "transparency", None)
    market_data = _attr(transparency, "market_data", None)
    market_fields = _market_data_from_transparency(market_data)
    if market_fields is None:
        market_fields = _market_data_from_fallbacks(response, request)
    return market_fields


def _market_sources(market_fields: ReportMap, t: TranslationsLike) -> _MarketSources:
    managed_source = t.market_provenance_source_managed_dataset
    return _MarketSources(
        risk_free_rate_source=_sanitize_market_data_source_display(
            market_fields.get("risk_free_rate_source"),
            managed_source,
        ),
        equity_risk_premium_source=_sanitize_market_data_source_display(
            market_fields.get("equity_risk_premium_source"),
            managed_source,
        ),
        gdp_growth_source=_sanitize_market_data_source_display(
            market_fields.get("gdp_growth_source"),
            managed_source,
        ),
    )


def _has_market_provenance(
    *,
    risk_free_rate: object,
    equity_risk_premium: object,
    gdp_growth_rate: object,
    sources: _MarketSources,
) -> bool:
    unresolved_sources = {"unresolved", "", None}
    return bool(
        (risk_free_rate is not None and sources.risk_free_rate_source not in unresolved_sources)
        or (
            equity_risk_premium is not None
            and sources.equity_risk_premium_source not in unresolved_sources
        )
        or gdp_growth_rate is not None
    )


def _build_market_provenance_context(
    response: object,
    request: object,
    t: TranslationsLike,
) -> _MarketProvenanceContext:
    market_fields = _market_fields(response, request)
    sources = _market_sources(market_fields, t)
    risk_free_rate = market_fields.get("risk_free_rate")
    equity_risk_premium = market_fields.get("equity_risk_premium")
    gdp_growth_rate = market_fields.get("gdp_growth_rate")
    has_market_data_provenance = _has_market_provenance(
        risk_free_rate=risk_free_rate,
        equity_risk_premium=equity_risk_premium,
        gdp_growth_rate=gdp_growth_rate,
        sources=sources,
    )
    valuation_date = _first_present(
        market_fields.get("risk_free_rate_observed_at"),
        _attr(response, "valuation_date", None),
        _attr(request, "valuation_date", None),
        market_fields.get("valuation_date"),
    )
    economic_context = _mapping_or_none(_attr(request, "economic_context", None)) or {}
    market_data_provenance = (
        {
            "risk_free_rate": safe_float(risk_free_rate),
            "risk_free_rate_source": sources.risk_free_rate_source,
            "risk_free_rate_is_override": (
                str(sources.risk_free_rate_source).lower()
                in {"request_override", "economic_context_override"}
                or bool(economic_context.get("risk_free_rate_is_override"))
            ),
            "equity_risk_premium": safe_float(equity_risk_premium),
            "equity_risk_premium_source": sources.equity_risk_premium_source,
            "gdp_growth_rate": safe_float(gdp_growth_rate),
            "gdp_growth_source": sources.gdp_growth_source,
            "valuation_date": _serialize_date(valuation_date),
        }
        if has_market_data_provenance
        else None
    )
    return _MarketProvenanceContext(
        provenance=market_data_provenance,
        has_provenance=has_market_data_provenance,
    )


def build_report_intelligence_context(
    *,
    response: object,
    request: object,
    t: TranslationsLike,
) -> ReportMap:
    """Build report-facing anomaly, NWC, and market-provenance context."""
    anomaly = _build_anomaly_context(response, request, t)
    nwc = _build_nwc_context(response, request)
    market = _build_market_provenance_context(response, request, t)

    return {
        "trial_balance_anomalies": anomaly.data,
        "has_trial_balance_anomalies": anomaly.has_anomalies,
        "trial_balance_anomaly_primary_flag": anomaly.primary_flag,
        "trial_balance_anomaly_summary": anomaly.summary,
        "nwc_normalization": nwc.data,
        "has_nwc_normalization": nwc.has_normalization,
        "market_data_provenance": market.provenance,
        "has_market_data_provenance": market.has_provenance,
    }
