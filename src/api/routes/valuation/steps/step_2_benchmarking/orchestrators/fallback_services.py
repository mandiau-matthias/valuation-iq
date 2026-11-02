"""
Fallback support services for the Step 2 benchmarking orchestrator.

These classes are only used when optional Step 2 support modules cannot be
imported. Keeping them outside the orchestrator preserves the production
contract without letting fallback scaffolding bloat the execution coordinator.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Mapping

from ..constants import Step2MultiplesDefaults


class FallbackRecoveryService:
    """Minimal recovery service used when the primary recovery service is unavailable."""

    def __init__(self, logger) -> None:
        self.logger = logger

    def recover_result_dict(
        self,
        backup: Mapping[str, object] | None,
        error: Exception,
        context: Mapping[str, object] | None = None,
    ) -> dict[str, object]:
        context = context or {}
        context.get("correlation_id")

        ev_ebitda_present = backup.get("ev_ebitda") is not None if backup else False
        ev_revenue_present = backup.get("ev_revenue") is not None if backup else False

        if backup and (ev_ebitda_present or ev_revenue_present):
            ev_ebitda = Decimal(
                str(backup.get("ev_ebitda", Step2MultiplesDefaults.DEFAULT_EV_EBITDA))
            )
            ev_revenue = Decimal(
                str(backup.get("ev_revenue", Step2MultiplesDefaults.DEFAULT_EV_REVENUE))
            )
            pe_ratio = Decimal(
                str(backup.get("pe_ratio", Step2MultiplesDefaults.DEFAULT_PE_RATIO))
            )

            return {
                "primary_method": "EV/EBITDA" if ev_ebitda_present else "EV/Revenue",
                "ev_ebitda_multiple": ev_ebitda,
                "ev_ebitda_p25": (
                    ev_ebitda * Step2MultiplesDefaults.PERCENTILE_P25_MULTIPLIER
                ),
                "ev_ebitda_p50": ev_ebitda,
                "ev_ebitda_p75": (
                    ev_ebitda * Step2MultiplesDefaults.PERCENTILE_P75_MULTIPLIER
                ),
                "ev_revenue_multiple": ev_revenue,
                "ev_revenue_p25": (
                    ev_revenue * Step2MultiplesDefaults.PERCENTILE_P25_MULTIPLIER
                ),
                "ev_revenue_p50": ev_revenue,
                "ev_revenue_p75": (
                    ev_revenue * Step2MultiplesDefaults.PERCENTILE_P75_MULTIPLIER
                ),
                "pe_ratio": pe_ratio,
                "data_source": backup.get("data_source", "fallback_recovery"),
                "warning": f"Recovered from backup: {str(error)}",
                "recovery_applied": True,
            }

        return {
            "primary_method": "EV/EBITDA",
            "ev_ebitda_multiple": Step2MultiplesDefaults.DEFAULT_EV_EBITDA,
            "ev_ebitda_p25": (
                Step2MultiplesDefaults.DEFAULT_EV_EBITDA
                * Step2MultiplesDefaults.PERCENTILE_P25_MULTIPLIER
            ),
            "ev_ebitda_p50": Step2MultiplesDefaults.DEFAULT_EV_EBITDA,
            "ev_ebitda_p75": (
                Step2MultiplesDefaults.DEFAULT_EV_EBITDA
                * Step2MultiplesDefaults.PERCENTILE_P75_MULTIPLIER
            ),
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
            "warning": f"Using defaults: {str(error)}",
            "recovery_applied": True,
        }


class FallbackProvenanceTracker:
    """No-op provenance tracker used when provenance tracking cannot be imported."""

    def __init__(self, correlation_id: str | None) -> None:
        self.correlation_id = correlation_id

    def track_multiples_selection(self, *args, **kwargs) -> None:
        pass

    def track_sme_calibration(self, *args, **kwargs) -> None:
        pass

    def track_primary_method_selection(self, *args, **kwargs) -> None:
        pass

    def track_recovery(self, *args, **kwargs) -> None:
        pass

    def add_to_result_dict(self, result_dict):
        return result_dict


def create_fallback_recovery_service(logger) -> FallbackRecoveryService:
    return FallbackRecoveryService(logger)


def create_fallback_provenance_tracker(
    correlation_id: str | None,
) -> FallbackProvenanceTracker:
    return FallbackProvenanceTracker(correlation_id)
