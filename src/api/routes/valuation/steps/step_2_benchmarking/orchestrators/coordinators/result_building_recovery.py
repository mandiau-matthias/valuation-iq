"""Fallback recovery helpers for Step 2 result building."""

from decimal import Decimal
from typing import Mapping

from src.api.routes.valuation.benchmark_contract_utils import is_resolved_benchmark_contract

from ...constants import Step2MultiplesDefaults


class ResultBuildingFallbackRecoveryService:
    """Recovery service used when the primary Step 2 recovery service is unavailable."""

    def __init__(self, logger) -> None:
        self.logger = logger

    def recover_result_dict(
        self,
        backup: Mapping[str, object] | None = None,
        error: Exception | None = None,
        context: Mapping[str, object] | None = None,
    ) -> dict[str, object]:
        """Recover result dictionary from backup or explicit fallback defaults."""
        context = context or {}
        requires_trusted_benchmark = context.get("requires_trusted_benchmark") is True

        ev_ebitda_present = backup.get("ev_ebitda") is not None if backup else False
        ev_revenue_present = backup.get("ev_revenue") is not None if backup else False

        if backup and (ev_ebitda_present or ev_revenue_present):
            contract = backup.get("benchmark_contract") or backup.get("benchmark_provenance")
            if requires_trusted_benchmark and not is_resolved_benchmark_contract(contract):
                raise ValueError(
                    "Refusing Step 2 backup recovery without a resolved benchmark contract"
                )
            return _recover_from_backup(
                backup=backup,
                error=error,
                ev_ebitda_present=ev_ebitda_present,
                ev_revenue_present=ev_revenue_present,
                requires_trusted_benchmark=requires_trusted_benchmark,
            )

        if requires_trusted_benchmark:
            raise ValueError(
                "Refusing Step 2 default recovery without explicit allow_untrusted_multiples_fallback=true"
            )

        return _recover_from_defaults(error)


def create_result_building_fallback_recovery_service(
    logger,
) -> ResultBuildingFallbackRecoveryService:
    return ResultBuildingFallbackRecoveryService(logger)


def create_fallback_result_from_multiples(
    multiples_data: object,
    error: Exception | None,
    context: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """Create a minimal result from multiples data when recovery service is unavailable."""
    context = context or {}
    if context.get("requires_trusted_benchmark") is True:
        raise ValueError(
            "Refusing local Step 2 fallback result without explicit allow_untrusted_multiples_fallback=true"
        )

    if not isinstance(multiples_data, dict):
        multiples_data = {}

    ev_ebitda = Decimal(
        str(multiples_data.get("ev_ebitda", Step2MultiplesDefaults.DEFAULT_EV_EBITDA))
    )
    ev_revenue = Decimal(
        str(multiples_data.get("ev_revenue", Step2MultiplesDefaults.DEFAULT_EV_REVENUE))
    )
    pe_ratio = Decimal(str(multiples_data.get("pe_ratio", Step2MultiplesDefaults.DEFAULT_PE_RATIO)))

    primary = "EV/EBITDA" if multiples_data.get("ev_ebitda") is not None else "EV/Revenue"
    ebitda_p25 = ev_ebitda * Step2MultiplesDefaults.PERCENTILE_P25_MULTIPLIER
    ebitda_p75 = ev_ebitda * Step2MultiplesDefaults.PERCENTILE_P75_MULTIPLIER
    revenue_p25 = ev_revenue * Step2MultiplesDefaults.PERCENTILE_P25_MULTIPLIER
    revenue_p75 = ev_revenue * Step2MultiplesDefaults.PERCENTILE_P75_MULTIPLIER

    return {
        "primary_method": primary,
        "ev_ebitda_multiple": ev_ebitda,
        "ev_ebitda_p25": ebitda_p25,
        "ev_ebitda_p50": ev_ebitda,
        "ev_ebitda_p75": ebitda_p75,
        "ev_revenue_multiple": ev_revenue,
        "ev_revenue_p25": revenue_p25,
        "ev_revenue_p50": ev_revenue,
        "ev_revenue_p75": revenue_p75,
        "pe_ratio": pe_ratio,
        "data_source": multiples_data.get("data_source", "fallback_recovery"),
        "warning": f"Recovered from backup: {str(error) if error else 'unknown error'}",
        "recovery_applied": True,
        "multiples_p25": revenue_p25 if primary == "EV/Revenue" else ebitda_p25,
        "multiples_p50": ev_revenue if primary == "EV/Revenue" else ev_ebitda,
        "multiples_p75": revenue_p75 if primary == "EV/Revenue" else ebitda_p75,
    }


def _recover_from_backup(
    *,
    backup: Mapping[str, object],
    error: Exception | None,
    ev_ebitda_present: bool,
    ev_revenue_present: bool,
    requires_trusted_benchmark: bool,
) -> dict[str, object]:
    ev_ebitda = _backup_decimal(
        backup, "ev_ebitda", Step2MultiplesDefaults.DEFAULT_EV_EBITDA, requires_trusted_benchmark
    )
    ev_revenue = _backup_decimal(
        backup, "ev_revenue", Step2MultiplesDefaults.DEFAULT_EV_REVENUE, requires_trusted_benchmark
    )
    pe_ratio = _backup_decimal(
        backup, "pe_ratio", Step2MultiplesDefaults.DEFAULT_PE_RATIO, requires_trusted_benchmark
    )

    primary = "EV/EBITDA" if ev_ebitda_present else "EV/Revenue"
    if primary == "EV/Revenue" and ev_revenue is None:
        raise ValueError("Refusing Step 2 recovery: EV/Revenue benchmark is missing")
    if primary != "EV/Revenue" and ev_ebitda is None:
        raise ValueError("Refusing Step 2 recovery: EV/EBITDA benchmark is missing")

    ebitda_p25 = _explicit_or_scaled(
        backup.get("ev_ebitda_p25"), ev_ebitda, Step2MultiplesDefaults.PERCENTILE_P25_MULTIPLIER
    )
    ebitda_p75 = _explicit_or_scaled(
        backup.get("ev_ebitda_p75"), ev_ebitda, Step2MultiplesDefaults.PERCENTILE_P75_MULTIPLIER
    )
    revenue_p25 = _explicit_or_scaled(
        backup.get("ev_revenue_p25"), ev_revenue, Step2MultiplesDefaults.PERCENTILE_P25_MULTIPLIER
    )
    revenue_p75 = _explicit_or_scaled(
        backup.get("ev_revenue_p75"), ev_revenue, Step2MultiplesDefaults.PERCENTILE_P75_MULTIPLIER
    )
    ebitda_p50 = backup.get("ev_ebitda_p50") if backup.get("ev_ebitda_p50") is not None else ev_ebitda
    revenue_p50 = (
        backup.get("ev_revenue_p50") if backup.get("ev_revenue_p50") is not None else ev_revenue
    )

    return {
        "primary_method": primary,
        "ev_ebitda_multiple": ev_ebitda,
        "ev_ebitda_p25": ebitda_p25,
        "ev_ebitda_p50": ebitda_p50,
        "ev_ebitda_p75": ebitda_p75,
        "ev_revenue_multiple": ev_revenue,
        "ev_revenue_p25": revenue_p25,
        "ev_revenue_p50": revenue_p50,
        "ev_revenue_p75": revenue_p75,
        "pe_ratio": pe_ratio,
        "data_source": backup.get("data_source", "fallback_recovery"),
        "warning": f"Recovered from backup: {str(error) if error else 'unknown error'}",
        "recovery_applied": True,
        "multiples_p25": revenue_p25 if primary == "EV/Revenue" else ebitda_p25,
        "multiples_p50": ev_revenue if primary == "EV/Revenue" else ev_ebitda,
        "multiples_p75": revenue_p75 if primary == "EV/Revenue" else ebitda_p75,
    }


def _recover_from_defaults(error: Exception | None) -> dict[str, object]:
    ebitda_p25 = (
        Step2MultiplesDefaults.DEFAULT_EV_EBITDA
        * Step2MultiplesDefaults.PERCENTILE_P25_MULTIPLIER
    )
    ebitda_p75 = (
        Step2MultiplesDefaults.DEFAULT_EV_EBITDA
        * Step2MultiplesDefaults.PERCENTILE_P75_MULTIPLIER
    )
    return {
        "primary_method": "EV/EBITDA",
        "ev_ebitda_multiple": Step2MultiplesDefaults.DEFAULT_EV_EBITDA,
        "ev_ebitda_p25": ebitda_p25,
        "ev_ebitda_p50": Step2MultiplesDefaults.DEFAULT_EV_EBITDA,
        "ev_ebitda_p75": ebitda_p75,
        "ev_revenue_multiple": Step2MultiplesDefaults.DEFAULT_EV_REVENUE,
        "ev_revenue_p25": (
            Step2MultiplesDefaults.DEFAULT_EV_REVENUE
            * Step2MultiplesDefaults.PERCENTILE_P25_MULTIPLIER
        ),
        "ev_revenue_p50": Step2MultiplesDefaults.DEFAULT_EV_REVENUE,
        "ev_revenue_p75": (
            Step2MultiplesDefaults.DEFAULT_EV_REVENUE
            * Step2MultiplesDefaults.PERCENTILE_P75_MULTIPLIER
        ),
        "pe_ratio": Step2MultiplesDefaults.DEFAULT_PE_RATIO,
        "data_source": "fallback_defaults",
        "warning": f"Using defaults: {str(error) if error else 'unknown error'}",
        "recovery_applied": True,
        "multiples_p25": ebitda_p25,
        "multiples_p50": Step2MultiplesDefaults.DEFAULT_EV_EBITDA,
        "multiples_p75": ebitda_p75,
    }


def _backup_decimal(
    backup: Mapping[str, object],
    key: str,
    default: Decimal,
    requires_trusted_benchmark: bool,
) -> Decimal | None:
    value = backup.get(key)
    if value is None:
        return None if requires_trusted_benchmark else default
    return Decimal(str(value))


def _explicit_or_scaled(raw_value: object, base: Decimal | None, multiplier: Decimal) -> object:
    if raw_value is not None:
        return raw_value
    if base is None:
        return None
    return base * multiplier
