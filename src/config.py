"""
Configuration module for Upswitch Valuation Engine

This module handles all application configuration using Pydantic Settings
for type-safe environment variable management.
"""

import json
import os
from decimal import Decimal
from ipaddress import ip_address
from typing import List, Literal, Optional, Union
from urllib.parse import urlparse

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _default_api_middleware_log_mode() -> str:
    """Prefer minimal API middleware logging on Railway to avoid log rate limits."""
    if os.environ.get("RAILWAY_ENVIRONMENT") or os.environ.get("RAILWAY_SERVICE_NAME"):
        return "minimal"
    return "full"


def resolve_default_server_host() -> str:
    """Bind locally by default, but keep platform deployments externally reachable."""
    configured_host = os.environ.get("HOST", "").strip()
    if configured_host:
        return configured_host
    if os.environ.get("RAILWAY_ENVIRONMENT") or os.environ.get("RAILWAY_SERVICE_NAME"):
        return str(ip_address(0))
    return "127.0.0.1"


class Settings(BaseSettings):
    """Application settings with environment variable support"""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False, extra="ignore"
    )

    # Application Settings
    environment: str = Field(
        default="development", description="Environment: development, staging, production"
    )
    expose_openapi_in_production: bool = Field(
        default=False,
        description=(
            "When True, serve /docs, /redoc, and /openapi.json in production. "
            "Use only behind private network, mTLS, or when intentionally publishing engine docs. "
            "Env: EXPOSE_OPENAPI_IN_PRODUCTION."
        ),
    )
    app_name: str = Field(default="Upswitch Valuation Engine", description="Application name")
    app_version: str = Field(default="1.0.0", description="Application version")
    debug: bool = Field(default=False, description="Debug mode")
    log_level: str = Field(default="info", description="Logging level")
    request_body_logging: bool = Field(
        default=False,
        description="Log full request bodies for valuation endpoints. Never enable for production traffic.",
    )
    api_middleware_log_mode: Literal["full", "minimal"] = Field(
        default_factory=_default_api_middleware_log_mode,
        description=(
            "full: verbose per-request middleware (audit + performance lines). "
            "minimal: one access line per request (recommended on Railway; avoids ~500 logs/sec caps)."
        ),
    )

    # Server Configuration
    host: str = Field(default_factory=resolve_default_server_host, description="Server host")
    port: int = Field(default=8080, description="Server port")
    workers: int = Field(default=4, description="Number of workers")
    reload: bool = Field(default=True, description="Auto-reload on code changes")

    # Database Configuration
    database_url: str = Field(
        default="postgresql://localhost:5432/upswitch_valuation",
        description="PostgreSQL database URL",
    )

    # Business Types Database (separate database with business_types table)
    business_types_database_url: str = Field(
        default="",
        description="Database URL for business types (if separate from main DB)",
    )

    # KBO Database (1.8M companies)
    kbo_database_url: str = Field(
        default="",
        description="KBO database URL for 1.8M Belgian companies",
    )
    database_pool_size: int = Field(default=20, description="Database connection pool size")
    database_max_overflow: int = Field(default=10, description="Max overflow connections")

    # =========================================================================
    # BRAIN & MUSCLE ARCHITECTURE: Stateless Mode Configuration
    # =========================================================================
    # When ValuationIQ runs in stateless mode (THE MUSCLE):
    # - All data comes from Titan (THE BRAIN) via API requests
    # - No direct database access required
    # - No Redis session state
    # - No AI/LLM calls (handled by Titan with Claude)
    #
    # To enable stateless mode, set:
    #   STATELESS_MODE=true
    # Or individually:
    #   REQUIRE_EXTERNAL_DATA=true
    #   DATABASE_OPTIONAL=true
    #   REDIS_OPTIONAL=true
    # =========================================================================

    stateless_mode: bool = Field(
        default=True,
        description="Enable full stateless mode (Brain & Muscle Architecture). "
        "When True, ValuationIQ is a pure calculation engine with no external state. "
        "DEFAULT: True (as of Jan 2026 cleanup)",
    )
    require_external_data: bool = Field(
        default=False,
        description="When True, require all data to come from Titan API (no direct DB/API access)",
    )
    titan_api_url: str = Field(
        default="",
        description="Explicit Titan API URL for registry and external-data fetching",
    )
    hermes_evidence_public_key_registry_json: str = Field(
        default="{}",
        description=(
            "JSON object keyed by Hermes evidence key_id. Each entry must include "
            "issuer and public_key_b64 and may include not_before, not_after and revoked."
        ),
    )
    titan_valuation_case_public_key_registry_json: str = Field(
        default="{}",
        description=(
            "JSON object keyed by Titan valuation-case key_id. Each entry must include "
            "issuer and public_key_b64 and may include not_before, not_after and revoked."
        ),
    )
    titan_valuation_assurance_public_key_registry_json: str = Field(
        default="{}",
        description=(
            "JSON object keyed by Titan valuation-assurance key_id. Each entry must include "
            "issuer and public_key_b64 and may include not_before, not_after and revoked."
        ),
    )
    titan_valuation_assurance_status_bearer_token: str = Field(
        default="",
        description=(
            "Dedicated bearer credential for ValuationIQ's fail-closed, no-cache call to "
            "Titan's current assurance-head and revocation authority."
        ),
    )
    database_optional: bool = Field(
        default=True,
        description="When True, app starts without database (uses Titan data)",
    )
    redis_optional: bool = Field(
        default=True,
        description="When True, app starts without Redis (no session state caching)",
    )

    @model_validator(mode="after")
    def enforce_titan_kbo_boundary(self) -> "Settings":
        railway_deployment = bool(
            os.environ.get("RAILWAY_ENVIRONMENT") or os.environ.get("RAILWAY_SERVICE_NAME")
        )
        deployed_environment = railway_deployment or self.environment.lower() in {
            "staging",
            "production",
        }
        if not deployed_environment:
            return self
        legacy_kbo_variable = "KBO" + "_DATABASE_URL"
        if self.kbo_database_url:
            raise ValueError(
                f"{legacy_kbo_variable} is Titan-only and must not be configured in ValuationIQ"
            )
        if not self.stateless_mode or not self.require_external_data:
            raise ValueError(
                "ValuationIQ deployments must enable STATELESS_MODE and REQUIRE_EXTERNAL_DATA"
            )
        if not self.titan_api_url:
            raise ValueError("TITAN_API_URL is required for ValuationIQ deployments")
        titan_origin = urlparse(self.titan_api_url)
        if titan_origin.scheme != "https" or not titan_origin.netloc:
            raise ValueError(
                "ValuationIQ deployments require an HTTPS TITAN_API_URL for live assurance"
            )
        try:
            evidence_keys = json.loads(self.hermes_evidence_public_key_registry_json)
        except json.JSONDecodeError as exc:
            raise ValueError("HERMES_EVIDENCE_PUBLIC_KEY_REGISTRY_JSON must be valid JSON") from exc
        if not isinstance(evidence_keys, dict) or not evidence_keys:
            raise ValueError(
                "ValuationIQ deployments require a non-empty Hermes evidence public-key registry"
            )
        try:
            valuation_case_keys = json.loads(self.titan_valuation_case_public_key_registry_json)
        except json.JSONDecodeError as exc:
            raise ValueError(
                "TITAN_VALUATION_CASE_PUBLIC_KEY_REGISTRY_JSON must be valid JSON"
            ) from exc
        if not isinstance(valuation_case_keys, dict) or not valuation_case_keys:
            raise ValueError(
                "ValuationIQ deployments require a non-empty Titan valuation-case "
                "public-key registry"
            )
        try:
            valuation_assurance_keys = json.loads(
                self.titan_valuation_assurance_public_key_registry_json
            )
        except json.JSONDecodeError as exc:
            raise ValueError(
                "TITAN_VALUATION_ASSURANCE_PUBLIC_KEY_REGISTRY_JSON must be valid JSON"
            ) from exc
        if not isinstance(valuation_assurance_keys, dict) or not valuation_assurance_keys:
            raise ValueError(
                "ValuationIQ deployments require a non-empty Titan valuation-assurance "
                "public-key registry"
            )
        if not self.titan_valuation_assurance_status_bearer_token.strip():
            raise ValueError(
                "ValuationIQ deployments require TITAN_VALUATION_ASSURANCE_STATUS_BEARER_TOKEN"
            )
        return self

    cap_country_baseline_multiple_to_sector: bool = Field(
        default=True,
        description="When True and Step 2 served a non-defendable country-baseline "
        "(e.g. Damodaran European total-market) EV/EBITDA fallback because no "
        "defendable sector benchmark existed, Step 3 anchors the percentile band "
        "to the synced business-type sector multiple (the figure shown on the "
        "business-type card). Scale-DOWN only. Kill-switch for the sector anchor.",
    )

    # Redis Configuration (Railway-optimized)
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        description="Redis URL for caching",
        # Railway provides REDIS_URL automatically
    )
    redis_host: Optional[str] = Field(default=None)
    redis_port: int = Field(default=6379)
    redis_password: Optional[str] = Field(default=None)
    redis_max_connections: int = Field(default=50, description="Max Redis connections")
    redis_socket_timeout: int = Field(default=15, description="Redis socket timeout (seconds)")
    redis_socket_connect_timeout: int = Field(default=15, description="Redis connection timeout")
    redis_retry_on_timeout: bool = Field(default=True, description="Retry on timeout")
    redis_health_check_interval: int = Field(default=30, description="Health check interval")
    cache_ttl: int = Field(default=3600, description="Default cache TTL in seconds")

    # Context Memory Configuration
    enable_redis_context: bool = Field(
        default=False, description="Enable Redis-backed context storage"
    )
    context_redis_db: int = Field(default=0, description="Redis DB for conversation context")
    # UPDATED: Extended TTLs to allow users to return and continue conversations
    context_guest_ttl: int = Field(
        default=604800, description="Guest session TTL in seconds (7 days, was 2 hours)"
    )
    context_guest_completed_ttl: int = Field(
        default=2592000, description="Completed guest session TTL (30 days, was 24 hours)"
    )
    context_logged_in_ttl: int = Field(
        default=7776000, description="Logged-in user TTL (90 days, was 7 days)"
    )
    context_ttl_extension_enabled: bool = Field(
        default=True, description="Auto-extend TTL on each interaction"
    )
    context_ttl_extension_amount: int = Field(
        default=86400, description="TTL extension per interaction (24 hours)"
    )
    context_compression_threshold: int = Field(
        default=10240, description="Compress contexts larger than this (bytes)"
    )
    context_lru_cache_size: int = Field(default=100, description="LRU cache size for hot contexts")

    # ML Pipeline Configuration
    enable_ml_pipeline: bool = Field(default=False, description="Enable ML pipeline features")
    ml_embeddings_enabled: bool = Field(
        default=False, description="Enable embedding generation and storage"
    )
    ml_features_enabled: bool = Field(
        default=False, description="Enable feature extraction and storage"
    )
    ml_predictions_enabled: bool = Field(
        default=False, description="Enable prediction caching and serving"
    )
    ml_background_tasks_enabled: bool = Field(
        default=False, description="Enable background ML tasks"
    )

    # Embedding Configuration
    # DEPRECATED: provider-backed embeddings have been removed; use Titan.
    embedding_model: str = Field(
        default="legacy_cached_vector",
        description="DEPRECATED: generated embeddings moved to Titan",
    )
    embedding_dimensions: int = Field(default=1536, description="Embedding dimensions")
    embedding_cache_ttl: int = Field(default=604800, description="Embedding cache TTL (7 days)")
    embedding_batch_size: int = Field(default=10, description="Batch size for embedding generation")
    embedding_daily_cost_limit: Decimal = Field(
        default=10.0, description="DEPRECATED: embedding generation cost limit moved to Titan"
    )

    # Feature Store Configuration
    feature_store_redis_db: int = Field(default=1, description="Redis DB for feature store")
    feature_cache_ttl: int = Field(default=3600, description="Feature cache TTL (1 hour)")
    feature_batch_size: int = Field(default=20, description="Batch size for feature extraction")
    feature_drift_threshold: Decimal = Field(
        default=0.1, description="Feature drift detection threshold"
    )

    # Prediction Cache Configuration
    prediction_cache_redis_db: int = Field(default=3, description="Redis DB for prediction cache")
    prediction_cache_ttl: int = Field(default=3600, description="Prediction cache TTL (1 hour)")
    prediction_cache_hit_rate_threshold: Decimal = Field(
        default=0.5, description="Minimum cache hit rate threshold"
    )
    ml_performance_threshold: Decimal = Field(default=0.8, description="ML performance threshold")
    ml_retraining_threshold: Decimal = Field(default=0.7, description="ML retraining threshold")

    # ML Task Configuration
    embedding_task_interval: int = Field(
        default=300, description="Embedding task interval (5 minutes)"
    )
    feature_task_interval: int = Field(
        default=600, description="Feature task interval (10 minutes)"
    )
    ml_task_interval: int = Field(default=3600, description="ML task interval (1 hour)")
    ml_task_timeout: int = Field(default=300, description="ML task timeout (5 minutes)")

    # Semantic Search Configuration
    semantic_search_threshold: Decimal = Field(
        default=0.7, description="Semantic search similarity threshold"
    )
    semantic_search_max_results: int = Field(
        default=10, description="Maximum semantic search results"
    )
    duplicate_detection_threshold: Decimal = Field(
        default=0.8, description="Duplicate detection threshold"
    )

    # External API Keys
    # NOTE: provider-model config removed - Brain & Muscle Architecture
    # All model orchestration features are now in Titan (The Brain)
    # ValuationIQ (The Muscle) is a pure stateless calculation engine

    # KVK (Netherlands) — optional third-party registry; NL works without it (manual / Yuki)
    kvk_api_key: Optional[str] = Field(
        default=None,
        description="Optional API key for NL registry provider (e.g. Overheid.io OpenKvK V3)",
    )
    kvk_api_base_url: str = Field(
        default="https://api.overheid.io/v3/openkvk",
        description="Base URL when KVK_API_KEY is set (default: Overheid.io OpenKvK V3)",
    )

    oecd_api_key: Optional[str] = Field(default=None, description="OECD API key")
    oecd_base_url: str = Field(
        default="https://sdmx.oecd.org/public/rest", description="OECD API base URL"
    )

    ecb_base_url: str = Field(
        default="https://sdw-wsrest.ecb.europa.eu/service", description="ECB API base URL"
    )

    fmp_api_key: Optional[str] = Field(default=None, description="Financial Modeling Prep API key")
    fmp_base_url: str = Field(
        default="https://financialmodelingprep.com/api/v3", description="FMP API base URL"
    )

    # NOTE: Alpha Vantage removed - not implemented (no adapter code exists)
    # Market data comes from Delphi via business_types DB or Titan enrichment

    eurostat_base_url: str = Field(
        default="https://ec.europa.eu/eurostat/api/dissemination",
        description="Eurostat API base URL",
    )

    world_bank_base_url: str = Field(
        default="https://api.worldbank.org/v2", description="World Bank API base URL"
    )

    # Rate Limiting
    rate_limit_per_minute: int = Field(default=60, description="Rate limit per minute")
    rate_limit_per_hour: int = Field(default=1000, description="Rate limit per hour")

    oecd_rate_limit: int = Field(default=100, description="OECD API rate limit per hour")
    ecb_rate_limit: int = Field(default=200, description="ECB API rate limit per hour")
    fmp_rate_limit: int = Field(default=250, description="FMP API rate limit per day")

    # Caching Strategy
    enable_cache: bool = Field(default=True, description="Enable caching")
    market_data_cache_ttl: int = Field(default=3600, description="Market data cache TTL")
    macro_data_cache_ttl: int = Field(default=86400, description="Macro data cache TTL")
    valuation_cache_ttl: int = Field(default=3600, description="Valuation cache TTL")
    comparable_cache_ttl: int = Field(default=7200, description="Comparable data cache TTL")

    # Authentication & Security
    secret_key: str = Field(default="", description="Secret key for sessions")
    algorithm: str = Field(default="HS256", description="JWT algorithm")
    access_token_expire_minutes: int = Field(default=30, description="Access token expiration")

    # JWT Configuration - consolidated (accepts JWT_SECRET or JWT_SECRET_KEY)
    jwt_secret: str = Field(
        default="",
        description="JWT secret key for token validation",
    )
    jwt_algorithm: str = Field(default="HS256", description="JWT algorithm")
    jwt_expire_minutes: int = Field(default=60, description="JWT token expiration")

    # CORS Configuration
    allowed_origins: Union[List[str], str] = Field(
        default=[
            "http://localhost:3000",
            "http://localhost:5173",
            "http://localhost:3001",
            "https://valuation.upswitch.app",  # Production frontend
            "https://www.valuation.upswitch.app",  # Production frontend with www
            "https://upswitch.app",
            "https://valuation.upswitch.app",
            "https://upswitch-valuation-tester.vercel.app",
            "https://upswitch-valuation-tester-git-main-mandiau-matthias-projects.vercel.app",
        ],
        description="Allowed CORS origins",
    )
    cors_allow_credentials: bool = Field(default=True, description="Allow credentials in CORS")
    cors_allow_methods: List[str] = Field(
        default=["GET", "POST", "PUT", "DELETE", "OPTIONS"], description="Allowed CORS methods"
    )
    cors_allow_headers: List[str] = Field(default=["*"], description="Allowed CORS headers")

    # Security Configuration
    allowed_hosts: List[str] = Field(
        default=[
            "localhost",
            "127.0.0.1",
            "healthcheck.railway.app",
            # Starlette: *.example.com matches any subdomain (Titan calls ValuationIQ at *.up.railway.app)
            "*.up.railway.app",
            "*.upswitch.app",
        ],
        description=(
            "TrustedHostMiddleware allowlist. Include healthcheck.railway.app for Railway probes; "
            "*.up.railway.app for public Railway URLs; *.upswitch.app for custom domains. "
            "Override via ALLOWED_HOSTS if needed (JSON array)."
        ),
    )

    # Valuation Engine Configuration
    default_projection_years: int = Field(default=5, description="Default DCF projection years")
    default_terminal_growth_rate: Decimal = Field(
        default=0.02, description="Default terminal growth rate"
    )
    default_market_risk_premium: Decimal = Field(
        default=0.06, description="Default market risk premium"
    )
    default_small_cap_premium: Decimal = Field(
        default=0.03, description="Default small cap premium"
    )

    # Discounts & Adjustments
    private_company_discount: Decimal = Field(default=0.25, description="Private company discount")
    size_discount_small: Decimal = Field(
        default=0.30, description="Size discount for small companies"
    )
    size_discount_medium: Decimal = Field(
        default=0.20, description="Size discount for medium companies"
    )
    size_discount_large: Decimal = Field(
        default=0.10, description="Size discount for large companies"
    )
    liquidity_discount: Decimal = Field(default=0.25, description="Liquidity discount")

    # Risk Assessment Thresholds
    high_risk_threshold: int = Field(default=70, description="High risk threshold")
    medium_risk_threshold: int = Field(default=40, description="Medium risk threshold")
    low_risk_threshold: int = Field(default=20, description="Low risk threshold")

    # Confidence Scoring
    high_confidence_score: int = Field(default=8, description="High confidence score threshold")
    medium_confidence_score: int = Field(default=5, description="Medium confidence score threshold")

    # Value Chain Validation Tolerances
    value_chain_tolerance_percent: Decimal = Field(
        default=0.1,
        description="Value chain validation tolerance percentage (0.1 = 0.1%)",
    )
    rounding_warning_threshold_percent: Decimal = Field(
        default=5.0,
        description="Rounding impact warning threshold percentage (5.0 = 5%)",
    )
    # Defense-in-depth max drift the final ValuationValidator will silently
    # repair when it detects ordering drift in the (low, mid, high) band.
    # Above this fraction, repair is refused and a hard error surfaces so
    # we don't paper over genuinely broken upstream state.
    #
    # M&A defensibility note: any silent rewrite of the central estimate
    # (mid) above ~5% is materially misleading. We default to 10% as a
    # pragmatic middle: tight enough to surface real bugs, loose enough
    # to absorb rounding edge cases at small valuations (e.g. €100
    # rounding on €1K mid = 10%). For institutional / advisor-facing
    # deployments, tighten to 0.05 (5%) or lower.
    range_repair_max_mid_drift: Decimal = Field(
        default=Decimal("0.10"),
        description="Max fractional mid drift the validator will silently repair (0.10 = 10%)",
    )
    # ── M&A defensibility invariant thresholds ──────────────────────────
    # These tune the WARNING-level invariants in
    # ``ValuationValidator._validate_ma_invariants``. The defaults match
    # standard M&A practitioner expectations and Damodaran's industry
    # bounds. Tighten for institutional / advisor-facing deployments.
    ma_invariant_ev_equity_bridge_tolerance: Decimal = Field(
        default=Decimal("0.01"),
        description="EV ≈ Equity + Net Debt tolerance as fraction of EV (0.01 = 1%)",
    )
    # Tightened to McKinsey / Damodaran practitioner band. Default
    # [1.0x, 25x] catches obvious methodology errors while leaving room
    # for distressed (1-2x) and high-growth tech (15-25x). Override per
    # industry deployment when needed.
    ma_invariant_implied_ebitda_multiple_min: Decimal = Field(
        default=Decimal("1.0"),
        description="Lower bound on implied EV/EBITDA — below this signals miscalibration or distress",
    )
    ma_invariant_implied_ebitda_multiple_max: Decimal = Field(
        default=Decimal("25.0"),
        description="Upper bound on implied EV/EBITDA — above this signals miscalibration",
    )
    # Cross-method divergence: the EBITDA path and SDE path should
    # triangulate within this fraction. Wide divergence signals either
    # bad EBITDA normalization or wrong methodology selection.
    ma_invariant_ebitda_sde_max_divergence: Decimal = Field(
        default=Decimal("1.0"),  # 100% — i.e. ratio ≤ 2x or ≥ 0.5x
        description="Max fractional divergence between EBITDA-path and SDE-path mid (1.0 = 100%)",
    )
    # Hybrid cross-method divergence: the DCF leg and the market-multiple leg
    # should triangulate within this fraction. A DCF leg that dwarfs the market
    # leg (an intrinsic value implying a multiple far above the benchmark, built
    # on fallback forecast assumptions) is a miscalibration signal — and is most
    # dangerous precisely when an advisor has weighted DCF heavily. Default 1.0
    # (100%, i.e. one leg ≤ 2× the other) mirrors the EBITDA/SDE divergence band.
    ma_invariant_dcf_market_max_divergence: Decimal = Field(
        default=Decimal("1.0"),
        description="Max fractional divergence between the DCF-leg EV and the market-multiple-leg EV in a hybrid (1.0 = 100%, i.e. one ≤ 2× the other)",
    )
    # Band-width sanity: (high - low) / mid should be in this range.
    # Below 10% is overconfident; above 250% is uselessly wide.
    ma_invariant_band_width_min: Decimal = Field(
        default=Decimal("0.10"),
        description="Min fractional band width (high-low)/mid — below this signals overconfidence",
    )
    ma_invariant_band_width_max: Decimal = Field(
        default=Decimal("2.50"),
        description="Max fractional band width (high-low)/mid — above this signals uselessly wide range",
    )
    # Asking-price markup sanity: 0% ≤ markup ≤ 50%. Negative or
    # extremely high markups indicate config or override errors.
    ma_invariant_asking_markup_min: Decimal = Field(
        default=Decimal("0.0"),
        description="Min fractional asking-price markup over mid (0.0 = no markup)",
    )
    ma_invariant_asking_markup_max: Decimal = Field(
        default=Decimal("0.50"),
        description="Max fractional asking-price markup over mid (0.50 = 50% above mid)",
    )
    ma_invariant_high_confidence_threshold: int = Field(
        default=80,
        description="Confidence score considered 'high' for thinness check (default 80%)",
    )
    ma_invariant_thin_data_year_threshold: int = Field(
        default=1,
        description="Years-of-data considered 'thin' (default 1 year)",
    )

    # AI/ML Configuration
    risk_model_path: str = Field(
        default="models/risk_assessment_model.pkl", description="Risk model path"
    )
    comps_model_path: str = Field(
        default="models/comparables_matcher_model.pkl", description="Comps model path"
    )
    data_quality_model_path: str = Field(
        default="models/data_quality_model.pkl", description="Data quality model path"
    )

    enable_feature_store: bool = Field(default=False, description="Enable ML feature store")
    feature_store_redis_db: int = Field(default=1, description="Redis DB for feature store")

    enable_shap_explanations: bool = Field(default=True, description="Enable SHAP explanations")
    shap_sample_size: int = Field(default=100, description="SHAP sample size")

    # Report Generation
    enable_pdf_generation: bool = Field(default=True, description="Enable PDF report generation")
    pdf_template_path: str = Field(
        default="templates/valuation_report.html", description="PDF template path"
    )
    pdf_logo_path: str = Field(default="assets/upswitch_logo.png", description="PDF logo path")

    enable_excel_export: bool = Field(default=True, description="Enable Excel export")
    enable_json_export: bool = Field(default=True, description="Enable JSON export")
    enable_csv_export: bool = Field(default=True, description="Enable CSV export")

    # Monitoring & Observability
    enable_metrics: bool = Field(default=True, description="Enable Prometheus metrics")
    expose_metrics_in_production: bool = Field(
        default=False,
        description=(
            "Expose Prometheus /metrics in production. Keep false unless the service "
            "is behind a private network, gateway auth, or an allowlisted metrics scraper."
        ),
    )
    metrics_port: int = Field(default=9090, description="Metrics port")

    log_format: str = Field(default="json", description="Log format: json or text")
    log_output: str = Field(default="stdout", description="Log output: stdout or file")
    log_file_path: str = Field(default="logs/valuation_engine.log", description="Log file path")

    sentry_dsn: Optional[str] = Field(default=None, description="Sentry DSN for error tracking")
    sentry_environment: str = Field(default="development", description="Sentry environment")
    sentry_traces_sample_rate: Decimal = Field(default=0.1, description="Sentry traces sample rate")

    # Performance Settings
    db_pool_size: int = Field(default=20, description="Database pool size")
    db_max_overflow: int = Field(default=10, description="Database max overflow")
    db_pool_timeout: int = Field(default=30, description="Database pool timeout")

    max_concurrent_requests: int = Field(default=100, description="Max concurrent requests")
    request_timeout: int = Field(default=30, description="Request timeout in seconds")

    # Valuation Calculation Timeout
    valuation_timeout_seconds: Decimal = Field(
        default=90.0,
        description="Valuation calculation timeout in seconds (default: 90s, was 30s)",
    )

    enable_background_jobs: bool = Field(default=True, description="Enable background jobs")
    background_job_queue: str = Field(default="redis", description="Background job queue")

    # Validation Framework Configuration
    validation_enabled: bool = Field(
        default=False,
        description="Enable validation framework for Q&A answers",
    )
    validation_confidence_threshold: Decimal = Field(
        default=Decimal("0.85"),
        description="Minimum confidence threshold for validation (0.0-1.0)",
    )

    # Data Refresh Intervals
    market_data_refresh_interval: int = Field(
        default=3600, description="Market data refresh interval"
    )
    macro_data_refresh_interval: int = Field(
        default=86400, description="Macro data refresh interval"
    )
    comparable_data_refresh_interval: int = Field(
        default=604800, description="Comparable data refresh interval"
    )

    # Testing & Development
    test_database_url: str = Field(
        default="postgresql://localhost:5432/upswitch_valuation_test",
        description="Test database URL",
    )
    test_mode: bool = Field(default=False, description="Test mode")
    mock_external_apis: bool = Field(default=False, description="Mock external APIs for testing")
    load_test_fixtures: bool = Field(default=False, description="Load test fixtures")

    # Feature Flags
    enable_dcf_valuation: bool = Field(default=True, description="Enable DCF valuation")
    enable_multiples_valuation: bool = Field(default=True, description="Enable multiples valuation")
    enable_asset_based_valuation: bool = Field(
        default=True, description="Enable asset-based valuation"
    )
    enable_ai_risk_assessment: bool = Field(default=True, description="Enable AI risk assessment")
    enable_scenario_analysis: bool = Field(default=True, description="Enable scenario analysis")
    enable_continuous_updates: bool = Field(default=False, description="Enable continuous updates")

    # Business Rules
    min_historical_years: int = Field(default=3, description="Minimum historical years required")
    require_audited_financials: bool = Field(
        default=False, description="Require audited financials"
    )
    require_industry_classification: bool = Field(
        default=True, description="Require industry classification"
    )

    max_valuation_amount: Decimal = Field(default=1_000_000_000, description="Max valuation amount")
    min_valuation_amount: Decimal = Field(default=10_000, description="Min valuation amount")
    max_debt_to_equity_ratio: Decimal = Field(default=5.0, description="Max debt to equity ratio")

    # Internationalization
    default_language: str = Field(default="en", description="Default language")
    supported_languages: List[str] = Field(
        default=["en", "de", "fr", "nl", "es"], description="Supported languages"
    )
    default_currency: str = Field(default="EUR", description="Default currency")
    default_timezone: str = Field(default="Europe/Amsterdam", description="Default timezone")

    # Contact & Support
    support_email: str = Field(default="support@upswitch.com", description="Support email")
    admin_email: str = Field(default="admin@upswitch.com", description="Admin email")

    # PDF Generation Configuration - Bank-Grade Compliance
    pdf_a_level: str = Field(
        default="3B", description="PDF/A compliance level (3B=basic, 3A=accessible, 3U=Unicode)"
    )
    pdf_ua_enabled: bool = Field(default=True, description="Enable PDF/UA accessibility features")
    pdf_encryption_enabled: bool = Field(
        default=True, description="Enable PDF encryption with AES-256"
    )
    pdf_owner_password: Optional[str] = Field(
        default=None,
        description="PDF owner password (auto-generated if None)",
    )
    pdf_allow_print: bool = Field(default=True, description="Allow printing of PDFs")
    pdf_allow_copy: bool = Field(
        default=False, description="Allow text extraction/copying from PDFs"
    )
    pdf_allow_modify: bool = Field(default=False, description="Allow modification of PDFs")
    pdf_watermark_enabled: bool = Field(
        default=True, description="Enable confidentiality watermark"
    )
    pdf_watermark_text: str = Field(
        default="Strictly Private & Confidential", description="Watermark text for PDFs"
    )
    pdf_image_dpi: int = Field(default=300, description="Image resolution for PDF generation (DPI)")
    pdf_compression_level: int = Field(
        default=6, description="PDF compression level (0-9, balance size vs quality)"
    )
    pdf_validate_on_generation: bool = Field(
        default=True, description="Validate PDF compliance after generation"
    )
    pdf_fail_on_validation_error: bool = Field(
        default=False, description="Fail PDF generation if validation errors occur"
    )

    @field_validator("environment")
    @classmethod
    def validate_environment(cls, v: str) -> str:
        """Validate environment value"""
        allowed_environments = ["development", "staging", "production", "test"]
        if v not in allowed_environments:
            raise ValueError(f"Environment must be one of {allowed_environments}")
        return v

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validate log level"""
        allowed_levels = ["debug", "info", "warning", "error", "critical"]
        if v.lower() not in allowed_levels:
            raise ValueError(f"Log level must be one of {allowed_levels}")
        return v.lower()

    @field_validator("api_middleware_log_mode")
    @classmethod
    def validate_api_middleware_log_mode(cls, v: str) -> str:
        allowed = ("full", "minimal")
        if v.lower() not in allowed:
            raise ValueError(f"api_middleware_log_mode must be one of {allowed}")
        return v.lower()

    @field_validator("host", mode="before")
    @classmethod
    def validate_host(cls, v: str) -> str:
        configured_host = str(v or "").strip()
        return configured_host or resolve_default_server_host()

    @field_validator("allowed_origins")
    @classmethod
    def validate_allowed_origins(cls, v: Union[List[str], str]) -> List[str]:
        """Convert comma-separated string to a stable, de-duplicated origin list."""
        if isinstance(v, str):
            candidates = [origin.strip() for origin in v.split(",") if origin.strip()]
        else:
            candidates = [origin.strip() for origin in v if origin.strip()]

        return list(dict.fromkeys(candidates))

    @model_validator(mode="after")
    def validate_production_security(self):
        """Fail fast on production settings that expose secrets or sensitive request data."""
        if not self.is_production:
            return self

        insecure_secret_values = {"", "change-me-in-production"}
        missing = [
            field_name
            for field_name in ("secret_key", "jwt_secret")
            if str(getattr(self, field_name) or "").strip() in insecure_secret_values
        ]
        if missing:
            joined = ", ".join(missing)
            raise ValueError(f"Production requires explicit secret values for: {joined}")
        if self.debug:
            raise ValueError("DEBUG must be false in production")
        if self.request_body_logging:
            raise ValueError("REQUEST_BODY_LOGGING must be false in production")
        self._validate_production_cors()
        return self

    def _validate_production_cors(self) -> None:
        """Reject permissive CORS settings before a production process can boot."""
        unsafe_origins = []
        for origin in self.allowed_origins:
            parsed = urlparse(origin)
            hostname = parsed.hostname or ""
            is_loopback = hostname in {"localhost", "127.0.0.1", "::1"} or hostname.endswith(
                ".localhost"
            )
            if "*" in origin or parsed.scheme != "https" or not parsed.netloc or is_loopback:
                unsafe_origins.append(origin)

        if unsafe_origins:
            joined = ", ".join(unsafe_origins)
            raise ValueError(
                "Production CORS allowed_origins must be explicit https origins; "
                f"unsafe origins: {joined}"
            )

    @property
    def is_development(self) -> bool:
        """Check if running in development"""
        return self.environment == "development"

    @property
    def is_production(self) -> bool:
        """Check if running in production"""
        return self.environment == "production"

    @property
    def is_testing(self) -> bool:
        """Check if running in test mode"""
        return self.environment == "test" or self.test_mode

    @property
    def is_stateless(self) -> bool:
        """
        Check if running in stateless mode (Brain & Muscle Architecture).

        When True, ValuationIQ operates as a pure calculation engine:
        - All data comes from Titan via stateless API requests
        - No database access
        - No Redis session state
        - No AI/LLM calls (handled by Titan)

        Use /api/v2/stateless/* endpoints for stateless mode.
        """
        return self.stateless_mode or (self.require_external_data and self.database_optional)

    def get_database_url(self, use_test: bool = False) -> str:
        """Get appropriate database URL"""
        if use_test or self.is_testing:
            return self.test_database_url
        return self.database_url


# Global settings instance
settings = Settings()


# Helper function to get settings
def get_settings() -> Settings:
    """Get application settings instance"""
    return settings
