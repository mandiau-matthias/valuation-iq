"""
API Request/Response Schemas for Valuation Engine.

These schemas define the contract between the API and clients,
providing validation, documentation, and type safety.
"""

from src.api.business_type_mix import normalize_business_type_mix_fields
from src.api.legacy_industry_validation import get_valid_industries
from src.api.legacy_input_schemas import (
    BalanceSheetAdjustmentInput,
    HoldingConsolidationInput,
    OwnershipSummary,
    ShareholderRosterEntry,
    TaxLatencyInput,
    YearDataInput,
)
from src.api.legacy_quick_schemas import (
    ErrorResponse,
    HealthResponse,
    QuickValuationRequest,
    QuickValuationResponse,
)
from src.api.legacy_request_schemas import ValuationRequest
from src.api.legacy_response_schemas import (
    DCFValuationResponse,
    FinancialMetricsResponse,
    MCPInsightsResponse,
    MethodologySelection,
    MonteCarloResults,
    MultiplePipeline,
    MultiplePipelineStage,
    MultiplesValuationResponse,
    OwnerCompensationSwap,
    SmallFirmAdjustments,
    ValuationDataQuality,
    ValuationResponse,
)
from src.api.legacy_schema_validation import (
    normalize_business_model_field,
    normalize_enrichment_multiple_distributions_request,
    normalize_historical_ebitda_weighting_mode_field,
    normalize_historical_ebitda_weights_field,
    normalize_key_metrics_field,
    normalize_real_estate_treatment_field,
    sanitize_industry,
    validate_advisor_controls_request,
    validate_historical_years_order,
    validate_industry_field,
    validate_year_buckets_request,
)
from src.api.report_data_schemas import (
    AccountantBranding,
    ComparableTransaction,
    EBITDAAdjustment,
    ValuationMetric,
    ValuationReportData,
    YearlyEBITDA,
)
from src.domain.models import BusinessModel, ComparableCompany, ConfidenceLevel, IndustryCode
from src.domain.owner_models.owner_dependency import OwnerDependencyFactors, OwnerDependencyResult
from src.domain.sellability_models import SellabilityAssessmentRender
from src.domain.startup_valuation.schemas import StartupInputs
from src.domain.transparency import (
    DataProvenance,
    IndustryBenchmark,
    MarketDataDetails,
    TransparencyData,
    ValidationReport,
)
from src.utils.decimal_helpers import from_decimal, to_decimal
from src.utils.fiscal_year import get_max_confirmable_year

JsonObject = dict[str, object]
