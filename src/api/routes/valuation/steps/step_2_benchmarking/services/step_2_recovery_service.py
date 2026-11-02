"""
Step 2 Recovery Service

Centralized recovery logic for Step 2 multiples calculation.
Single source of truth for error recovery strategies.
"""

from decimal import Decimal
from typing import Any, Dict, Optional

from src.api.routes.valuation.benchmark_contract_utils import extract_resolved_benchmark_contract
from src.utils.decimal_helpers import to_decimal
from src.utils.valuation_logger import ValuationLogger

from ..constants import Step2MultiplesDefaults


class Step2RecoveryService:
    """Centralized recovery service for Step 2."""

    def __init__(self, logger: ValuationLogger):
        """
        Initialize the recovery service.

        Args:
            logger: Logger instance for structured logging
        """
        self.logger = logger

    def recover_result_dict(
        self,
        backup: Optional[Dict[str, Any]],
        error: Exception,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Recover result dictionary from backup or defaults.

        Args:
            backup: Backup multiples data (from database lookup)
            error: The exception that triggered recovery
            context: Additional context (correlation_id, etc.)

        Returns:
            Recovered result dictionary with recovery_applied=True

        Raises:
            StepExecutionError: If recovery fails completely
        """
        context = context or {}
        correlation_id = context.get("correlation_id")
        requires_trusted_benchmark = (
            context.get("requires_trusted_benchmark") is True
            or bool(context.get("business_type_id"))
            and context.get("allow_untrusted_multiples_fallback") is not True
        )

        # Try to recover from backup first
        if backup and self._is_valid_backup(backup):
            if requires_trusted_benchmark and not self._backup_has_resolved_contract(backup):
                raise ValueError("Refusing Step 2 recovery without a resolved benchmark contract")
            self.logger.warning(
                "Step 2: Recovering from backup multiples data",
                extra={
                    "step_number": 2,
                    "correlation_id": correlation_id,
                    "backup_source": backup.get("data_source"),
                    "error_type": type(error).__name__,
                    "error_message": str(error),
                    "recovery_method": "backup",
                    # BANK-GRADE: Check for None explicitly, not truthiness (Decimal("0") is valid)
                    "backup_has_ev_ebitda": backup.get("ev_ebitda") is not None,
                    "backup_has_ev_revenue": backup.get("ev_revenue") is not None,
                },
            )
            return self._recover_from_backup(backup, error, context)

        if requires_trusted_benchmark:
            raise ValueError(
                "Refusing Step 2 default recovery for concrete business_type_id without "
                "explicit allow_untrusted_multiples_fallback=true"
            )

        # Fall back to defaults
        self.logger.warning(
            "Step 2: No valid backup available, using defaults",
            extra={
                "step_number": 2,
                "correlation_id": correlation_id,
                "error_type": type(error).__name__,
                "error_message": str(error),
                "recovery_method": "defaults",
                "backup_available": backup is not None,
                "backup_is_dict": isinstance(backup, dict) if backup else False,
                "backup_keys": list(backup.keys()) if isinstance(backup, dict) else [],
            },
        )
        return self._recover_from_defaults(error, context)

    def _is_valid_backup(self, backup: Dict[str, Any]) -> bool:
        """
        Check if backup data is valid for recovery.

        Args:
            backup: Backup data dictionary

        Returns:
            True if backup has valid multiples data
        """
        if not isinstance(backup, dict) or len(backup) == 0:
            return False

        # BANK-GRADE: Check for None explicitly, not truthiness (Decimal("0") is valid)
        # Zero is a valid (though unusual) multiple value and should not be rejected
        has_ev_ebitda = backup.get("ev_ebitda") is not None
        has_ev_revenue = backup.get("ev_revenue") is not None

        return has_ev_ebitda or has_ev_revenue

    def _recover_from_backup(
        self, backup: Dict[str, Any], error: Exception, context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Build result dict from backup data.

        Args:
            backup: Backup multiples data
            error: The exception that triggered recovery
            context: Additional context

        Returns:
            Recovered result dictionary
        """
        correlation_id = context.get("correlation_id")
        requires_trusted_benchmark = context.get("requires_trusted_benchmark") is True

        # Extract multiples with proper type conversion
        ev_ebitda = self._safe_extract_multiple(
            backup,
            "ev_ebitda",
            None if requires_trusted_benchmark else Step2MultiplesDefaults.DEFAULT_EV_EBITDA,
        )
        ev_revenue = self._safe_extract_multiple(
            backup,
            "ev_revenue",
            None if requires_trusted_benchmark else Step2MultiplesDefaults.DEFAULT_EV_REVENUE,
        )
        pe_ratio = self._safe_extract_multiple(
            backup,
            "pe_ratio",
            None if requires_trusted_benchmark else Step2MultiplesDefaults.DEFAULT_PE_RATIO,
        )

        # Preserve the canonical method when present. If backup data has both
        # multiple families but no explicit method, default to EBITDA so
        # profitable companies do not drift onto a revenue path during recovery.
        ev_revenue_present = backup.get("ev_revenue") is not None
        ev_ebitda_present = backup.get("ev_ebitda") is not None
        primary_method = self._resolve_primary_method(
            backup=backup,
            context=context,
            ev_ebitda_present=ev_ebitda_present,
            ev_revenue_present=ev_revenue_present,
        )
        if primary_method == "EV/Revenue" and ev_revenue is None:
            raise ValueError("Refusing Step 2 recovery: EV/Revenue benchmark is missing")
        if primary_method != "EV/Revenue" and ev_ebitda is None:
            raise ValueError("Refusing Step 2 recovery: EV/EBITDA benchmark is missing")

        # Build result dict
        # BANK-GRADE: Use explicit None checking for percentiles to handle Decimal("0") correctly
        # Decimal("0") is falsy but valid - must check for None explicitly, not truthiness
        ev_ebitda_p25_backup = backup.get("ev_ebitda_p25")
        ev_ebitda_p50_backup = backup.get("ev_ebitda_p50")
        ev_ebitda_p75_backup = backup.get("ev_ebitda_p75")
        ev_revenue_p25_backup = backup.get("ev_revenue_p25")
        ev_revenue_p50_backup = backup.get("ev_revenue_p50")
        ev_revenue_p75_backup = backup.get("ev_revenue_p75")

        resolved_ebitda_p25 = (
            ev_ebitda_p25_backup
            if ev_ebitda_p25_backup is not None
            else (
                ev_ebitda * Step2MultiplesDefaults.PERCENTILE_P25_MULTIPLIER
                if ev_ebitda is not None
                else None
            )
        )
        resolved_ebitda_p75 = (
            ev_ebitda_p75_backup
            if ev_ebitda_p75_backup is not None
            else (
                ev_ebitda * Step2MultiplesDefaults.PERCENTILE_P75_MULTIPLIER
                if ev_ebitda is not None
                else None
            )
        )
        resolved_revenue_p25 = (
            ev_revenue_p25_backup
            if ev_revenue_p25_backup is not None
            else (
                ev_revenue * Step2MultiplesDefaults.PERCENTILE_P25_MULTIPLIER
                if ev_revenue is not None
                else None
            )
        )
        resolved_revenue_p75 = (
            ev_revenue_p75_backup
            if ev_revenue_p75_backup is not None
            else (
                ev_revenue * Step2MultiplesDefaults.PERCENTILE_P75_MULTIPLIER
                if ev_revenue is not None
                else None
            )
        )

        result = {
            "primary_method": primary_method,
            "ev_ebitda_multiple": ev_ebitda,
            "ev_ebitda_p25": resolved_ebitda_p25,
            "ev_ebitda_p50": (
                ev_ebitda_p50_backup if ev_ebitda_p50_backup is not None else ev_ebitda
            ),
            "ev_ebitda_p75": resolved_ebitda_p75,
            "ev_revenue_multiple": ev_revenue,
            "ev_revenue_p25": resolved_revenue_p25,
            "ev_revenue_p50": (
                ev_revenue_p50_backup if ev_revenue_p50_backup is not None else ev_revenue
            ),
            "ev_revenue_p75": resolved_revenue_p75,
            "pe_ratio": pe_ratio,
            "data_source": backup.get("data_source", "fallback_recovery"),
            "data_source_details": backup.get("data_source_details", {}),
            "source_quality": backup.get("source_quality", "degraded"),
            "benchmark_contract": backup.get("benchmark_contract"),
            "benchmark_provenance": backup.get("benchmark_provenance")
            or backup.get("benchmark_contract"),
            "benchmark_id": backup.get("benchmark_id"),
            "dataset_version_id": backup.get("dataset_version_id"),
            "warning": f"Result building failed but recovered from backup: {str(error)}",
            "recovery_applied": True,
            "multiples_p25": (
                resolved_revenue_p25 if primary_method == "EV/Revenue" else resolved_ebitda_p25
            ),
            "multiples_p50": ev_revenue if primary_method == "EV/Revenue" else ev_ebitda,
            "multiples_p75": (
                resolved_revenue_p75 if primary_method == "EV/Revenue" else resolved_ebitda_p75
            ),
        }

        self.logger.info(
            "Step 2: Successfully recovered from backup",
            extra={
                "step_number": 2,
                "correlation_id": correlation_id,
                "data_source": result["data_source"],
                "ev_ebitda_multiple": str(ev_ebitda),
                "ev_revenue_multiple": str(ev_revenue),
                "recovery_applied": True,
            },
        )

        return result

    @staticmethod
    def _backup_has_resolved_contract(backup: Dict[str, Any]) -> bool:
        return extract_resolved_benchmark_contract(backup) is not None

    def _recover_from_defaults(self, error: Exception, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Build result dict from SME-aware defaults.

        Uses business_type_id, business_category, and industry from context
        to select appropriate multiples instead of generic 7.0x.

        Args:
            error: The exception that triggered recovery
            context: Additional context (may include business_type_id, business_category, industry)

        Returns:
            Result dictionary with recovery defaults
        """
        correlation_id = context.get("correlation_id")
        if context.get("requires_trusted_benchmark") is True:
            raise ValueError(
                "Refusing Step 2 default recovery without explicit allow_untrusted_multiples_fallback=true"
            )
        business_type_id = context.get("business_type_id")
        business_category = context.get("business_category")
        industry = context.get("industry")

        ev_ebitda = Step2MultiplesDefaults.DEFAULT_EV_EBITDA
        ev_revenue = Step2MultiplesDefaults.DEFAULT_EV_REVENUE
        pe_ratio = Step2MultiplesDefaults.DEFAULT_PE_RATIO
        data_source = "fallback_defaults"

        try:
            from ..collectors.industry_benchmark_collector import IndustryBenchmarkCollector

            collector = IndustryBenchmarkCollector()
            fallback = collector.get_fallback_multiples(
                business_category, industry, business_type_id
            )
            if fallback:
                ev_ebitda = fallback.get("ev_ebitda", ev_ebitda)
                ev_revenue = fallback.get("ev_revenue", ev_revenue)
                pe_ratio = fallback.get("pe", pe_ratio)
                data_source = fallback.get("data_source", "fallback_sme_aware")
        except Exception:
            pass

        ebitda_p25 = ev_ebitda * Step2MultiplesDefaults.PERCENTILE_P25_MULTIPLIER
        ebitda_p75 = ev_ebitda * Step2MultiplesDefaults.PERCENTILE_P75_MULTIPLIER
        revenue_p25 = ev_revenue * Step2MultiplesDefaults.PERCENTILE_P25_MULTIPLIER
        revenue_p75 = ev_revenue * Step2MultiplesDefaults.PERCENTILE_P75_MULTIPLIER

        result = {
            "primary_method": context.get("primary_method", "EV/EBITDA"),
            "ev_ebitda_multiple": ev_ebitda,
            "ev_ebitda_p25": ebitda_p25,
            "ev_ebitda_p50": ev_ebitda,
            "ev_ebitda_p75": ebitda_p75,
            "ev_revenue_multiple": ev_revenue,
            "ev_revenue_p25": revenue_p25,
            "ev_revenue_p50": ev_revenue,
            "ev_revenue_p75": revenue_p75,
            "pe_ratio": pe_ratio,
            "data_source": data_source,
            "source_quality": (
                "emergency" if data_source == "fallback_generic_defaults" else "degraded"
            ),
            "warning": f"Step 2 exception occurred ({type(error).__name__}: {str(error)}), using SME-aware defaults",
            "recovery_applied": True,
            "multiples_p25": ebitda_p25,
            "multiples_p50": ev_ebitda,
            "multiples_p75": ebitda_p75,
        }

        self.logger.warning(
            "Step 2: Using SME-aware default multiples",
            extra={
                "step_number": 2,
                "correlation_id": correlation_id,
                "error_type": type(error).__name__,
                "recovery_applied": True,
                "data_source": data_source,
                "business_type_id": business_type_id,
                "ev_ebitda": str(ev_ebitda),
                "ev_revenue": str(ev_revenue),
            },
        )

        return result

    def _resolve_primary_method(
        self,
        backup: Dict[str, Any],
        context: Dict[str, Any],
        ev_ebitda_present: bool,
        ev_revenue_present: bool,
    ) -> str:
        """Resolve a canonical primary method for recovered Step 2 results."""
        requested_method = context.get("primary_method") or backup.get("primary_method")
        normalized_method = self._normalize_primary_method(requested_method)
        if normalized_method:
            return normalized_method
        if ev_ebitda_present:
            return "EV/EBITDA"
        if ev_revenue_present:
            return "EV/Revenue"
        return "EV/EBITDA"

    @staticmethod
    def _normalize_primary_method(primary_method: Any) -> Optional[str]:
        """Normalize legacy Step 2 method tokens to canonical Step 3 tokens."""
        if primary_method is None:
            return None
        normalized = str(primary_method).strip().upper()
        if normalized in {"EV/EBITDA", "EBITDA_MULTIPLE"}:
            return "EV/EBITDA"
        if normalized in {"EV/REVENUE", "REVENUE_MULTIPLE"}:
            return "EV/Revenue"
        return None

    def _safe_extract_multiple(
        self, data: Dict[str, Any], key: str, default: Optional[Decimal]
    ) -> Optional[Decimal]:
        """
        Safely extract and convert multiple to Decimal.

        Args:
            data: Data dictionary
            key: Key to extract
            default: Default value if extraction fails

        Returns:
            Decimal value, or None when no default is allowed
        """
        value = data.get(key)

        if value is None:
            return default

        if isinstance(value, Decimal):
            return value

        try:
            return to_decimal(value)
        except (ValueError, TypeError):
            self.logger.warning(
                (
                    f"Step 2: Failed to convert {key} to Decimal, using default"
                    if default is not None
                    else f"Step 2: Failed to convert {key} to Decimal; no fallback allowed"
                ),
                extra={
                    "step_number": 2,
                    "key": key,
                    "value": str(value),
                    "default": str(default) if default is not None else None,
                },
            )
            if default is None:
                raise
            return default
