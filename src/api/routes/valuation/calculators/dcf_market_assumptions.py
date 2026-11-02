"""Market-assumption response shaping for API-layer DCF results."""

from __future__ import annotations

from collections.abc import Callable, Mapping

from src.api.schemas import ValuationRequest


def build_dcf_market_assumptions(
    request: ValuationRequest,
    market_context: object,
    market_context_metadata: Mapping[str, object],
    *,
    logger: object,
    tax_rate_provenance_builder: Callable[[object], dict[str, object] | None],
) -> dict[str, object]:
    """Build market assumptions with the tax basis used in the calculation."""
    market_assumptions = {
        "risk_free_rate": getattr(market_context, "government_bond_yield", None),
        "risk_free_rate_source": market_context_metadata.get("risk_free_rate_source"),
        "risk_free_rate_observed_at": market_context_metadata.get("risk_free_rate_observed_at"),
        "economic_snapshot_id": market_context_metadata.get("economic_snapshot_id"),
        "economic_snapshot_hash": market_context_metadata.get("economic_snapshot_hash"),
        "economic_snapshot_issuer": market_context_metadata.get("economic_snapshot_issuer"),
        "equity_risk_premium": getattr(market_context, "equity_risk_premium", None),
        "equity_risk_premium_source": market_context_metadata.get("equity_risk_premium_source"),
        "gdp_growth_rate": getattr(market_context, "long_term_gdp_growth", None),
        "gdp_growth_source": market_context_metadata.get("gdp_growth_source"),
        "inflation_rate": getattr(market_context, "inflation_rate", None),
        "valuation_date": market_context_metadata.get("valuation_date"),
    }

    # Resolver defects must not silently erase the basis of a priced result.
    tax_provenance = tax_rate_provenance_builder(request)
    if tax_provenance:
        market_assumptions["tax_rate"] = tax_provenance.get("rate")
        market_assumptions["tax_rate_source"] = tax_provenance.get("source")
        market_assumptions["tax_rate_reasons"] = tax_provenance.get("reasons")
        market_assumptions["tax_rate_provenance"] = tax_provenance

    return market_assumptions
