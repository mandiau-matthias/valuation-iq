"""
Request Utilities

Utility functions for request processing, normalization, and mode detection.
Extracted from valuation.py to improve modularity.

BANK-GRADE QUALITY:
- Full type hints
- Comprehensive error handling
- Detailed logging
- No code duplication
"""

import hashlib
from decimal import Decimal
from typing import Any, Dict

from src.api.schemas import ValuationRequest
from src.config import get_settings
from src.utils.logging import get_logger
from src.utils.registry_identity_context import resolve_business_type_id, resolve_registry_identity

from ..metrics import auto_enable_counter, data_quality_gauge, normalization_counter
from .real_estate_carve_out import apply_real_estate_carve_out as _apply_real_estate_carve_out

logger = get_logger(__name__)


def _decimal_or_none(value: Any) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        numeric = Decimal(str(value))
    except Exception:
        return None
    return numeric if numeric.is_finite() else None


def _get_row_value(row: Any, key: str) -> Any:
    if isinstance(row, dict):
        return row.get(key)
    return getattr(row, key, None)


def _has_positive_historical_revenue(row: Any) -> bool:
    revenue = _decimal_or_none(_get_row_value(row, "revenue"))
    return revenue is not None and revenue > 0


def _strip_unusable_historical_years(request: ValuationRequest) -> ValuationRequest:
    historical_years = list(getattr(request, "historical_years_data", None) or [])
    if not historical_years:
        return request

    filtered_years = [year for year in historical_years if _has_positive_historical_revenue(year)]
    if len(filtered_years) == len(historical_years):
        return request

    logger.info(
        "Dropped unusable historical rows before validation",
        extra={
            "dropped_count": len(historical_years) - len(filtered_years),
            "remaining_count": len(filtered_years),
        },
    )
    return request.model_copy(update={"historical_years_data": filtered_years})


def _reanchor_placeholder_current_year(request: ValuationRequest) -> ValuationRequest:
    """Mirror of `_strip_unusable_historical_years` for the CURRENT year.

    M&A basis hygiene: when `current_year_data` is a no-books placeholder (an
    open filing year synced from an accounting import: revenue 0, EBITDA 0,
    empty balance sheet) and usable closed years exist in the history, the
    valuation must be based on the latest CLOSED accounts — not on a
    zero-filled draft. Zero-turnover holdings (balance-sheet substance, no
    operating figures) are deliberately untouched; the asset-based path owns
    those. Shares the helper with the stateless route so both calculation
    lanes anchor identically.
    """
    from src.services.reports.stateless_calculation_helpers import (
        maybe_reanchor_placeholder_current_year,
    )

    promoted, remaining, reanchor = maybe_reanchor_placeholder_current_year(
        request.current_year_data,
        list(getattr(request, "historical_years_data", None) or []),
    )
    if reanchor is None:
        return request

    logger.info(
        "Re-anchored placeholder current year onto latest usable closed year",
        extra={
            "valuation_id": getattr(request, "valuation_id", None),
            "company_name": getattr(request, "company_name", None),
            "from_year": reanchor["from_year"],
            "to_year": reanchor["to_year"],
        },
    )
    return request.model_copy(
        update={
            "current_year_data": promoted,
            "historical_years_data": remaining,
        }
    )


def get_request_fingerprint(request: ValuationRequest) -> str:
    """
    Generate unique fingerprint for debugging.

    Args:
        request: Valuation request

    Returns:
        Hexadecimal fingerprint string (16 characters)
    """
    data = request.model_dump_json(exclude_none=True, exclude_unset=True)
    return hashlib.sha256(data.encode()).hexdigest()[:16]


def log_field_usage(request: ValuationRequest) -> None:
    """
    Log which fields are actually provided in the request.

    Args:
        request: Valuation request
    """
    provided_fields = {k: v is not None for k, v in request.model_dump(exclude_unset=True).items()}

    optional_fields_used = [
        k
        for k in [
            "business_type",
            "business_description",
            "business_highlights",
            "reason_for_selling",
            "city",
            "shares_for_sale",
            "exclude_real_estate",
            "real_estate_book_value",
            "estimated_market_rent",
        ]
        if provided_fields.get(k)
    ]

    # DEBUG: field-usage telemetry. Missing-field problems surface as
    # downstream validation errors or readiness signals — this counter is
    # developer-facing only.
    logger.debug(
        f"Field usage: {len(provided_fields)}/{len(request.model_fields)} fields provided",
        extra={
            "total_fields": len(provided_fields),
            "optional_fields_used": optional_fields_used,
            "has_historical": bool(request.historical_years_data),
            "has_balance_sheet": bool(
                request.current_year_data.total_assets and request.current_year_data.total_debt
            ),
        },
    )


def is_quick_mode(request: ValuationRequest) -> bool:
    """
    Detect if request should use quick valuation mode.

    Quick mode criteria:
    - Only basic financial data (revenue, EBITDA)
    - No historical years data
    - No balance sheet data (total_assets, total_debt, cash)
    - No complex methodology requirements

    Args:
        request: Valuation request

    Returns:
        True if request should use quick mode, False for comprehensive mode
    """
    # Check for historical data
    has_historical = request.historical_years_data and len(request.historical_years_data) > 0

    # Check for balance sheet data
    has_balance_sheet = (
        request.current_year_data.total_assets
        or request.current_year_data.total_liabilities
        or request.current_year_data.cash
    )

    # Check for additional financial metrics
    has_net_income = request.current_year_data.net_income is not None

    # Check if methodology is explicitly set to something other than default
    has_explicit_methodology = request.methodology and request.methodology.upper() not in [
        "HYBRID",
        "QUICK",
        None,
        "",
    ]

    # Manual flow is identified by dataSource='manual' (forwarded from Node.js)
    # Note: use_dcf and use_multiples default to True so cannot be used for detection
    is_manual_flow = (
        hasattr(request, "dataSource") and getattr(request, "dataSource", None) == "manual"
    )

    is_quick = (
        not has_historical
        and not has_balance_sheet
        and not has_net_income
        and not has_explicit_methodology
        and not is_manual_flow
    )

    return is_quick


def normalize_request_fields(request: ValuationRequest) -> ValuationRequest:
    """
    Normalize duplicate fields from different frontend sources (immutable).

    Handles field name inconsistencies between different frontend implementations.

    Args:
        request: Valuation request

    Returns:
        Normalized valuation request
    """
    updates: Dict[str, Any] = {}

    # Normalize employee count
    if request.employee_count and not request.number_of_employees:
        updates["number_of_employees"] = request.employee_count
        normalization_counter.labels(field="employee_count").inc()

    # Normalize top-level revenue
    if request.revenue and not request.current_year_data.revenue:
        current_year_updates = request.current_year_data.model_copy(
            update={"revenue": request.revenue}
        )
        updates["current_year_data"] = current_year_updates
        normalization_counter.labels(field="revenue").inc()

    # Ensure methodology is set
    if not request.methodology:
        updates["methodology"] = "HYBRID"
        normalization_counter.labels(field="methodology").inc()

    resolved_identity = resolve_registry_identity(
        country_code=request.country_code,
        business_context=request.business_context,
        registration_number=request.registration_number,
        kbo_number=request.kbo_number,
        kvk_number=request.kvk_number,
        vat_number=request.vat_number,
        legal_form=request.legal_form,
        postal_code=getattr(request, "postal_code", None),
        city=getattr(request, "city", None),
    )
    for field, value in resolved_identity.items():
        if getattr(request, field, None) != value:
            updates[field] = value
            normalization_counter.labels(field=f"registry_{field}").inc()
    business_type_id = resolve_business_type_id(
        business_context=request.business_context,
        business_type_id=request.business_type_id,
    )
    if request.business_type_id != business_type_id:
        updates["business_type_id"] = business_type_id
        normalization_counter.labels(field="registry_business_type_id").inc()

    normalized = request.model_copy(update=updates) if updates else request
    normalized = _reanchor_placeholder_current_year(normalized)
    normalized = _strip_unusable_historical_years(normalized)
    normalized = _apply_real_estate_carve_out(normalized)
    return normalized


def auto_enable_phase2_features(request: ValuationRequest) -> ValuationRequest:
    """
    Auto-enable Phase 2 features based on data quality (immutable).

    Automatically enables advanced features when sufficient data is available:
    - Monte Carlo Simulation: ≥2 years of historical data
    - Asymmetric Ranges: SMEs (<50 employees)
    - Intelligent Selection: Complete balance sheet + historical data

    Args:
        request: Valuation request

    Returns:
        Updated valuation request with Phase 2 features enabled
    """
    updates: Dict[str, Any] = {}

    # Calculate data quality indicators
    has_historical = request.historical_years_data and len(request.historical_years_data) >= 2
    has_balance_sheet = (
        request.current_year_data.total_assets
        and request.current_year_data.total_debt
        and request.current_year_data.cash
    )

    # Track data quality
    data_quality_gauge.labels(
        has_historical=str(has_historical), has_balance_sheet=str(has_balance_sheet)
    ).set(1 if (has_historical and has_balance_sheet) else 0)

    # Enable Monte Carlo if we have historical data
    if has_historical and not request.use_monte_carlo:
        updates["use_monte_carlo"] = True
        auto_enable_counter.labels(feature="monte_carlo").inc()
        logger.info("Auto-enabled Monte Carlo due to historical data availability")

    # Enable asymmetric ranges for SMEs
    if (
        request.number_of_employees
        and request.number_of_employees < 50
        and not request.use_asymmetric_ranges
    ):
        updates["use_asymmetric_ranges"] = True
        auto_enable_counter.labels(feature="asymmetric_ranges").inc()
        logger.debug("Auto-enabled asymmetric ranges for SME")

    # Enable intelligent selection if we have rich data
    if has_balance_sheet and has_historical and not request.use_intelligent_selection:
        updates["use_intelligent_selection"] = True
        auto_enable_counter.labels(feature="intelligent_selection").inc()
        logger.info("Auto-enabled intelligent selection due to data richness")

    return request.model_copy(update=updates) if updates else request
