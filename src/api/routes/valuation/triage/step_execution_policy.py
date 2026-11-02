"""Step execution policy for business-type triage."""

from collections.abc import Callable
from decimal import Decimal
from typing import Protocol

from src.api.routes.valuation.triage.business_type_taxonomy import BusinessTypeCategory
from src.api.routes.valuation.triage.methodology_selection import (
    REVENUE_THRESHOLD_MEDIUM,
    REVENUE_THRESHOLD_MICRO,
    REVENUE_THRESHOLD_SMALL,
)
from src.api.schemas import ValuationRequest
from src.errors import ValidationError
from src.utils.decimal_helpers import from_decimal, to_decimal

CategoryResolver = Callable[[], BusinessTypeCategory]


class LoggerLike(Protocol):
    def debug(self, message: str, *args: object, **kwargs: object) -> object: ...

    def info(self, message: str, *args: object, **kwargs: object) -> object: ...

    def warning(self, message: str, *args: object, **kwargs: object) -> object: ...

    def error(self, message: str, *args: object, **kwargs: object) -> object: ...


def _object_has_owner_employee_data(source: object) -> bool:
    return (
        getattr(source, "number_of_owners", None) is not None
        and getattr(source, "number_of_employees", None) is not None
    )


def _request_has_owner_employee_data(request: ValuationRequest) -> bool:
    if not hasattr(request, "number_of_owners") or not hasattr(request, "number_of_employees"):
        return False
    return _object_has_owner_employee_data(request)


def _business_context_has_owner_employee_data(request: ValuationRequest) -> bool:
    if not hasattr(request, "business_context"):
        return False

    business_context = request.business_context or {}
    return (
        business_context.get("number_of_owners") is not None
        and business_context.get("number_of_employees") is not None
    )


def _current_year_data_has_owner_employee_data(request: ValuationRequest) -> bool:
    if not hasattr(request, "current_year_data"):
        return False

    current_data = request.current_year_data
    if not hasattr(current_data, "number_of_owners") or not hasattr(
        current_data, "number_of_employees"
    ):
        return False
    return _object_has_owner_employee_data(current_data)


def _has_step4_owner_employee_data(request: ValuationRequest) -> bool:
    return (
        _request_has_owner_employee_data(request)
        or _business_context_has_owner_employee_data(request)
        or _current_year_data_has_owner_employee_data(request)
    )


def check_conditional_data(
    step_number: int,
    request: ValuationRequest,
    previous_results: dict[int, object],
    *,
    logger: LoggerLike,
) -> bool:
    """Check if a step should execute based on data availability."""
    if step_number != 4:
        return True

    if not _has_step4_owner_employee_data(request):
        logger.debug(
            "Step 4 owner/employee data missing; allowing structured quality warning",
            extra={"step_number": 4},
        )

    # Step 4 deliberately executes its missing-data branch so the StepOutput
    # includes high-severity quality_warning metadata.
    return True


def check_conditional_business_type(
    step_number: int,
    request: ValuationRequest,
    previous_results: dict[int, object],
    *,
    category_resolver: CategoryResolver,
    logger: LoggerLike,
) -> bool:
    """Check if a step should execute based on business type."""
    try:
        category = category_resolver()

        if step_number == 4:
            if category == BusinessTypeCategory.SAAS_SOFTWARE:
                revenue = 0
                if hasattr(request, "current_year_data") and request.current_year_data:
                    revenue = getattr(request.current_year_data, "revenue", 0) or 0

                if revenue > 10_000_000:
                    logger.info(
                        "Step 4 skipped: Large SaaS company has lower owner dependency risk",
                        extra={
                            "step_number": 4,
                            "business_category": category.value,
                            "revenue": revenue,
                        },
                    )
                    return False

            if category == BusinessTypeCategory.PROFESSIONAL_SERVICES:
                return True

        return True

    except (ValidationError, ValueError, TypeError, AttributeError, KeyError) as e:
        logger.error(
            f"Error in check_conditional_business_type for step {step_number}: {e}",
            extra={"step_number": step_number, "error_type": type(e).__name__},
            exc_info=True,
        )
        return True


def check_conditional_size(
    step_number: int,
    request: ValuationRequest,
    previous_results: dict[int, object],
    *,
    logger: LoggerLike,
) -> bool:
    """Check if a step should execute based on company size."""
    try:
        revenue = 0
        if hasattr(request, "current_year_data") and request.current_year_data:
            revenue = getattr(request.current_year_data, "revenue", 0) or 0

        if step_number == 4 and revenue < 100_000:
            logger.info(
                "Step 4 skipped: Micro-business owner concentration is less relevant",
                extra={"step_number": 4, "revenue": revenue},
            )
            return False

        return True

    except (ValidationError, ValueError, TypeError, AttributeError, KeyError) as e:
        logger.error(
            f"Error in check_conditional_size for step {step_number}: {e}",
            extra={"step_number": step_number, "error_type": type(e).__name__},
            exc_info=True,
        )
        return True


def check_conditional_sde(
    step_number: float,
    request: ValuationRequest,
    previous_results: dict[int, object],
    *,
    category_resolver: CategoryResolver,
    logger: LoggerLike,
) -> bool:
    """Check if SDE should execute based on business characteristics."""
    try:
        revenue = Decimal("0")
        if hasattr(request, "current_year_data") and request.current_year_data:
            revenue = to_decimal(getattr(request.current_year_data, "revenue", 0) or 0)

        num_owners = 1
        if hasattr(request, "number_of_owners") and request.number_of_owners:
            num_owners = request.number_of_owners
        elif hasattr(request, "business_context"):
            business_context = request.business_context or {}
            num_owners = business_context.get("number_of_owners", 1)

        category = category_resolver()

        if revenue < REVENUE_THRESHOLD_MICRO:
            logger.debug(
                "Step 2.7 (SDE) executing: micro business",
                extra={
                    "step_number": step_number,
                    "revenue": from_decimal(revenue),
                    "reason": "micro_business",
                },
            )
            return True

        if revenue < REVENUE_THRESHOLD_SMALL and num_owners <= 3:
            logger.debug(
                "Step 2.7 (SDE) executing: small owner-operated business",
                extra={
                    "step_number": step_number,
                    "revenue": from_decimal(revenue),
                    "num_owners": num_owners,
                    "reason": "small_owner_operated",
                },
            )
            return True

        if revenue < REVENUE_THRESHOLD_MEDIUM:
            if category in (
                BusinessTypeCategory.PROFESSIONAL_SERVICES,
                BusinessTypeCategory.HEALTHCARE,
                BusinessTypeCategory.RETAIL_FOOD,
            ):
                if num_owners <= 3:
                    logger.debug(
                        "Step 2.7 (SDE) executing: medium service business, owner-operated",
                        extra={
                            "step_number": step_number,
                            "revenue": from_decimal(revenue),
                            "category": category.value,
                            "reason": "service_owner_operated",
                        },
                    )
                    return True

        logger.info(
            "Step 2.7 (SDE) skipped: business characteristics not suitable for SDE",
            extra={
                "step_number": step_number,
                "revenue": from_decimal(revenue),
                "num_owners": num_owners,
                "category": category.value,
                "reason": "not_sde_appropriate",
            },
        )
        return False

    except (ValidationError, ValueError, TypeError, AttributeError, KeyError) as e:
        logger.warning(
            f"Error in check_conditional_sde for step {step_number}: {e}",
            extra={"step_number": step_number, "error_type": type(e).__name__},
            exc_info=True,
        )
        return False


def check_conditional_asset_based(
    step_number: float,
    request: ValuationRequest,
    previous_results: dict[int, object],
    *,
    category_resolver: CategoryResolver,
    logger: LoggerLike,
) -> bool:
    """Check if Asset-Based valuation should execute."""
    try:
        category = category_resolver()

        asset_heavy_categories = {
            BusinessTypeCategory.MANUFACTURING,
            BusinessTypeCategory.CONSTRUCTION,
            BusinessTypeCategory.REAL_ESTATE,
            BusinessTypeCategory.TRANSPORTATION,
        }

        if category in asset_heavy_categories:
            logger.info(
                "Asset-Based step executing: asset-heavy business category",
                extra={
                    "step_number": step_number,
                    "category": category.value,
                    "reason": "asset_heavy_category",
                },
            )
            return True

        if hasattr(request, "asset_based_calibration"):
            asset_calibration = request.asset_based_calibration or {}
            preference = asset_calibration.get("asset_methodology_preference", 0)
            if preference and float(preference) > 0.5:
                logger.info(
                    "Asset-Based step executing: high asset methodology preference",
                    extra={
                        "step_number": step_number,
                        "preference": preference,
                        "reason": "high_asset_preference",
                    },
                )
                return True

        return False

    except (ValidationError, ValueError, TypeError, AttributeError, KeyError) as e:
        logger.warning(
            f"Error in check_conditional_asset_based for step {step_number}: {e}",
            extra={"step_number": step_number, "error_type": type(e).__name__},
            exc_info=True,
        )
        return False
