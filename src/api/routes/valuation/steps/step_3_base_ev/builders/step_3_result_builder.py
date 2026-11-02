"""
Step 3 Result Builder

Builds result dictionaries and metadata for Step 3 (Base Enterprise Value).

SOURCE TRACING:
- Data Source: TITAN_BUSINESS_TYPES_DB (enriched multiples from the Upswitch Index)
- Methodology Foundation: EV = metric x resolved benchmark multiple
- Methodology: EV = Metric × Multiple (EV/EBITDA or EV/Revenue)

ALIGNMENT WITH UPSWITCH PRIMITIVES:
- Primitive 2: Algorithmic Defensibility - formula and sources fully traceable
"""

from decimal import Decimal
from typing import Any, Dict, Optional

from src.api.routes.valuation.benchmark_contract_utils import (
    benchmark_contract_source_key,
    is_resolved_benchmark_contract,
)
from src.utils.decimal_helpers import from_decimal, to_decimal
from src.utils.logging import get_logger

from ...base_step import StepOutput, StepStatus
from ...source_tracing import build_source_metadata, get_step_academic_sources

logger = get_logger(__name__)


class Step3ResultBuilder:
    """Builds result dictionaries and metadata for Step 3."""

    def __init__(self, step_name: str):
        """
        Initialize the result builder.

        Args:
            step_name: Step name for StepOutput
        """
        self.step_name = step_name

    def build_result_dict(
        self,
        ev_low_float: Decimal,
        ev_mid_float: Decimal,
        ev_high_float: Decimal,
        primary_method: str,
        metric_name: str,
        metric_float: Decimal,
        multiple_float: Decimal,
        multiple_p25_float: Decimal,
        multiple_p50_float: Decimal,
        multiple_p75_float: Decimal,
        using_real_percentiles: bool,
        implied_ebitda_multiple: Optional[Decimal] = None,
        benchmark_provenance: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Build comprehensive result dictionary.

        Args:
            ev_low_float: EV low value
            ev_mid_float: EV mid value
            ev_high_float: EV high value
            primary_method: Primary method
            metric_name: Metric name
            metric_float: Metric value
            multiple_float: Median multiple
            multiple_p25_float: P25 multiple
            multiple_p50_float: P50 multiple
            multiple_p75_float: P75 multiple
            using_real_percentiles: Whether using real percentiles
            implied_ebitda_multiple: Implied EBITDA multiple when primary method is Revenue
                (EV_mid / EBITDA — transparency for advisors)

        Returns:
            Result dictionary
        """
        result = {
            "enterprise_value_low": ev_low_float,
            "enterprise_value_mid": ev_mid_float,
            "enterprise_value_high": ev_high_float,
            "primary_method": primary_method,
            "primary_metric": metric_name,
            "primary_metric_value": metric_float,
            "primary_multiple": multiple_float,
            # Percentile multiples for frontend display
            "multiple_p25": multiple_p25_float,
            "multiple_p50": multiple_p50_float,
            "multiple_p75": multiple_p75_float,
            "percentile_source": "real" if using_real_percentiles else "estimated",
            # Multiple pipeline tracking (Multiple-First Discounting feature)
            # Store initial multiples - these become the baseline for all subsequent discount steps
            "initial_multiple_low": multiple_p25_float,
            "initial_multiple_mid": multiple_p50_float,
            "initial_multiple_high": multiple_p75_float,
            # Current multiples (will be adjusted by subsequent discount steps)
            # Initially same as initial multiples, but Steps 4-6 will update these
            "current_multiple_low": multiple_p25_float,
            "current_multiple_mid": multiple_p50_float,
            "current_multiple_high": multiple_p75_float,
            # Initialize empty list for pipeline stages (Steps 4-8 will populate)
            "multiple_pipeline_stages": [],
            "benchmark_contract": benchmark_provenance,
            "benchmark_provenance": benchmark_provenance,
        }

        if isinstance(benchmark_provenance, dict):
            result.update(
                {
                    "benchmark_id": benchmark_provenance.get("benchmark_id"),
                    "dataset_version_id": benchmark_provenance.get("dataset_version_id"),
                    "benchmark_country_code": benchmark_provenance.get("country_code"),
                    "benchmark_region_key": benchmark_provenance.get("region_key"),
                    "benchmark_tier": benchmark_provenance.get("tier"),
                    "benchmark_walk_step": benchmark_provenance.get("walk_step"),
                    "benchmark_scope_stage": benchmark_provenance.get("scope_stage"),
                    "benchmark_sample_size": benchmark_provenance.get("sample_size"),
                    "benchmark_confidence_band": benchmark_provenance.get("confidence_band"),
                    "benchmark_source_mix": benchmark_provenance.get("source_mix"),
                    "benchmark_evidence_summary": benchmark_provenance.get("evidence_summary"),
                    "benchmark_published_at": benchmark_provenance.get("published_at"),
                    "benchmark_methodology_version": benchmark_provenance.get(
                        "methodology_version"
                    ),
                }
            )

        if implied_ebitda_multiple is not None:
            result["implied_ebitda_multiple"] = implied_ebitda_multiple

        return result

    def build_metadata_dict(
        self,
        metric_name: str,
        metric_float: Decimal,
        multiple_p25_float: Decimal,
        multiple_p50_float: Decimal,
        multiple_p75_float: Decimal,
        ev_low_float: Decimal,
        ev_mid_float: Decimal,
        ev_high_float: Decimal,
        using_real_percentiles: bool,
        data_source: str = "TITAN_BUSINESS_TYPES_DB",
        benchmark_provenance: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Build metadata dictionary with full source tracing.

        Args:
            metric_name: Metric name
            metric_float: Metric value
            multiple_p25_float: P25 multiple
            multiple_p50_float: P50 multiple
            multiple_p75_float: P75 multiple
            ev_low_float: EV low value
            ev_mid_float: EV mid value
            ev_high_float: EV high value
            using_real_percentiles: Whether using real percentiles
            data_source: Data source identifier for tracing

        Returns:
            Metadata dictionary with source tracing
        """
        if is_resolved_benchmark_contract(benchmark_provenance):
            data_source = benchmark_contract_source_key(benchmark_provenance)

        # Build source tracing metadata
        source_metadata = build_source_metadata(
            step_key="step_3_base_ev",
            data_source=data_source,
        )

        return {
            # Calculation details
            "formula": f"{metric_name} × Multiple",
            "calculation_mid": f"{metric_float:,.0f} × {multiple_p50_float:.2f}x = {ev_mid_float:,.0f}",
            "calculation_low": f"{metric_float:,.0f} × {multiple_p25_float:.2f}x = {ev_low_float:,.0f}",
            "calculation_high": f"{metric_float:,.0f} × {multiple_p75_float:.2f}x = {ev_high_float:,.0f}",
            "percentile_source": "real" if using_real_percentiles else "estimated",
            "multiple_p25": multiple_p25_float,
            "multiple_p50": multiple_p50_float,
            "multiple_p75": multiple_p75_float,
            "precision": "Decimal (bank-grade)",
            "rounding": "ROUND_HALF_EVEN (banker's rounding)",
            "range_validated": True,
            "benchmark_contract": benchmark_provenance,
            "benchmark_provenance": benchmark_provenance,
            "benchmark_id": (
                benchmark_provenance.get("benchmark_id")
                if isinstance(benchmark_provenance, dict)
                else None
            ),
            "dataset_version_id": (
                benchmark_provenance.get("dataset_version_id")
                if isinstance(benchmark_provenance, dict)
                else None
            ),
            "benchmark_country_code": (
                benchmark_provenance.get("country_code")
                if isinstance(benchmark_provenance, dict)
                else None
            ),
            "benchmark_region_key": (
                benchmark_provenance.get("region_key")
                if isinstance(benchmark_provenance, dict)
                else None
            ),
            "benchmark_tier": (
                benchmark_provenance.get("tier") if isinstance(benchmark_provenance, dict) else None
            ),
            "benchmark_walk_step": (
                benchmark_provenance.get("walk_step")
                if isinstance(benchmark_provenance, dict)
                else None
            ),
            "benchmark_scope_stage": (
                benchmark_provenance.get("scope_stage")
                if isinstance(benchmark_provenance, dict)
                else None
            ),
            "benchmark_sample_size": (
                benchmark_provenance.get("sample_size")
                if isinstance(benchmark_provenance, dict)
                else None
            ),
            "benchmark_confidence_band": (
                benchmark_provenance.get("confidence_band")
                if isinstance(benchmark_provenance, dict)
                else None
            ),
            "benchmark_source_mix": (
                benchmark_provenance.get("source_mix")
                if isinstance(benchmark_provenance, dict)
                else None
            ),
            "benchmark_evidence_summary": (
                benchmark_provenance.get("evidence_summary")
                if isinstance(benchmark_provenance, dict)
                else None
            ),
            "benchmark_published_at": (
                benchmark_provenance.get("published_at")
                if isinstance(benchmark_provenance, dict)
                else None
            ),
            "benchmark_methodology_version": (
                benchmark_provenance.get("methodology_version")
                if isinstance(benchmark_provenance, dict)
                else None
            ),
            # Source tracing (Primitive 2: Algorithmic Defensibility)
            "data_source": source_metadata["data_source"],
            "data_source_name": source_metadata["data_source_name"],
            "source_confidence": source_metadata["source_confidence"],
            "academic_sources": source_metadata["academic_sources"],
            "primary_citation": source_metadata["primary_citation"],
        }

    def build_skipped_result(
        self, revenue: Decimal, ebitda: Optional[Decimal], primary_method: str
    ) -> Dict[str, Any]:
        """
        Build SKIPPED status result.

        Args:
            revenue: Revenue value
            ebitda: EBITDA value (optional)
            primary_method: Primary method

        Returns:
            Result dictionary for SKIPPED status
        """
        return {
            "enterprise_value_low": Decimal("0.0"),
            "enterprise_value_mid": Decimal("0.0"),
            "enterprise_value_high": Decimal("0.0"),
            "primary_method": primary_method,
            "skip_reason": "Revenue is zero or negative - cannot calculate enterprise value",
            "revenue": revenue,
            "ebitda": ebitda,
        }
