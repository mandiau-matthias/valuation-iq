"""
Step 1 Orchestrator

Orchestrates the main execution flow for Step 1 Input Validation.
"""

from decimal import Decimal
from typing import Any, Dict

from src.utils.decimal_helpers import from_decimal, to_decimal
from src.utils.logging import get_logger

from ...base_step import StepInput, StepOutput, StepStatus
from ..builders import Step1MetadataBuilder, Step1ResultBuilder
from ..calculators import Step1MarginCalculator
from ..extractors import Step1CompanyExtractor, Step1MetricsExtractor
from ..validators import Step1Validator

logger = get_logger(__name__)


class Step1Orchestrator:
    """Orchestrates the main execution flow for Step 1."""

    def __init__(
        self,
        step_name: str,
        metrics_extractor: Step1MetricsExtractor,
        company_extractor: Step1CompanyExtractor,
        margin_calculator: Step1MarginCalculator,
        validator: Step1Validator,
        result_builder: Step1ResultBuilder,
        metadata_builder: Step1MetadataBuilder,
    ):
        """
        Initialize the orchestrator.

        Args:
            step_name: Step name for StepOutput
            metrics_extractor: Step1MetricsExtractor instance
            company_extractor: Step1CompanyExtractor instance
            margin_calculator: Step1MarginCalculator instance
            validator: Step1Validator instance
            result_builder: Step1ResultBuilder instance
            metadata_builder: Step1MetadataBuilder instance
        """
        self.step_name = step_name
        self.metrics_extractor = metrics_extractor
        self.company_extractor = company_extractor
        self.margin_calculator = margin_calculator
        self.validator = validator
        self.result_builder = result_builder
        self.metadata_builder = metadata_builder

    async def orchestrate_execution(
        self, input_data: StepInput, request: any, context: Dict[str, Any]
    ) -> StepOutput:
        """
        Orchestrate the main execution flow.

        Args:
            input_data: StepInput with request and context
            request: Valuation request
            context: Step context dictionary

        Returns:
            StepOutput with calculation results
        """
        logger.info(
            "▶️  Executing Step 1: Input Data & Business Profile",
            extra={
                "step_number": 1,
                "step_name": self.step_name,
                "company": getattr(request, "company_name", "N/A"),
                "has_current_year_data": bool(getattr(request, "current_year_data", None)),
                "current_year_data_revenue": (
                    getattr(getattr(request, "current_year_data", None), "revenue", None)
                    if getattr(request, "current_year_data", None)
                    else None
                ),
                "current_year_data_ebitda": (
                    getattr(getattr(request, "current_year_data", None), "ebitda", None)
                    if getattr(request, "current_year_data", None)
                    else None
                ),
            },
        )

        # Extract financial metrics
        revenue, ebitda, using_weighted, weighting_method = (
            self.metrics_extractor.extract_financial_metrics(request, context)
        )

        # Validate revenue (warn but don't fail)
        self.validator.validate_revenue(revenue, using_weighted)

        # Calculate EBITDA margin
        ebitda_margin = self.margin_calculator.calculate_ebitda_margin(revenue, ebitda)

        # Extract company information
        company_info = self.company_extractor.extract_company_info(request)

        # DEBUG: "Step 1: Input Data & Business Profile - Calculation Complete"
        # below is the canonical exit log; this line is the per-source detail.
        logger.debug(
            f"✅ Step 1: Input validation complete (using {'weighted' if using_weighted else 'current year'} metrics)",
            extra={
                "step_number": 1,
                "revenue": revenue,
                "ebitda": ebitda,
                "ebitda_margin": round(ebitda_margin, 2),
                "using_weighted_metrics": using_weighted,
                "weighting_method": weighting_method,
                "company_name": company_info.get("company_name"),
                "industry": company_info.get("industry"),
                "country": company_info.get("country"),
                "founded_year": company_info.get("founded_year"),
                "num_employees": company_info.get("num_employees"),
            },
        )

        # Comprehensive summary logging for auditability
        weighted_metrics = context.get("weighted_metrics", {})
        logger.info(
            "📊 Step 1: Input Data & Business Profile - Calculation Complete",
            extra={
                "step_number": 1,
                "step_name": "Input Data & Business Profile",
                "status": "COMPLETED",
                "inputs": {
                    "has_current_year_data": bool(getattr(request, "current_year_data", None)),
                    "has_weighted_metrics": bool(weighted_metrics),
                    "has_historical_data": bool(getattr(request, "historical_years_data", None)),
                },
                "calculation": {
                    "methodology": (
                        "McKinsey Weighted Metrics" if using_weighted else "Current Year Only"
                    ),
                    "formula": (
                        "Weighted = Year1×1/6 + Year2×2/6 + Year3×3/6"
                        if using_weighted
                        else "Current Year Value"
                    ),
                    "weighting_method": weighting_method,
                    "ebitda_margin_calculation": (
                        f"EBITDA Margin = (EBITDA / Revenue) × 100"
                        if ebitda is not None and revenue > 0
                        else "N/A"
                    ),
                },
                "outputs": {
                    "revenue": revenue,
                    "ebitda": ebitda,
                    "ebitda_margin": ebitda_margin,
                    "company_info": company_info,
                },
                "metadata": {
                    "using_weighted_metrics": using_weighted,
                    "weighting_method": weighting_method,
                    "validation_passed": True,
                    "normalized_fields": ["revenue", "ebitda"],
                    "academic_reference": "McKinsey Valuation (2015), Chapter 3: Financial Statement Analysis",
                },
            },
        )

        # Run trial balance anomaly scanner on historical + current year data
        anomaly_scan_result = None
        try:
            from src.domain.trial_balance_anomaly_scanner import TrialBalanceAnomalyScanner
            historical = getattr(request, "historical_years_data", None) or []
            current_yd = getattr(request, "current_year_data", None)
            if len(historical) >= 2:
                scanner = TrialBalanceAnomalyScanner(z_threshold=2.0, min_years=3)
                anomaly_scan_result = scanner.scan(historical, current_yd)
                if anomaly_scan_result.has_anomalies:
                    logger.info(
                        "Trial balance anomaly scan found flags",
                        anomaly_count=len(anomaly_scan_result.anomaly_flags),
                        accounts=[f.account for f in anomaly_scan_result.anomaly_flags],
                    )
        except Exception as scan_err:
            logger.warning("Trial balance anomaly scan failed (non-critical)", error=str(scan_err))

        # Build result dictionary
        result_data = self.result_builder.build_result_dict(
            revenue, ebitda, ebitda_margin, company_info, using_weighted, weighting_method
        )

        if anomaly_scan_result is not None:
            result_data["trial_balance_anomalies"] = anomaly_scan_result.to_dict()

        # Build metadata dictionary
        metadata = self.metadata_builder.build_metadata_dict(
            revenue, ebitda, using_weighted, weighting_method
        )

        # DEBUG: per-step diagnostic.
        current_data = request.current_year_data
        logger.debug(
            "🔍 Step 1: Result data prepared for downstream steps",
            extra={
                "step_number": 1,
                "result_revenue": result_data["revenue"],
                "result_ebitda": result_data["ebitda"],
                "result_ebitda_margin": result_data["ebitda_margin"],
                "revenue_source": (
                    "current_year_data"
                    if current_data and (getattr(current_data, "revenue", 0) or 0) > 0
                    else ("weighted_metrics" if using_weighted else "none")
                ),
                "note": "This data will be used by Step 3 for base EV calculation",
            },
        )

        return StepOutput(
            step_number=1,
            step_name=self.step_name,
            status=StepStatus.COMPLETED,
            result=result_data,
            metadata=metadata,
        )
