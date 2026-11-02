"""Quick valuation orchestration isolated from the main valuation facade."""

from __future__ import annotations

import asyncio
import uuid
from decimal import Decimal
from typing import Awaitable, Callable, Optional, Protocol

from src.api.routes.valuation.benchmark_contract_utils import (
    REQUIRED_BENCHMARK_PROVENANCE_FIELDS,
    diagnose_request_benchmark_contract,
    extract_request_resolved_benchmark_contract,
    request_allows_untrusted_multiples_fallback,
)
from src.api.routes.valuation.valuation_types import BusinessType, ValuationMethod
from src.api.schemas import QuickValuationRequest, QuickValuationResponse
from src.config.valuation_constants import get_asking_price_markup
from src.utils.country_code import normalize_iso3166_alpha2
from src.utils.exceptions import (
    CalculationError,
    ConfigurationError,
    DatabaseError,
    MultiplesCalculationError,
)


class QuickValuationLogger(Protocol):
    def info(self, message: str, *args: object, **kwargs: object) -> None: ...

    def error(self, message: str, *args: object, **kwargs: object) -> None: ...


QuickMethodologySelector = Callable[[BusinessType, str], Awaitable[ValuationMethod]]


def quick_request_display_name(request: object) -> str:
    """API schema uses company_name; progressive QuickValuationRequest uses business_name."""
    name = getattr(request, "company_name", None) or getattr(request, "business_name", None)
    return str(name).strip() if name else "Quick Valuation"


async def determine_quick_valuation_methodology(
    business_type: BusinessType, industry: str
) -> ValuationMethod:
    """Determine appropriate quick valuation methodology."""
    return ValuationMethod.MULTIPLES


class QuickValuationProcessor:
    """Process quick valuation requests without bloating the main facade."""

    def __init__(
        self,
        *,
        quick_calculator: object,
        business_adjuster: object,
        logger: QuickValuationLogger,
    ) -> None:
        self.quick_calculator = quick_calculator
        self.business_adjuster = business_adjuster
        self.logger = logger

    async def process(
        self,
        request: QuickValuationRequest,
        context: Optional[dict[str, object]] = None,
        methodology_selector: QuickMethodologySelector = determine_quick_valuation_methodology,
    ) -> QuickValuationResponse:
        """Process quick valuation request."""
        _ = context
        try:
            industry = (
                request.industry.value
                if hasattr(request.industry, "value")
                else str(request.industry)
            )
            self.logger.info(
                "🚀 Processing quick valuation (refactored)",
                extra={
                    "company": quick_request_display_name(request),
                    "industry": industry,
                },
            )

            valuation_id = str(uuid.uuid4())
            methodology = await methodology_selector(request.business_type, request.industry)

            self.logger.info(
                f"📊 Methodology selected: {methodology.value if hasattr(methodology, 'value') else str(methodology)}"
            )

            allow_untrusted_multiples_fallback = request_allows_untrusted_multiples_fallback(
                request
            )
            benchmark_contract = extract_request_resolved_benchmark_contract(request)
            if not allow_untrusted_multiples_fallback and benchmark_contract is None:
                raise MultiplesCalculationError(
                    "Resolved benchmark contract required for quick valuation. "
                    "ValuationIQ will not publish DB, generic, or hardcoded quick "
                    "multiples unless allow_untrusted_multiples_fallback=true is explicit.",
                    step="quick_valuation_preflight",
                    calculation_type="Quick Valuation",
                    context={
                        "code": "BENCHMARK_CONTRACT_REQUIRED",
                        "country_code": getattr(request, "country_code", None),
                        "business_type_id": getattr(request, "business_type_id", None),
                        "required_contract_fields": list(REQUIRED_BENCHMARK_PROVENANCE_FIELDS),
                        **diagnose_request_benchmark_contract(request),
                    },
                )

            business_type_id = getattr(request, "business_type_id", None)
            quick_country = normalize_iso3166_alpha2(getattr(request, "country_code", None))
            base_valuation = await self.quick_calculator.calculate(
                request.revenue,
                request.ebitda,
                industry,
                methodology,
                business_type_id,
                country_code=quick_country,
                benchmark_contract=benchmark_contract,
                allow_untrusted_multiples_fallback=allow_untrusted_multiples_fallback,
            )

            self.logger.info(f"💰 Base valuation: {base_valuation:,.0f}")

            adjusted_valuation = await self.business_adjuster.apply_adjustments(
                base_valuation,
                request.business_type,
                industry,
            )

            self.logger.info(f"🎨 Adjusted valuation: {adjusted_valuation:,.0f}")

            value_range_task = self.quick_calculator.calculate_value_range(
                adjusted_valuation,
                request.business_type,
                industry,
            )
            confidence_task = self.quick_calculator.calculate_confidence_score(
                request, adjusted_valuation, methodology
            )
            key_factors_task = self.quick_calculator.generate_key_factors(
                request, adjusted_valuation, methodology
            )

            value_range, confidence_score, _key_factors = await asyncio.gather(
                value_range_task, confidence_task, key_factors_task
            )

            self.logger.info(f"🎯 Confidence: {confidence_score*100:.0f}%")

            await self.quick_calculator.generate_recommendations(
                request, adjusted_valuation, confidence_score
            )

            response = QuickValuationResponse(
                valuation_range_low=value_range.get("low", adjusted_valuation * Decimal("0.8")),
                valuation_range_mid=adjusted_valuation,
                valuation_range_high=value_range.get("high", adjusted_valuation * Decimal("1.2")),
                recommended_asking_price=adjusted_valuation
                * get_asking_price_markup(
                    "medium",
                    advisor_override_pct=getattr(request, "asking_price_buffer_pct", None),
                ),
                confidence="medium" if confidence_score > Decimal("0.6") else "low",
                confidence_score=int(confidence_score * 100),
                methodology_used=methodology,
                note="This is a quick estimate. For a comprehensive valuation, please provide complete financial data.",
                benchmark_contract=benchmark_contract,
                benchmark_provenance=benchmark_contract,
                benchmark_id=benchmark_contract.get("benchmark_id") if benchmark_contract else None,
                dataset_version_id=(
                    benchmark_contract.get("dataset_version_id") if benchmark_contract else None
                ),
                benchmark_country_code=(
                    benchmark_contract.get("country_code") if benchmark_contract else None
                ),
                benchmark_region_key=(
                    benchmark_contract.get("region_key") if benchmark_contract else None
                ),
                benchmark_tier=benchmark_contract.get("tier") if benchmark_contract else None,
                benchmark_walk_step=(
                    benchmark_contract.get("walk_step") if benchmark_contract else None
                ),
                benchmark_sample_size=(
                    benchmark_contract.get("sample_size") if benchmark_contract else None
                ),
                benchmark_confidence_band=(
                    benchmark_contract.get("confidence_band") if benchmark_contract else None
                ),
                benchmark_source_mix=(
                    benchmark_contract.get("source_mix") if benchmark_contract else None
                ),
                benchmark_evidence_summary=(
                    benchmark_contract.get("evidence_summary") if benchmark_contract else None
                ),
                benchmark_published_at=(
                    benchmark_contract.get("published_at") if benchmark_contract else None
                ),
                benchmark_methodology_version=(
                    benchmark_contract.get("methodology_version") if benchmark_contract else None
                ),
            )

            self.logger.info(
                "✅ Quick valuation processed successfully",
                extra={
                    "valuation_id": valuation_id,
                    "valuation": adjusted_valuation,
                    "confidence": confidence_score,
                },
            )

            return response

        except (
            MultiplesCalculationError,
            CalculationError,
            DatabaseError,
            ConfigurationError,
        ):
            raise
        except Exception as exc:
            self.logger.error(
                "❌ Quick valuation failed",
                extra={
                    "error": str(exc),
                    "company": quick_request_display_name(request),
                    "error_type": type(exc).__name__,
                },
                exc_info=True,
            )
            raise MultiplesCalculationError(
                f"Unexpected error in quick valuation: {exc}",
                step="quick_valuation_orchestration",
                calculation_type="Quick Valuation",
                context={
                    "company": quick_request_display_name(request),
                    "error_type": type(exc).__name__,
                },
            ) from exc


__all__ = [
    "QuickValuationProcessor",
    "determine_quick_valuation_methodology",
    "quick_request_display_name",
]
