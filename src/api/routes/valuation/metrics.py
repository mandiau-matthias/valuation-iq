"""
Prometheus metrics for valuation API
"""

from decimal import Decimal

from prometheus_client import Counter, Gauge, Histogram

from src.utils.decimal_helpers import from_decimal, to_decimal

# Auto-enable feature tracking
auto_enable_counter = Counter(
    "valuation_auto_enable_total",
    "Number of times Phase 2 features were auto-enabled",
    ["feature"],  # monte_carlo, asymmetric_ranges, intelligent_selection
)

# Field normalization tracking
normalization_counter = Counter(
    "valuation_field_normalization_total",
    "Number of times fields were normalized",
    ["field"],  # employee_count, revenue, methodology
)

# Validation tracking
validation_error_counter = Counter(
    "valuation_validation_errors_total",
    "Number of validation errors",
    ["error_type"],  # schema_validation, post_normalization, required_field
)

# Request tracking
valuation_requests_total = Counter(
    "valuation_requests_total",
    "Total number of valuation requests",
    ["methodology", "industry", "business_model"],
)

# Response time tracking
valuation_duration_seconds = Histogram(
    "valuation_duration_seconds",
    "Time spent processing valuation requests",
    ["methodology"],
    buckets=[
        Decimal("0.1"),
        Decimal("0.5"),
        Decimal("1.0"),
        Decimal("2.0"),
        Decimal("5.0"),
        Decimal("10.0"),
        Decimal("30.0"),
    ],
)

# Field usage tracking
optional_fields_gauge = Gauge(
    "valuation_optional_fields_provided",
    "Number of optional fields provided in request",
    ["field_name"],
)

# Data quality indicators
data_quality_gauge = Gauge(
    "valuation_data_quality_score",
    "Data quality score for valuation requests",
    ["has_historical", "has_balance_sheet"],
)

# Success/failure tracking
valuation_success_counter = Counter(
    "valuation_success_total", "Number of successful valuations", ["methodology"]
)

valuation_failure_counter = Counter(
    "valuation_failure_total", "Number of failed valuations", ["error_type"]
)

# Endpoint consolidation metrics
endpoint_usage_counter = Counter(
    "valuation_endpoint_usage_total",
    "Number of requests per endpoint",
    ["endpoint"],  # calculate, quick, dcf, multiples, asset-based, calculate/stream
)

mode_selection_counter = Counter(
    "valuation_mode_selection_total",
    "Mode selection (auto-detect vs explicit)",
    ["mode", "selection_method"],  # mode: quick/comprehensive, selection_method: auto/explicit
)

deprecation_warning_counter = Counter(
    "valuation_deprecation_warnings_total",
    "Number of deprecation warnings logged",
    ["deprecated_endpoint", "recommended_endpoint"],
)

auto_detection_accuracy_gauge = Gauge(
    "valuation_auto_detection_accuracy",
    "Accuracy of auto-detection (1.0 = perfect, 0.0 = all wrong)",
    ["detected_mode", "actual_mode"],  # For tracking if auto-detection was correct
)

# ============================================================================
# BUSINESS TYPE VALIDATION METRICS (December 2025)
# ============================================================================

business_type_lookups_total = Counter(
    "business_type_lookups_total",
    "Total business type lookups via API",
    [
        "flow_type",
        "match_type",
    ],  # flow_type: conversational/manual/calculator, match_type: exact/fuzzy/none
)

business_type_api_duration = Histogram(
    "business_type_api_duration_seconds",
    "Business type API lookup duration",
    ["endpoint", "flow_type"],
    buckets=[
        Decimal("0.1"),
        Decimal("0.2"),
        Decimal("0.5"),
        Decimal("1.0"),
        Decimal("2.0"),
        Decimal("5.0"),
        Decimal("15.0"),  # Timeout threshold
    ],
)

business_type_api_errors = Counter(
    "business_type_api_errors_total",
    "Business type API errors",
    ["error_type", "flow_type"],  # error_type: timeout/http_error/network_error/parse_error
)

business_type_matches = Counter(
    "business_type_matches_total",
    "Business type match results",
    ["match_quality"],  # exact/fuzzy/none
)

business_type_industry_derivations = Counter(
    "business_type_industry_derivations_total",
    "Industry auto-derived from business type",
    ["source"],  # database/static_fallback/failed
)

# IndustryExtractor deprecation tracking
industry_extractor_usage = Counter(
    "industry_extractor_usage_total",
    "DEPRECATED: IndustryExtractor usage (to be removed)",
    ["caller"],  # field_extraction_coordinator/other
)

# ============================================================================
# MULTIPLES DATA SOURCE METRICS (January 2026)
# ============================================================================
# Track where valuation multiples come from to monitor data pipeline health
# and identify when fallbacks are being used instead of resolved benchmark contracts.

multiples_source_counter = Counter(
    "valuation_multiples_source_total",
    "Valuation multiples by data source - tracks pipeline health",
    ["source", "business_type_id"],
    # source values:
    # - titan_enrichment: Best - resolved benchmark contract via Titan
    # - business_type_db: Legacy cache fallback
    # - database_driven_default: Disclosed startup-cache fallback
    # - database_category_default: Disclosed aggregate fallback
    # - database_industry_default: Disclosed aggregate fallback
    # - fmp_api: Disclosed external public-company fallback
    # - cache: Disclosed cached external fallback
    # - hardcoded_business_type: Legacy - should be rare
    # - hardcoded_category_default: Legacy - should be rare
    # - hardcoded_industry: Legacy - should be rare
    # - hardcoded_default: Critical - indicates pipeline failure
)

multiples_fallback_counter = Counter(
    "valuation_multiples_fallback_total",
    "Fallback usage when resolved benchmark contracts are unavailable - indicates issues",
    ["fallback_type", "severity"],
    # fallback_type: hardcoded_business_type, hardcoded_category, hardcoded_industry, generic
    # severity: LOW, MEDIUM, HIGH, CRITICAL
)

titan_enrichment_status = Counter(
    "titan_enrichment_status_total",
    "Titan enrichment success/failure for business types",
    ["status", "business_type_id"],
    # status: success, missing, partial
)

# ----------------------------------------------------------------------------
# Country-aware multiples-source telemetry
# ----------------------------------------------------------------------------
# A non-zero rate of `source="hardcoded_default"` for any country is a
# pipeline failure. The active-catalog × 16 guarantee means every (business_type,
# country) request should land on Titan enrichment (PRIORITY -1) or, at
# worst, on the synced category default. Keep this counter separate from
# `multiples_source_counter` so adding the country dimension doesn't break
# existing dashboards built on the (source, business_type_id) tuple.
#
# Cardinality: 12 sources × active business types × 17 countries (16 + "unknown")
# ~= 35k series upper bound. Acceptable for Prometheus; the real population
# is much smaller because most (BT, country) cells never fire.
multiples_source_by_country_counter = Counter(
    "valuation_multiples_source_by_country_total",
    (
        "Valuation multiples by data source AND country — per-country pipeline "
        "health. Use to monitor the active-catalog × 16 coverage guarantee: any sustained "
        "rate of source=hardcoded_default for a country is a P0 alert."
    ),
    ["source", "business_type_id", "country_code"],
)

multiples_critical_fallback_counter = Counter(
    "valuation_multiples_critical_fallback_total",
    (
        "CRITICAL: generic 8.0x EBITDA / 1.0x revenue fallback fired — "
        "every increment indicates the entire data pipeline (Titan, DB, "
        "FMP, cache, all defaults) failed for that (business_type, country)."
    ),
    ["business_type_id", "country_code", "industry"],
)

database_defaults_loaded = Gauge(
    "database_driven_defaults_loaded",
    "Number of business types loaded from database at startup",
    ["type"],  # business_types, categories, industries
)

# ============================================================================
# SME CALIBRATION METRICS (January 2026)
# ============================================================================
# Track SME calibration data sources to ensure database-driven valuations
# and identify when hardcoded fallbacks are being used.

sme_calibration_source_counter = Counter(
    "sme_calibration_source_total",
    "SME calibration data source - tracks priority cascade health",
    ["source", "sme_class", "industry"],
    # source values (in priority order):
    # - titan_enrichment: Priority 1 - from Titan request (best - database-sourced via API)
    # - database_category: Priority 2 - from DatabaseDrivenDefaults by category
    # - database_industry: Priority 2 - from DatabaseDrivenDefaults by industry
    # - hardcoded_fallback: Priority 3 - disclosed emergency values (must be opt-in)
)

sme_calibration_fallback_counter = Counter(
    "sme_calibration_fallback_total",
    "SME calibration fallback usage - indicates missing database data",
    ["sme_class", "industry", "reason"],
    # reason: no_titan_data, db_not_initialized, db_lookup_failed
)

sme_size_premium_source_counter = Counter(
    "sme_size_premium_source_total",
    "Size premium data source for WACC calculation",
    ["source", "sme_class"],
    # source: database, hardcoded_duff_phelps
)

sme_multiple_bounds_violation_counter = Counter(
    "sme_multiple_bounds_violation_total",
    "SME multiple exceeded academic bounds and was clamped",
    ["sme_class", "bound_type"],  # bound_type: min_floor, max_ceiling
)
