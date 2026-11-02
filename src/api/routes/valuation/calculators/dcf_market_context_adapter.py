"""Build DCF market context and provenance from request-level assumptions."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Callable, Optional, Protocol

from src.config.economic_snapshots import (
    ECONOMIC_SNAPSHOT_SCHEMA_VERSION,
    verify_economic_snapshot_hash,
)
from src.domain.models import MarketContext
from src.utils.decimal_helpers import to_decimal

CountryDefaultsResolver = Callable[[Optional[str]], dict[str, object]]
CountryNormalizer = Callable[[object], str]
RiskFreeRateResolver = Callable[[str], tuple[Optional[Decimal], str]]
EquityRiskPremiumResolver = Callable[..., tuple[Decimal, str]]


class MarketContextLogger(Protocol):
    """Logger surface used by the market-context adapter."""

    def info(self, message: str, *args: object, **kwargs: object) -> None:
        """Log informational market-context events."""

    def error(self, message: str, *args: object, **kwargs: object) -> None:
        """Log market-context failures."""


def _is_verified_economic_snapshot(
    economic_context: dict[str, object],
    *,
    country_code: str,
    direct_sector_wacc: bool = False,
) -> bool:
    """Recognize an intact governed snapshot, never a hash-shaped claim.

    This adapter is also used by legacy request paths, so the presence of a
    risk-free rate alone is deliberately insufficient.  A complete canonical
    commitment must verify and bind the same jurisdiction before its values
    outrank a live/static resolver.
    """

    identity_fields = ("schema_version", "snapshot_id", "snapshot_hash", "snapshot_issuer")
    if not any(economic_context.get(field) for field in identity_fields):
        return False

    required_identity = (
        "snapshot_id",
        "snapshot_hash",
        "snapshot_issuer",
        "risk_free_rate_observed_at",
        "equity_risk_premium_observed_at",
        "growth_rates_observed_at",
        "source_references",
    )
    required_values = (
        "risk_free_rate",
        "gdp_growth_rate",
        "terminal_growth_rate",
        "inflation_rate",
    )
    has_equity_risk_premium = any(
        economic_context.get(field) is not None
        for field in ("equity_risk_premium", "market_risk_premium", "erp")
    )
    if not (
        economic_context.get("schema_version") == ECONOMIC_SNAPSHOT_SCHEMA_VERSION
        and str(economic_context.get("country_code") or "").strip().upper() == country_code
        and str(economic_context.get("source") or "").strip().lower() != "static_defaults"
        and all(economic_context.get(field) for field in required_identity)
        and all(economic_context.get(field) is not None for field in required_values)
        # An all-in direct-sector WACC does not price CAPM components again.
        # Its signed evidence contract may therefore bind a deliberately null
        # ERP while this economic snapshot governs only growth/inflation and
        # records the non-priced engine placeholders.  Every component-build
        # path still requires an explicit ERP.
        and (has_equity_risk_premium or direct_sector_wacc)
    ):
        raise ValueError(
            "economic snapshot claim is incomplete, ungoverned, or bound to another country"
        )
    verify_economic_snapshot_hash(economic_context)
    return True


def build_dcf_market_context(
    *,
    request: object,
    logger: MarketContextLogger,
    normalize_country_code: CountryNormalizer,
    resolve_country_defaults: CountryDefaultsResolver,
    get_risk_free_rate_fn: RiskFreeRateResolver,
    resolve_equity_risk_premium_fn: EquityRiskPremiumResolver,
) -> tuple[MarketContext, dict[str, object]]:
    """Create a MarketContext plus immutable-per-call provenance metadata."""
    try:
        country_code = normalize_country_code(getattr(request, "country_code", None))
        logger.info("🌍 Creating MarketContext", extra={"country": country_code})

        country_defaults = resolve_country_defaults(country_code)

        economic_context = getattr(request, "economic_context", None) or {}
        economic_context_risk_free_rate = (
            to_decimal(economic_context["risk_free_rate"])
            if economic_context.get("risk_free_rate") is not None
            else None
        )
        economic_context_is_override = economic_context.get("risk_free_rate_is_override", True)
        raw_wacc_contract = getattr(request, "wacc_evidence_contract", None)
        if hasattr(raw_wacc_contract, "model_dump"):
            raw_wacc_contract = raw_wacc_contract.model_dump(mode="python")
        direct_sector_wacc = bool(
            isinstance(raw_wacc_contract, dict)
            and raw_wacc_contract.get("mode") == "direct_sector_wacc"
        )
        public_modeled_dcf_authorized = (
            getattr(request, "public_modeled_dcf_authorized", False) is True
        )
        has_verified_snapshot = _is_verified_economic_snapshot(
            economic_context,
            country_code=country_code,
            direct_sector_wacc=direct_sector_wacc,
        )

        resolved_risk_free_rate, risk_free_rate_source = get_risk_free_rate_fn(country_code)
        explicit_bond_yield = getattr(request, "government_bond_yield", None)
        if has_verified_snapshot:
            if economic_context_risk_free_rate is None:
                raise ValueError("verified economic snapshot is missing risk_free_rate")
            if explicit_bond_yield is not None and to_decimal(explicit_bond_yield) != (
                economic_context_risk_free_rate
            ):
                raise ValueError(
                    "government_bond_yield conflicts with the verified economic snapshot"
                )
            bond_yield = economic_context_risk_free_rate
        elif explicit_bond_yield is not None:
            bond_yield = explicit_bond_yield
        elif economic_context_risk_free_rate is not None and economic_context_is_override:
            bond_yield = economic_context_risk_free_rate
        elif resolved_risk_free_rate is not None:
            bond_yield = resolved_risk_free_rate
        elif economic_context_risk_free_rate is not None:
            bond_yield = economic_context_risk_free_rate
        else:
            bond_yield = country_defaults["bond_yield"]

        explicit_gdp_growth = getattr(request, "long_term_gdp_growth", None)
        economic_gdp_growth = (
            economic_context.get("gdp_growth_rate")
            if economic_context.get("gdp_growth_rate") is not None
            else economic_context.get("terminal_growth_rate")
        )
        gdp_growth = (
            explicit_gdp_growth
            if explicit_gdp_growth is not None
            else (
                to_decimal(economic_gdp_growth)
                if economic_gdp_growth is not None
                else country_defaults["gdp_growth"]
            )
        )
        inflation = (
            to_decimal(economic_context["inflation_rate"])
            if economic_context.get("inflation_rate") is not None
            else country_defaults["inflation"]
        )
        economic_context_erp = next(
            (
                to_decimal(economic_context[field])
                for field in ("equity_risk_premium", "market_risk_premium", "erp")
                if economic_context.get(field) is not None
            ),
            None,
        )
        explicit_erp = getattr(request, "equity_risk_premium", None)
        if has_verified_snapshot:
            if economic_context_erp is None:
                if not direct_sector_wacc:
                    raise ValueError("verified economic snapshot is missing equity_risk_premium")
                # The core DCF engine still needs a structurally complete market
                # context before the governed all-in WACC override is applied.
                # Resolve a non-priced placeholder and label it explicitly; it
                # must never be presented as a component of the applied rate.
                equity_risk_premium, _ = resolve_equity_risk_premium_fn(
                    country_code=country_code,
                    explicit_override=None,
                    economic_context={},
                )
                erp_source = "not_priced_direct_sector_wacc_mode"
            elif explicit_erp is not None and to_decimal(explicit_erp) != economic_context_erp:
                raise ValueError(
                    "equity_risk_premium conflicts with the verified economic snapshot"
                )
            else:
                equity_risk_premium = economic_context_erp
                erp_source = str(economic_context.get("source") or "verified_economic_snapshot")
        else:
            equity_risk_premium, erp_source = resolve_equity_risk_premium_fn(
                country_code=country_code,
                explicit_override=explicit_erp,
                economic_context=economic_context,
            )
            if public_modeled_dcf_authorized:
                erp_source = str(
                    economic_context.get("source") or "valuation_iq_public_modeled_defaults.v1"
                )

        market_context = MarketContext(
            country_code=country_code,
            government_bond_yield=bond_yield,
            long_term_gdp_growth=gdp_growth,
            inflation_rate=inflation,
            equity_risk_premium=equity_risk_premium,
            valuation_date=date.today(),
        )
        if has_verified_snapshot:
            risk_free_metadata_source = str(
                economic_context.get("risk_free_rate_source")
                or economic_context.get("source")
                or "verified_economic_snapshot"
            )
        elif explicit_bond_yield is not None:
            risk_free_metadata_source = (
                str(
                    economic_context.get("risk_free_rate_source")
                    or economic_context.get("source")
                    or "valuation_iq_public_modeled_defaults.v1"
                )
                if public_modeled_dcf_authorized
                else "request_override"
            )
        elif economic_context_risk_free_rate is not None and economic_context_is_override:
            risk_free_metadata_source = "economic_context_override"
        elif resolved_risk_free_rate is not None:
            risk_free_metadata_source = risk_free_rate_source
        elif economic_context_risk_free_rate is not None:
            risk_free_metadata_source = "economic_context"
        else:
            risk_free_metadata_source = "country_defaults"
        market_context_metadata: dict[str, object] = {
            "risk_free_rate_source": risk_free_metadata_source,
            "risk_free_rate_observed_at": (
                economic_context.get("risk_free_rate_observed_at")
                if has_verified_snapshot
                else None
            ),
            "economic_snapshot_id": (
                economic_context.get("snapshot_id") if has_verified_snapshot else None
            ),
            "economic_snapshot_hash": (
                economic_context.get("snapshot_hash") if has_verified_snapshot else None
            ),
            "economic_snapshot_issuer": (
                economic_context.get("snapshot_issuer") if has_verified_snapshot else None
            ),
            "equity_risk_premium_source": erp_source,
            "gdp_growth_source": (
                str(economic_context.get("source") or "valuation_iq_public_modeled_defaults.v1")
                if explicit_gdp_growth is not None and public_modeled_dcf_authorized
                else (
                    "request_override"
                    if explicit_gdp_growth is not None
                    else (
                        "economic_context"
                        if economic_gdp_growth is not None
                        else "country_defaults"
                    )
                )
            ),
            # Both names are projected because downstream calculation and
            # report contracts historically used different canonical labels.
            # They must remain the same governed Decimal, never an implicit 0.
            "risk_free_rate": bond_yield,
            "government_bond_yield": bond_yield,
            "equity_risk_premium": equity_risk_premium,
            "gdp_growth_rate": gdp_growth,
            "inflation_rate": inflation,
            "valuation_date": market_context.valuation_date.isoformat(),
        }

        logger.info(
            "✅ MarketContext created",
            extra={
                "country": getattr(request, "country_code", None),
                "normalized_country": country_code,
                "bond_yield": f"{bond_yield*100:.2f}%",
                "risk_free_rate_source": risk_free_metadata_source,
                "gdp_growth": f"{gdp_growth*100:.2f}%",
                "equity_risk_premium": f"{equity_risk_premium*100:.2f}%",
                "erp_source": erp_source,
            },
        )

        return market_context, market_context_metadata

    except Exception as exc:
        logger.error(
            "❌ Failed to create MarketContext",
            extra={"error": str(exc), "country": getattr(request, "country_code", None)},
            exc_info=True,
        )
        raise
