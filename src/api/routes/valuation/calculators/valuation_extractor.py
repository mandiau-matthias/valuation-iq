"""
Valuation Extractor

Handles extraction of valuation values and multiples from step results with
validation. Concrete business-type valuation multiples must already come from
the resolved benchmark contract.

Responsibilities:
- Extract enterprise value, equity value, and valuation range
- Extract revenue and EBITDA multiples
- Provide fallback values when primary sources are missing or invalid
- Validate all extracted values
"""

from decimal import Decimal
from typing import Callable, Dict, Optional

from src.api.routes.valuation.benchmark_contract_utils import extract_resolved_benchmark_contract
from src.api.routes.valuation.benchmark_contract_utils import (
    request_allows_untrusted_multiples_fallback as _request_allows_untrusted_multiples_fallback,
)
from src.api.schemas import ValuationRequest
from src.utils.decimal_helpers import from_decimal, to_decimal
from src.utils.valuation_logger import ValuationLogger

from .extractors import (
    EnterpriseValueCalculator,
    ValuationFallbackCalculator,
    ValuationRangeExtractor,
    ValuationValidator,
)

logger = ValuationLogger(__name__)


def _resolved_benchmark_contract(step_2: Dict[str, object]) -> Optional[Dict[str, object]]:
    return extract_resolved_benchmark_contract(step_2)


def _requires_resolved_contract(request: ValuationRequest) -> bool:
    return not _request_allows_untrusted_multiples_fallback(request)


_REVENUE_MULTIPLE_FIELDS = ("ev_revenue_multiple", "ev_revenue", "revenue_multiple")
_EBITDA_MULTIPLE_FIELDS = ("ev_ebitda_multiple", "ev_ebitda_ratio", "ev_ebitda")


def _request_business_type_id(request: ValuationRequest) -> str:
    return request.business_type_id if hasattr(request, "business_type_id") else "general-business"


def _extract_multiple_from_fields(
    step_2: Dict[str, object],
    fields: tuple[str, ...],
) -> tuple[object | None, str | None]:
    for field in fields:
        value = step_2.get(field)
        if value:
            return value, field
    return None, None


def _multiple_is_missing_or_invalid(value: object | None) -> bool:
    if not value:
        return True
    try:
        return to_decimal(value) <= Decimal("0")
    except (TypeError, ValueError):
        return True


class ValuationExtractor:
    """Handles extraction of valuation values and multiples with fallbacks."""

    def __init__(self, get_industry_default_fn: Callable[[str, str], Decimal], logger_instance):
        """
        Initialize the extractor with a reference to the industry defaults function.

        Args:
            get_industry_default_fn: Function to get industry default multiples
            logger_instance: Logger instance from the parent calculator
        """
        self.get_industry_default_multiple = get_industry_default_fn
        self.logger = logger_instance

        # Initialize extractors (SRP: Single Responsibility Principle)
        self.range_extractor = ValuationRangeExtractor(self.logger)
        self.fallback_calculator = ValuationFallbackCalculator(self.logger)
        self.enterprise_calculator = EnterpriseValueCalculator(self.logger)
        self.validator = ValuationValidator(self.logger)

    def _fallback_multiple(self, request: ValuationRequest, metric: str) -> Decimal:
        return self.get_industry_default_multiple(
            _request_business_type_id(request),
            metric,
        )

    def _extract_or_fallback_multiple(
        self,
        *,
        step_2: Dict[str, object],
        request: ValuationRequest,
        fields: tuple[str, ...],
        metric: str,
        display_name: str,
        require_contract: bool,
        missing_error: str,
    ) -> tuple[object | None, str | None]:
        multiple_raw, field_found = _extract_multiple_from_fields(step_2, fields)
        if _multiple_is_missing_or_invalid(multiple_raw):
            if require_contract:
                raise ValueError(missing_error)
            fallback_multiple = self._fallback_multiple(request, metric)
            logger.warning(
                f"⚠️ {display_name} is None/0 in step_2, using industry fallback",
                extra={
                    f"step_2_{display_name}": multiple_raw,
                    "step_2_keys": list(step_2.keys()) if step_2 else [],
                    "field_tried": field_found,
                    "fallback_value": fallback_multiple,
                    "all_step_2_values": step_2 if step_2 else None,
                },
            )
            return fallback_multiple, field_found

        logger.debug(
            f"✅ {display_name} found in step_2",
            extra={"value": multiple_raw, "field_name": field_found},
        )
        return multiple_raw, field_found

    def extract_valuation_values(
        self,
        step_results: Dict[int, object],
        extracted_results: Dict[int, Dict[str, object]],
        request: ValuationRequest,
    ) -> Dict[str, Decimal]:
        """
        Extract and validate enterprise_value, equity_value, and valuation range.

        Args:
            step_results: Dictionary mapping step numbers to StepOutput objects
            extracted_results: Dictionary mapping step numbers to result dictionaries
            request: Valuation request

        Returns:
            Dictionary with enterprise_value, equity_value, valuation_low, valuation_mid, valuation_high
        """
        # BANK-GRADE:
        # - Step 11/10 own the final valuation range and final equity answer
        # - Step 7 is the EV-to-equity bridge before range synthesis
        # - Do not silently substitute EV as equity
        step_3 = extracted_results.get(3, {})
        step_5 = extracted_results.get(5, {})
        step_6 = extracted_results.get(6, {})
        step_7 = extracted_results.get(7, {})
        step_10 = extracted_results.get(10, {})
        step_11 = extracted_results.get(11, {})

        # Extract equity value with priority:
        # explicit Step 11/10 equity aliases > Step 11/10 valuation mid > Step 7.
        # Older Step 11 payloads only emitted valuation_* fields; accept those
        # as the final equity answer to keep the canonical value inside the
        # final defensibility band.
        equity_value = Decimal("0.0")
        equity_source = "NONE"

        if step_11.get("equity_value_mid") is not None:
            equity_value = to_decimal(step_11.get("equity_value_mid"))
            equity_source = "Step 11"
            self.logger.debug(
                "✅ Using equity value from Step 11", extra={"equity_value": str(equity_value)}
            )
        elif step_11.get("valuation_mid") is not None:
            equity_value = to_decimal(step_11.get("valuation_mid"))
            equity_source = "Step 11 valuation_mid"
            self.logger.info(
                "✅ Using final valuation midpoint from Step 11 as equity value",
                extra={"equity_value": str(equity_value)},
            )
        elif step_10.get("equity_value_mid") is not None:
            equity_value = to_decimal(step_10.get("equity_value_mid"))
            equity_source = "Step 10"
            self.logger.info(
                "✅ Using equity value from Step 10", extra={"equity_value": str(equity_value)}
            )
        elif step_10.get("valuation_mid") is not None:
            equity_value = to_decimal(step_10.get("valuation_mid"))
            equity_source = "Step 10 valuation_mid"
            self.logger.info(
                "✅ Using final valuation midpoint from Step 10 as equity value",
                extra={"equity_value": str(equity_value)},
            )
        elif step_7.get("equity_value_mid") is not None:
            equity_value = to_decimal(step_7.get("equity_value_mid"))
            equity_source = "Step 7"
            self.logger.info(
                "✅ Using equity value from Step 7", extra={"equity_value": str(equity_value)}
            )
        else:
            self.logger.error(
                "❌ No canonical equity value found from Step 7/10/11 explicit fields",
                extra={
                    "step7_has_equity": step_7.get("equity_value_mid") is not None,
                    "step10_has_explicit_equity": step_10.get("equity_value_mid") is not None,
                    "step11_has_explicit_equity": step_11.get("equity_value_mid") is not None,
                    "step10_has_valuation": step_10.get("valuation_mid") is not None,
                    "step11_has_valuation": step_11.get("valuation_mid") is not None,
                },
            )

        # Extract valuation range with priority: Step 11 > Step 10 > calculate from equity
        valuation_low, valuation_mid, valuation_high = self.range_extractor.extract_range(
            step_10, step_11, equity_value
        )

        # Log which step's values are being used
        if step_11.get("valuation_mid") is not None:
            self.logger.debug(
                "✅ Using valuation range from Step 11",
                extra={
                    "valuation_low": str(step_11.get("valuation_low")),
                    "valuation_mid": str(step_11.get("valuation_mid")),
                    "valuation_high": str(step_11.get("valuation_high")),
                },
            )
        elif step_10.get("valuation_mid") is not None:
            self.logger.info(
                "✅ Using valuation range from Step 10",
                extra={
                    "valuation_low": str(step_10.get("valuation_low")),
                    "valuation_mid": str(step_10.get("valuation_mid")),
                    "valuation_high": str(step_10.get("valuation_high")),
                },
            )
        else:
            self.logger.warning(
                "⚠️ Calculating valuation range from equity (Step 10/11 unavailable)",
                extra={"equity_value": str(equity_value), "equity_source": equity_source},
            )

        # Enterprise value must be the POST-discount EV — the Step 6 output, i.e.
        # after the Steps 4/4.5/5/6 discount chain — because that is the rail the
        # published equity value and the published multiple band both sit on.
        # Publishing the Step-3 BASE EV here is what put a 3.85x pre-discount
        # multiple next to a 2.0-3.5x post-discount band, and re-anchored the
        # report headline to an EV 46% above the synthesised value (VR-2026-9712):
        # the report reads `multiples_valuation.enterprise_value` as "the market
        # EV" and treats any gap to equity as an EV->equity bridge.
        # Step 3 stays as the last resort so a run that never reached Steps 5/6
        # still publishes something rather than zero.
        enterprise_value = Decimal("0.0")
        for source_step, source in ((6, step_6), (5, step_5), (3, step_3)):
            candidate = source.get("enterprise_value_mid")
            if candidate is not None and to_decimal(candidate) > 0:
                enterprise_value = to_decimal(candidate)
                if source_step != 6:
                    self.logger.warning(
                        "⚠️ Post-discount EV unavailable; falling back to an earlier step",
                        extra={
                            "ev_source_step": source_step,
                            "enterprise_value": str(enterprise_value),
                        },
                    )
                break

        # Validate and fix invalid valuation range
        if valuation_low <= 0 or valuation_mid <= 0 or valuation_high <= 0:
            self.logger.warning(
                "⚠️ Invalid valuation values detected, using fallback",
                extra={
                    "valuation_low": valuation_low,
                    "valuation_mid": valuation_mid,
                    "valuation_high": valuation_high,
                    "equity_value": equity_value,
                    "step11_has_values": step_11.get("valuation_mid") is not None,
                    "step10_has_values": step_10.get("valuation_mid") is not None,
                },
            )

            if equity_value > 0:
                valuation_low, valuation_mid, valuation_high = (
                    self.fallback_calculator.calculate_from_equity(equity_value)
                )
            else:
                valuation_low, valuation_mid, valuation_high = (
                    self.fallback_calculator.calculate_from_revenue_ebitda(request)
                )

        # Ensure equity_value is valid
        if equity_value <= 0:
            self.logger.warning(
                "⚠️ equity_value is invalid, using valuation_mid as explicit degraded fallback",
                extra={
                    "original_equity_value": equity_value,
                    "valuation_mid": valuation_mid,
                    "fallback_reason": "No canonical Step 7 equity value available",
                    "step7_status": (
                        step_results[7].status.value if 7 in step_results else "not_found"
                    ),
                },
            )
            equity_value = valuation_mid

        # Calculate enterprise value with debt adjustments
        enterprise_value = self.enterprise_calculator.calculate(
            valuation_mid, enterprise_value, request
        )

        # Final validation and emergency fallbacks
        return self.validator.validate_and_fix(
            valuation_low, valuation_mid, valuation_high, equity_value, enterprise_value
        )

    def extract_multiples_with_fallbacks(
        self, step_2: Dict[str, object], request: ValuationRequest
    ) -> Dict[str, object]:
        """
        Extract revenue and EBITDA multiples from step_2. For concrete
        business-type valuations, missing Step 2 multiples are not repaired
        from industry defaults unless the caller explicitly accepted an
        untrusted fallback.

        Args:
            step_2: Step 2 result dictionary
            request: Valuation request

        Returns:
            Dictionary with revenue_multiple_raw, ebitda_multiple_raw, and field names found
        """
        require_contract = _requires_resolved_contract(request)
        if require_contract and not _resolved_benchmark_contract(step_2 or {}):
            raise ValueError(
                "Cannot extract valuation multiples without the resolved benchmark "
                "contract from Step 2 or explicit fallback consent."
            )

        revenue_multiple_raw, revenue_field_found = self._extract_or_fallback_multiple(
            step_2=step_2 or {},
            request=request,
            fields=_REVENUE_MULTIPLE_FIELDS,
            metric="revenue",
            display_name="revenue_multiple",
            require_contract=require_contract,
            missing_error=(
                "Step 2 is missing EV/Revenue multiple. Refusing "
                "industry-default fallback without explicit consent."
            ),
        )

        ebitda_multiple_raw, ebitda_field_found = self._extract_or_fallback_multiple(
            step_2=step_2 or {},
            request=request,
            fields=_EBITDA_MULTIPLE_FIELDS,
            metric="ebitda",
            display_name="ebitda_multiple",
            require_contract=require_contract,
            missing_error=(
                "Step 2 is missing EV/EBITDA multiple. Refusing "
                "industry-default fallback without explicit consent."
            ),
        )

        logger.debug(
            "🔍 Step 4: Mapping multiples from step_2 with fallbacks",
            extra={
                "step_2_revenue_multiple": step_2.get("ev_revenue_multiple") if step_2 else None,
                "step_2_revenue_alt": step_2.get("ev_revenue") if step_2 else None,
                "revenue_field_found": revenue_field_found,
                "mapped_revenue_multiple": revenue_multiple_raw,
                "step_2_ebitda_multiple": step_2.get("ev_ebitda_multiple") if step_2 else None,
                "step_2_ebitda_alt": step_2.get("ev_ebitda_ratio") if step_2 else None,
                "ebitda_field_found": ebitda_field_found,
                "mapped_ebitda_multiple": ebitda_multiple_raw,
                "used_revenue_fallback": revenue_multiple_raw
                != (step_2.get("ev_revenue_multiple") if step_2 else None),
                "used_ebitda_fallback": ebitda_multiple_raw
                != (step_2.get("ev_ebitda_multiple") if step_2 else None),
            },
        )

        return {
            "revenue_multiple_raw": revenue_multiple_raw,
            "ebitda_multiple_raw": ebitda_multiple_raw,
            "revenue_field_found": revenue_field_found,
            "ebitda_field_found": ebitda_field_found,
        }
