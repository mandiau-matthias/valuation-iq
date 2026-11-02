"""
Response Builder

Builds ValuationResponse from detailed results and request data.
Handles response construction, validation, and sanitization.
"""

from src.api.response_currency import response_currency

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, Optional

from pydantic import ValidationError

from src.api.schemas import (
    DCFValuationResponse,
    MultiplesValuationResponse,
    ValuationRequest,
    ValuationResponse,
)
from src.config.valuation_constants import get_asking_price_markup
from src.utils.decimal_helpers import from_decimal, to_decimal
from src.utils.fiscal_year import get_current_filing_year
from src.utils.valuation_logger import ValuationLogger

from .owner_profiling_response import extract_owner_dependency_payload, extract_owner_risk_ledger
from .post_deal_swap import compute_post_deal_swap

MIN_RESPONSE_VALUE = Decimal("1.0")


def _default_methodology_weight(methodology: str, target_methodology: str) -> Decimal:
    if methodology == target_methodology:
        return Decimal("1.0")
    if methodology == "HYBRID":
        return Decimal("0.5")
    return Decimal("0.0")


def _methodology_display_name(dcf_weight: Decimal, multiples_weight: Decimal) -> str:
    if dcf_weight > Decimal("0.5"):
        return "Discounted Cash Flow (DCF)"
    if multiples_weight > Decimal("0.5"):
        return "Market Multiples"
    return "Hybrid Valuation"


def _current_multiple_from_results(detailed_results: Dict[str, object]) -> object | None:
    multiples_res = detailed_results.get("multiples_valuation", {})
    if isinstance(multiples_res, dict):
        return multiples_res.get("ebitda_multiple")
    return None


def _net_debt_from_current_year_data(current_year_data: Dict[str, object]) -> Decimal:
    total_debt = to_decimal(current_year_data.get("total_debt") or 0)
    cash = to_decimal(current_year_data.get("cash") or 0)
    return total_debt - cash


def _implied_current_multiple(
    *,
    current_multiple: object | None,
    ebitda: Decimal | None,
    equity_value_mid: Decimal,
    net_debt: Decimal,
) -> object | None:
    if current_multiple is not None or not ebitda or ebitda <= 0:
        return current_multiple
    implied_ev = equity_value_mid + net_debt
    return implied_ev / ebitda


def _recommended_asking_multiple(
    *,
    current_multiple: object | None,
    confidence_level: str,
    advisor_buffer_override: object | None,
) -> Decimal | None:
    if not current_multiple:
        return None
    try:
        current_multiple_decimal = to_decimal(current_multiple)
    except (TypeError, ValueError):
        return None
    if current_multiple_decimal <= 0:
        return None
    recommended_asking_multiple = current_multiple_decimal * get_asking_price_markup(
        confidence_level,
        advisor_override_pct=advisor_buffer_override,
    )
    if recommended_asking_multiple <= 0:
        return None
    return recommended_asking_multiple


def _asking_price_outputs(
    *,
    current_year_data: Dict[str, object],
    detailed_results: Dict[str, object],
    equity_value_mid: Decimal,
    confidence_level: str,
    advisor_buffer_override: object | None,
) -> tuple[Decimal, Decimal | None, Decimal]:
    ebitda = (
        to_decimal(current_year_data.get("ebitda"))
        if current_year_data.get("ebitda") is not None
        else None
    )
    net_debt = _net_debt_from_current_year_data(current_year_data)
    current_multiple = _implied_current_multiple(
        current_multiple=_current_multiple_from_results(detailed_results),
        ebitda=ebitda,
        equity_value_mid=equity_value_mid,
        net_debt=net_debt,
    )
    recommended_asking_multiple = _recommended_asking_multiple(
        current_multiple=current_multiple,
        confidence_level=confidence_level,
        advisor_buffer_override=advisor_buffer_override,
    )
    markup = get_asking_price_markup(
        confidence_level,
        advisor_override_pct=advisor_buffer_override,
    )
    enterprise_value = equity_value_mid + net_debt
    recommended_asking_price = enterprise_value * markup - net_debt
    return recommended_asking_price, recommended_asking_multiple, net_debt


def _positive_equity_range(
    equity_value_low: Decimal | None,
    equity_value_mid: Decimal | None,
    equity_value_high: Decimal | None,
) -> tuple[Decimal, Decimal, Decimal]:
    if equity_value_low is None or equity_value_low <= 0:
        equity_value_low = MIN_RESPONSE_VALUE
    if equity_value_mid is None or equity_value_mid <= 0:
        equity_value_mid = max(equity_value_low, MIN_RESPONSE_VALUE)
    if equity_value_high is None or equity_value_high <= 0:
        equity_value_high = max(equity_value_mid, MIN_RESPONSE_VALUE)
    if equity_value_low > equity_value_mid:
        equity_value_low = equity_value_mid
    if equity_value_high < equity_value_mid:
        equity_value_high = equity_value_mid
    return equity_value_low, equity_value_mid, equity_value_high


def _positive_asking_price(
    recommended_asking_price: Decimal | None,
    equity_value_mid: Decimal,
) -> Decimal:
    if recommended_asking_price is None or recommended_asking_price <= 0:
        return max(equity_value_mid, MIN_RESPONSE_VALUE)
    return recommended_asking_price


def _confidence_score_percentage(confidence_score: Decimal | None) -> int:
    if confidence_score is not None and confidence_score <= Decimal("1.0"):
        raw_score = int(confidence_score * 100)
    elif confidence_score is not None:
        raw_score = int(confidence_score)
    else:
        raw_score = 50
    return max(0, min(100, raw_score))


def _bounded_weight(weight: object) -> Decimal:
    return max(Decimal("0"), min(Decimal("1"), to_decimal(weight)))


def _base_response_dict(
    *,
    request: ValuationRequest,
    valuation_id: str,
    methodology_name: str,
    methodology_downgrade_reason: str | None,
    equity_value_low: Decimal,
    equity_value_mid: Decimal,
    equity_value_high: Decimal,
    recommended_asking_price: Decimal,
    recommended_asking_multiple: Decimal | None,
    dcf_weight: Decimal,
    multiples_weight: Decimal,
    confidence_level: str,
    confidence_score: int,
    current_year_data: Dict[str, object],
    financial_metrics: Dict[str, object],
) -> Dict[str, object]:
    return {
        "valuation_id": valuation_id,
        "company_name": request.company_name,
        "valuation_date": date.today(),
        "currency": response_currency(request),
        "equity_value_low": equity_value_low,
        "equity_value_mid": equity_value_mid,
        "equity_value_high": equity_value_high,
        "recommended_asking_price": recommended_asking_price,
        "recommended_asking_multiple": recommended_asking_multiple,
        "dcf_weight": dcf_weight,
        "multiples_weight": multiples_weight,
        "financial_metrics": financial_metrics,
        "overall_confidence": confidence_level,
        "confidence_score": confidence_score,
        "current_year_data": current_year_data,
        "methodology": methodology_name,
        "methodology_downgrade_reason": methodology_downgrade_reason,
    }


def _attach_step_results(
    response_dict: Dict[str, object],
    detailed_results: Dict[str, object],
) -> None:
    multiples_results_raw = detailed_results.get("multiples_valuation", {})
    if not isinstance(multiples_results_raw, dict) or "_step_results" not in multiples_results_raw:
        return
    step_results = multiples_results_raw["_step_results"]
    if not step_results or not isinstance(step_results, dict):
        return
    response_dict.setdefault("detailed_results", {})["step_results"] = step_results


def _attach_owner_profile_fields(
    response_dict: Dict[str, object],
    detailed_results: Dict[str, object],
) -> None:
    response_dict["owner_profiling"] = None
    owner_dep_result, owner_dep_adjustment = extract_owner_dependency_payload(detailed_results)
    response_dict["owner_dependency_result"] = owner_dep_result
    response_dict["owner_dependency_adjustment"] = owner_dep_adjustment
    response_dict["owner_risk_ledger"] = extract_owner_risk_ledger(detailed_results)


def _request_current_year(request: ValuationRequest) -> object | None:
    current_year_data = getattr(request, "current_year_data", None)
    if not current_year_data:
        return None
    return getattr(current_year_data, "year", None)


def _empty_current_year_data() -> Dict[str, object]:
    return {
        "year": get_current_filing_year(),
        "revenue": Decimal("0.0"),
        "ebitda": Decimal("0.0"),
    }


def _multiples_step_results(detailed_results: Dict[str, object]) -> Dict[object, object]:
    multiples_results = detailed_results.get("multiples_valuation", {})
    if not isinstance(multiples_results, dict):
        return {}
    step_results = multiples_results.get("_step_results", {})
    if not isinstance(step_results, dict):
        return {}
    return step_results


def _step1_result_payload(step_results: Dict[object, object]) -> Dict[str, object] | None:
    step1_result = step_results.get(1)
    if not step1_result or not hasattr(step1_result, "result"):
        return None
    step1_data = step1_result.result
    if isinstance(step1_data, dict):
        return step1_data
    return None


def _current_year_data_from_step1(
    request: ValuationRequest,
    detailed_results: Dict[str, object],
) -> Dict[str, object] | None:
    step1_data = _step1_result_payload(_multiples_step_results(detailed_results))
    if not step1_data:
        return None

    revenue = step1_data.get("revenue")
    ebitda = step1_data.get("ebitda")
    if not revenue or revenue <= 0:
        return None

    current_year = _request_current_year(request) or get_current_filing_year()
    return {
        "year": current_year,
        "revenue": to_decimal(revenue) if revenue else Decimal("0.0"),
        "ebitda": to_decimal(ebitda) if ebitda is not None else Decimal("0.0"),
    }


def _serialize_current_year_data(current_year_data: object) -> Dict[str, object]:
    if hasattr(current_year_data, "model_dump"):
        return current_year_data.model_dump()
    if hasattr(current_year_data, "dict"):
        return current_year_data.dict()
    if isinstance(current_year_data, dict):
        return current_year_data
    return {}


def _current_year_data_from_request(request: ValuationRequest) -> Dict[str, object] | None:
    current_year_data = getattr(request, "current_year_data", None)
    if not current_year_data:
        return None
    return _serialize_current_year_data(current_year_data)


class ResponseBuilder:
    """
    Builder for ValuationResponse construction.

    Responsibilities:
    - Construct ValuationResponse from detailed results
    - Extract and structure current year data
    - Build DCF and Multiples valuation responses
    - Validate response data
    """

    def __init__(
        self, summary_generator, confidence_scorer, logger: Optional[ValuationLogger] = None
    ):
        """
        Initialize response builder.

        Args:
            summary_generator: SummaryGenerator instance
            confidence_scorer: ConfidenceScorer instance
            logger: Optional logger instance
        """
        self.summary_generator = summary_generator
        self.confidence_scorer = confidence_scorer
        self.logger = logger or ValuationLogger(self.__class__.__name__)
        self.logger.debug("✅ ResponseBuilder initialized")

    def extract_current_year_data(
        self, request: ValuationRequest, detailed_results: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Extract current_year_data from request OR Step 1 result.

        Preserves the validated current-year inputs and their normalization provenance.
        Step 1 may be a weighted earnings basis spanning several fiscal years.

        Args:
            request: The valuation request
            detailed_results: Detailed results containing step results

        Returns:
            Dictionary containing current_year_data (revenue, ebitda, etc.)
        """
        try:
            actual_year = _current_year_data_from_request(request)
            if actual_year:
                return actual_year
            current_year_data = _current_year_data_from_step1(request, detailed_results)
            if current_year_data:
                self.logger.debug(
                    "✅ Extracted current_year_data from Step 1 result",
                    extra={
                        "source": "step1_result",
                        "revenue": current_year_data["revenue"],
                        "ebitda": current_year_data.get("ebitda"),
                    },
                )
                return current_year_data

            result = _current_year_data_from_request(request)
            if result is not None:
                self.logger.info(
                    "✅ Extracted current_year_data from request (fallback)",
                    extra={
                        "source": "request.current_year_data",
                        "revenue": result.get("revenue") if isinstance(result, dict) else None,
                        "ebitda": result.get("ebitda") if isinstance(result, dict) else None,
                    },
                )
                return result

            self.logger.warning("⚠️ No current_year_data available from Step 1 or request")
            return _empty_current_year_data()
        except Exception as e:
            self.logger.error(
                "❌ Error extracting current_year_data, using request fallback",
                extra={"error": str(e), "error_type": type(e).__name__},
                exc_info=True,
            )
            return _current_year_data_from_request(request) or _empty_current_year_data()

    def safe_create_dcf_valuation(
        self, dcf_data: Optional[Dict[str, Any]]
    ) -> Optional[DCFValuationResponse]:
        """
        Safely create DCFValuationResponse with error handling.

        Args:
            dcf_data: DCF valuation data dictionary

        Returns:
            DCFValuationResponse or None if data is invalid
        """
        if not dcf_data:
            return None

        try:
            return DCFValuationResponse.model_validate(dcf_data)
        except Exception as e:
            self.logger.error(
                "DCF validation failed",
                extra={
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "errors": e.errors() if hasattr(e, "errors") else None,
                    "dcf_data_keys": list(dcf_data.keys()) if dcf_data else None,
                },
                exc_info=True,
            )
            return None

    def safe_create_multiples_valuation(
        self, multiples_data: Optional[Dict[str, Any]]
    ) -> Optional[MultiplesValuationResponse]:
        """
        Safely create MultiplesValuationResponse with error handling.

        Args:
            multiples_data: Multiples valuation data dictionary

        Returns:
            MultiplesValuationResponse or None if data is invalid
        """
        if not multiples_data:
            return None

        try:
            return MultiplesValuationResponse.model_validate(multiples_data)
        except Exception as e:
            self.logger.error(
                "Multiples validation failed",
                extra={
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "errors": e.errors() if hasattr(e, "errors") else None,
                    "multiples_data_keys": list(multiples_data.keys()) if multiples_data else None,
                },
                exc_info=True,
            )
            return None

    def _populate_generated_summary_components(
        self,
        response_dict: Dict[str, object],
        *,
        request: ValuationRequest,
        detailed_results: Dict[str, object],
        methodology: str,
        dcf_exclusion_reason: str | None,
    ) -> None:
        requested_methodology = getattr(request, "methodology", None)
        dcf_included = detailed_results.get("dcf_valuation") is not None
        note_locale = getattr(request, "locale", None) or "nl"
        note_country_code = (
            str(getattr(request, "country_code", None) or "BE").strip().upper() or "BE"
        )

        response_dict["valuation_summary"] = self.summary_generator.generate_summary(
            request, detailed_results
        )
        response_dict["key_value_drivers"] = self.summary_generator.extract_value_drivers(
            request, detailed_results
        )
        response_dict["risk_factors"] = self.summary_generator.extract_risk_factors(
            request, detailed_results
        )
        response_dict["methodology_notes"] = self.summary_generator.generate_methodology_notes(
            methodology,
            requested_methodology=requested_methodology,
            dcf_included=dcf_included,
            dcf_exclusion_reason=dcf_exclusion_reason,
            locale=note_locale,
            country_code=note_country_code,
        )

    def _fallback_risk_factors(
        self,
        request: ValuationRequest,
        detailed_results: Dict[str, object],
    ) -> list[object]:
        try:
            return self.summary_generator._generate_fallback_risk_factors(request, detailed_results)
        except Exception:
            return [
                "Valuation estimates are subject to market conditions and comparable company data availability"
            ]

    def _ensure_summary_component_defaults(
        self,
        response_dict: Dict[str, object],
        *,
        request: ValuationRequest,
        detailed_results: Dict[str, object],
        methodology: str,
    ) -> None:
        if not response_dict.get("risk_factors") or len(response_dict["risk_factors"]) == 0:
            self.logger.warning("Risk factors empty, regenerating with fallback")
            response_dict["risk_factors"] = self._fallback_risk_factors(request, detailed_results)

        methodology_notes = response_dict.get("methodology_notes")
        if not methodology_notes or len(methodology_notes.strip()) == 0:
            response_dict["methodology_notes"] = f"Methodology: {methodology}"
            self.logger.warning("Methodology notes empty, using default")

    def _set_default_summary_components(
        self,
        response_dict: Dict[str, object],
        *,
        request: ValuationRequest,
        detailed_results: Dict[str, object],
        methodology: str,
    ) -> None:
        response_dict["valuation_summary"] = "Valuation completed successfully"
        response_dict["key_value_drivers"] = []
        response_dict["risk_factors"] = self._fallback_risk_factors(request, detailed_results)
        response_dict["methodology_notes"] = f"Methodology: {methodology}"

    def _populate_summary_components(
        self,
        response_dict: Dict[str, object],
        *,
        request: ValuationRequest,
        detailed_results: Dict[str, object],
        methodology: str,
        dcf_exclusion_reason: str | None,
    ) -> None:
        try:
            self._populate_generated_summary_components(
                response_dict,
                request=request,
                detailed_results=detailed_results,
                methodology=methodology,
                dcf_exclusion_reason=dcf_exclusion_reason,
            )
            self._ensure_summary_component_defaults(
                response_dict,
                request=request,
                detailed_results=detailed_results,
                methodology=methodology,
            )
        except Exception as summary_error:
            self.logger.warning(
                "Summary generation failed, using defaults",
                extra={"error": str(summary_error), "error_type": type(summary_error).__name__},
                exc_info=True,
            )
            self._set_default_summary_components(
                response_dict,
                request=request,
                detailed_results=detailed_results,
                methodology=methodology,
            )

    def _populate_post_deal_swap(
        self,
        response_dict: Dict[str, object],
        *,
        detailed_results: Dict[str, object],
        request: ValuationRequest,
        methodology: str,
        equity_value_low: Decimal,
        equity_value_mid: Decimal,
        equity_value_high: Decimal,
    ) -> None:
        try:
            swap = compute_post_deal_swap(
                detailed_results,
                pre_deal_equity_mid=equity_value_mid,
                pre_deal_equity_low=equity_value_low,
                pre_deal_equity_high=equity_value_high,
                locale=getattr(request, "locale", None),
                methodology=methodology,
                request=request,
            )
            response_dict["owner_compensation_swap"] = swap
            response_dict["post_deal_equity_value"] = swap.get("post_deal_equity_value")
        except Exception as swap_error:
            self.logger.warning(
                "Post-deal swap computation failed; falling back to no-swap",
                extra={
                    "error": str(swap_error),
                    "error_type": type(swap_error).__name__,
                },
                exc_info=True,
            )
            response_dict["owner_compensation_swap"] = None
            response_dict["post_deal_equity_value"] = equity_value_mid

    def build_response_dict(
        self,
        request: ValuationRequest,
        detailed_results: Dict[str, Any],
        valuation_id: str,
        methodology: str,
        equity_value_low: Decimal,
        equity_value_mid: Decimal,
        equity_value_high: Decimal,
        confidence_score: Decimal,
        financial_metrics: Dict[str, Any],
        dcf_exclusion_reason: Optional[str] = None,
        methodology_downgrade_reason: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Build response dictionary with all required fields.

        Args:
            request: Valuation request
            detailed_results: Detailed valuation results
            valuation_id: Valuation ID
            methodology: Methodology used
            equity_value_low: Low equity value
            equity_value_mid: Mid equity value
            equity_value_high: High equity value
            confidence_score: Confidence score (0-1)
            financial_metrics: Financial metrics dictionary
            dcf_exclusion_reason: Optional DCF exclusion reason
            methodology_downgrade_reason: Optional methodology downgrade reason

        Returns:
            Response dictionary ready for ValuationResponse construction
        """
        confidence_level = self.confidence_scorer.map_score_to_level(confidence_score)
        dcf_weight = detailed_results.get(
            "dcf_weight",
            _default_methodology_weight(methodology, "DCF"),
        )
        multiples_weight = detailed_results.get(
            "multiples_weight",
            _default_methodology_weight(methodology, "MULTIPLES"),
        )
        dcf_weight_decimal = to_decimal(dcf_weight)
        multiples_weight_decimal = to_decimal(multiples_weight)
        methodology_name = _methodology_display_name(dcf_weight_decimal, multiples_weight_decimal)
        current_year_data = self.extract_current_year_data(request, detailed_results)
        advisor_buffer_override = getattr(request, "asking_price_buffer_pct", None)
        recommended_asking_price, recommended_asking_multiple, _net_debt = _asking_price_outputs(
            current_year_data=current_year_data,
            detailed_results=detailed_results,
            equity_value_mid=equity_value_mid,
            confidence_level=confidence_level,
            advisor_buffer_override=advisor_buffer_override,
        )
        equity_value_low, equity_value_mid, equity_value_high = _positive_equity_range(
            equity_value_low,
            equity_value_mid,
            equity_value_high,
        )
        recommended_asking_price = _positive_asking_price(
            recommended_asking_price,
            equity_value_mid,
        )
        dcf_weight = _bounded_weight(dcf_weight_decimal)
        multiples_weight = _bounded_weight(multiples_weight_decimal)
        response_dict = _base_response_dict(
            request=request,
            valuation_id=valuation_id,
            methodology_name=methodology_name,
            methodology_downgrade_reason=methodology_downgrade_reason,
            equity_value_low=equity_value_low,
            equity_value_mid=equity_value_mid,
            equity_value_high=equity_value_high,
            recommended_asking_price=recommended_asking_price,
            recommended_asking_multiple=recommended_asking_multiple,
            dcf_weight=dcf_weight,
            multiples_weight=multiples_weight,
            confidence_level=confidence_level,
            confidence_score=_confidence_score_percentage(confidence_score),
            current_year_data=current_year_data,
            financial_metrics=financial_metrics,
        )

        # Build DCF and Multiples valuations
        response_dict["dcf_valuation"] = self.safe_create_dcf_valuation(
            detailed_results.get("dcf_valuation")
        )
        response_dict["multiples_valuation"] = self.safe_create_multiples_valuation(
            detailed_results.get("multiples_valuation")
        )

        # Extract step results if available
        _attach_step_results(response_dict, detailed_results)

        # Generate summary components
        self._populate_summary_components(
            response_dict,
            request=request,
            detailed_results=detailed_results,
            methodology=methodology,
            dcf_exclusion_reason=dcf_exclusion_reason,
        )

        # Set optional fields
        response_dict["mcp_insights"] = None
        # OWNER-PROFILING-1 OP-4c: surface engine output instead of hardcoding
        # `owner_profiling=None`. The legacy `owner_profiling` field on
        # `ValuationResponse` is deprecated (legacy_schemas.py:1835) — the
        # canonical fields are `owner_dependency_result` and
        # `owner_dependency_adjustment`. Both are populated when the
        # synthesizer ran the engine; both default to None / 0 otherwise.
        # M&A-grade Owner Risk Ledger — single auditable reconciliation.
        # Pure presentation metadata; never raises.
        _attach_owner_profile_fields(response_dict, detailed_results)
        response_dict["business_type_intelligence"] = None
        response_dict["monte_carlo_results"] = None

        # OWNER-PROFILING-2: Post-Deal equity swap for the Business Card
        # lens. Always emit a structured payload — the FE relies on
        # `applied=False` to disable the toggle, not on field absence.
        # Locale is threaded through so the rationale sentence renders in
        # NL or EN matching the rest of the report; numeric formatting
        # does not vary by locale.
        #
        # Methodology + request are passed so the helper can run the
        # 9-method fallback path (DCF / fiscal_4x) when Step 2.5 isn't
        # in the detailed_results, and so it can mark NAV / startup as
        # `state="not_applicable"` rather than `"unavailable"`.
        self._populate_post_deal_swap(
            response_dict,
            detailed_results=detailed_results,
            request=request,
            methodology=methodology,
            equity_value_low=equity_value_low,
            equity_value_mid=equity_value_mid,
            equity_value_high=equity_value_high,
        )

        return response_dict

    def build_response(self, response_dict: Dict[str, Any]) -> ValuationResponse:
        """
        Build ValuationResponse from response dictionary.

        Args:
            response_dict: Response dictionary

        Returns:
            ValuationResponse object
        """
        try:
            return ValuationResponse.model_validate(response_dict)
        except ValidationError as e:
            self.logger.error(
                "ValuationResponse validation failed",
                extra={"error": str(e), "errors": e.errors() if hasattr(e, "errors") else None},
                exc_info=True,
            )
            raise
