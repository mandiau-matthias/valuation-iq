"""
Valuation Validators

This module handles request validation for valuation API endpoints.
"""

from typing import Any, List, Optional

from src.utils.logging import get_logger

from .valuation_request_checks import (
    load_business_type_rules,
    load_industry_rules,
    load_validation_rules,
    validate_assumptions,
    validate_business_context,
    validate_business_information,
    validate_business_name,
    validate_business_type_industry,
    validate_market_data,
    validate_methodology,
    validate_optional_fields,
    validate_owner_profile,
    validate_quick_financial_data,
)
from .valuation_types import (
    QuickValuationRequest,
    ValidationError,
    ValidationResponse,
    ValuationRequest,
)
from src.domain.valuation_contract import normalize_method_key

from .year_data_validation import (
    validate_current_year_data,
    validate_ebitda_only_current_year_data,
    validate_ebitda_only_historical_data,
    validate_historical_data,
    validate_startup_current_year_data,
)

logger = get_logger(__name__)

EBITDA_MULTIPLE_METHOD_KEY = "ebitda_multiple"


def _is_ebitda_only_request(request: object) -> bool:
    """True when the request explicitly selects an EV/EBITDA multiple and has positive EBITDA
    but no positive revenue -- the abbreviated / gross-margin filer path. Gates the permissive
    revenue validation so the "revenue must be positive" rule is never relaxed for ordinary
    requests."""
    if normalize_method_key(getattr(request, "selected_method", None)) != EBITDA_MULTIPLE_METHOD_KEY:
        return False
    current = getattr(request, "current_year_data", None)
    if not current:
        return False
    ebitda = getattr(current, "ebitda", None)
    revenue = getattr(current, "revenue", None)
    return (ebitda is not None and ebitda > 0) and not (revenue is not None and revenue > 0)


class ValuationValidator:
    """Handles validation for valuation requests"""

    def __init__(self):
        """Initialize the valuation validator"""
        self.logger = logger
        self.validation_rules = load_validation_rules()
        self.business_type_rules = load_business_type_rules()
        self.industry_rules = load_industry_rules()

    async def validate_quick_valuation_request(
        self, request: QuickValuationRequest
    ) -> ValidationResponse:
        """
        Validate a quick valuation request

        Args:
            request: Quick valuation request to validate

        Returns:
            Validation response with errors and warnings
        """
        try:
            self.logger.info(
                "Validating quick valuation request",
                company_name=getattr(request, "company_name", "N/A"),
                industry=request.industry,
            )

            errors = []
            warnings = []

            # Validate business name (now optional)
            if hasattr(request, "company_name") and request.company_name:
                name_errors = validate_business_name(request.company_name, self.logger)
                errors.extend(name_errors)

            # Validate financial data
            financial_errors = validate_quick_financial_data(
                request.revenue, request.ebitda, self.logger
            )
            errors.extend(financial_errors)

            # Validate industry and business type
            type_errors = validate_business_type_industry(
                request.business_type, request.industry, self.logger
            )
            errors.extend(type_errors)

            # Validate optional fields
            optional_errors = validate_optional_fields(
                request.employee_count, request.owner_role, request.owner_hours, self.logger
            )
            warnings.extend(optional_errors)  # Optional fields generate warnings, not errors

            is_valid = len(errors) == 0

            self.logger.info(
                "Quick valuation request validation completed",
                is_valid=is_valid,
                errors=len(errors),
                warnings=len(warnings),
            )

            return ValidationResponse(is_valid=is_valid, errors=errors, warnings=warnings)

        except Exception as e:
            self.logger.error(f"Error validating quick valuation request: {e}")
            return ValidationResponse(
                is_valid=False,
                errors=[
                    ValidationError(
                        field="validation_system",
                        message=f"Validation system error: {str(e)}",
                        value=None,
                    )
                ],
            )

    async def validate_valuation_request(self, request: ValuationRequest) -> ValidationResponse:
        """
        Validate a comprehensive valuation request

        Args:
            request: Valuation request to validate

        Returns:
            Validation response with errors and warnings
        """
        try:
            # DEBUG: per-stage lifecycle; "Valuation request validation completed"
            # below is dup with this entry, so demote both.
            self.logger.debug(
                "Validating valuation request",
                company_name=getattr(request, "company_name", "N/A"),
                methodology=getattr(request, "methodology", "N/A"),
            )

            errors = []
            warnings = []

            # Validate business information
            business_errors = validate_business_information(
                getattr(request, "company_name", ""),
                getattr(request, "business_type", None),
                request.industry,
                self.logger,
            )
            errors.extend(business_errors)

            # Validate financial data (new schema format)
            # Startup valuations follow a venture-method path (Berkus + Scorecard + VC)
            # and are explicitly pre-revenue, so the strict "revenue must be positive"
            # rule does not apply. We route to a dedicated, more permissive validator
            # that still guards the field types and ensures the qualitative
            # ``startup_inputs`` block is supplied.
            is_startup_valuation = getattr(request, "selected_method", None) == "startup_valuation"
            # Abbreviated / gross-margin filer: explicit EV/EBITDA multiple, positive EBITDA,
            # no disclosed turnover. Route to permissive validators that keep every guard
            # except the positive-revenue one (which turnover-less filers can never satisfy).
            is_ebitda_only = _is_ebitda_only_request(request)
            if hasattr(request, "current_year_data") and request.current_year_data:
                if is_startup_valuation:
                    financial_errors = await self._validate_startup_current_year_data(
                        request.current_year_data,
                        startup_inputs=getattr(request, "startup_inputs", None),
                    )
                elif is_ebitda_only:
                    financial_errors = await self._validate_ebitda_only_current_year_data(
                        request.current_year_data
                    )
                else:
                    financial_errors = await self._validate_current_year_data(
                        request.current_year_data
                    )
                errors.extend(financial_errors)

            if hasattr(request, "historical_years_data") and request.historical_years_data:
                if is_ebitda_only:
                    historical_errors = await self._validate_ebitda_only_historical_data(
                        request.historical_years_data
                    )
                else:
                    historical_errors = await self._validate_historical_data(
                        request.historical_years_data
                    )
                errors.extend(historical_errors)

            # Validate market data (if present)
            if hasattr(request, "market_data") and request.market_data:
                market_errors = validate_market_data(request.market_data, self.logger)
                errors.extend(market_errors)

            # Validate methodology (if present)
            if hasattr(request, "methodology") and request.methodology:
                methodology_errors = validate_methodology(
                    request.methodology,
                    request.current_year_data,
                    getattr(request, "business_type", None),
                    self.logger,
                )
                errors.extend(methodology_errors)

            # Validate assumptions (if present)
            if hasattr(request, "assumptions") and request.assumptions:
                assumption_errors = validate_assumptions(request.assumptions, self.logger)
                errors.extend(assumption_errors)

            # Validate owner profile if provided
            if hasattr(request, "owner_profile") and request.owner_profile:
                profile_errors = validate_owner_profile(request.owner_profile, self.logger)
                warnings.extend(profile_errors)  # Owner profile issues are warnings

            # Validate business context if provided
            if hasattr(request, "business_context") and request.business_context:
                context_errors = validate_business_context(request.business_context, self.logger)
                warnings.extend(context_errors)  # Business context issues are warnings

            is_valid = len(errors) == 0

            # DEBUG: failures still log at WARN; success doesn't need INFO.
            self.logger.debug(
                "Valuation request validation completed",
                is_valid=is_valid,
                errors=len(errors),
                warnings=len(warnings),
            )

            return ValidationResponse(is_valid=is_valid, errors=errors, warnings=warnings)

        except Exception as e:
            self.logger.error(f"Error validating valuation request: {e}")
            return ValidationResponse(
                is_valid=False,
                errors=[
                    ValidationError(
                        field="validation_system",
                        message=f"Validation system error: {str(e)}",
                        value=None,
                    )
                ],
            )

    async def _validate_current_year_data(self, current_year_data) -> List[ValidationError]:
        """Compatibility wrapper for non-startup current-year validation."""
        return validate_current_year_data(current_year_data)

    async def _validate_startup_current_year_data(
        self,
        current_year_data,
        startup_inputs: Optional[Any] = None,
    ) -> List[ValidationError]:
        """Compatibility wrapper for startup current-year validation."""
        return validate_startup_current_year_data(current_year_data, startup_inputs)

    async def _validate_historical_data(self, historical_data) -> List[ValidationError]:
        """Compatibility wrapper for historical row validation."""
        return validate_historical_data(historical_data)

    async def _validate_ebitda_only_current_year_data(
        self, current_year_data
    ) -> List[ValidationError]:
        """Compatibility wrapper for EBITDA-only current-year validation."""
        return validate_ebitda_only_current_year_data(current_year_data)

    async def _validate_ebitda_only_historical_data(
        self, historical_data
    ) -> List[ValidationError]:
        """Compatibility wrapper for EBITDA-only historical validation."""
        return validate_ebitda_only_historical_data(historical_data)
