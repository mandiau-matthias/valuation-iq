"""Pure request-validation checks for legacy valuation endpoints."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from .valuation_types import (
    BusinessType,
    FinancialData,
    IndustryCategory,
    MarketData,
    ValidationError,
    ValuationMethod,
)


def validate_business_name(business_name: str, logger) -> List[ValidationError]:
    """Validate business name."""
    try:
        errors = []

        if not business_name or not business_name.strip():
            errors.append(
                ValidationError(
                    field="business_name",
                    message="Business name is required",
                    value=business_name,
                )
            )
        elif len(business_name.strip()) < 2:
            errors.append(
                ValidationError(
                    field="business_name",
                    message="Business name must be at least 2 characters long",
                    value=business_name,
                )
            )
        elif len(business_name) > 100:
            errors.append(
                ValidationError(
                    field="business_name",
                    message="Business name must be less than 100 characters",
                    value=business_name,
                )
            )

        return errors

    except Exception as e:
        logger.error(f"Error validating business name: {e}")
        return [
            ValidationError(
                field="business_name",
                message=f"Error validating business name: {str(e)}",
                value=business_name,
            )
        ]


def validate_quick_financial_data(
    revenue: Decimal,
    ebitda: Decimal,
    logger,
) -> List[ValidationError]:
    """Validate financial data for quick valuation."""
    try:
        errors = []

        if revenue is None:
            errors.append(
                ValidationError(field="revenue", message="Revenue is required", value=revenue)
            )
        elif revenue < 0:
            errors.append(
                ValidationError(
                    field="revenue", message="Revenue must be non-negative", value=revenue
                )
            )
        elif revenue > 1000000000000:
            errors.append(
                ValidationError(
                    field="revenue", message="Revenue seems unreasonably high", value=revenue
                )
            )

        if ebitda is None:
            errors.append(
                ValidationError(field="ebitda", message="EBITDA is required", value=ebitda)
            )
        elif ebitda > revenue:
            errors.append(
                ValidationError(
                    field="ebitda",
                    message="EBITDA cannot be greater than revenue",
                    value=ebitda,
                )
            )
        elif ebitda < -revenue:
            errors.append(
                ValidationError(
                    field="ebitda",
                    message="EBITDA loss seems unreasonably high",
                    value=ebitda,
                )
            )

        return errors

    except Exception as e:
        logger.error(f"Error validating quick financial data: {e}")
        return [
            ValidationError(
                field="financial_data",
                message=f"Error validating financial data: {str(e)}",
                value={"revenue": revenue, "ebitda": ebitda},
            )
        ]


def validate_business_type_industry(
    business_type: BusinessType,
    industry: IndustryCategory,
    logger,
) -> List[ValidationError]:
    """Validate business type and industry combination."""
    try:
        errors = []
        incompatible_combinations = {
            (
                BusinessType.STARTUP,
                IndustryCategory.MINING,
            ): "Startups are unlikely in mining industry",
            (
                BusinessType.STARTUP,
                IndustryCategory.UTILITIES,
            ): "Startups are unlikely in utilities industry",
            (
                BusinessType.FRANCHISE,
                IndustryCategory.TECHNOLOGY,
            ): "Franchises are rare in technology industry",
        }

        combination = (business_type, industry)
        if combination in incompatible_combinations:
            errors.append(
                ValidationError(
                    field="business_type_industry",
                    message=incompatible_combinations[combination],
                    value={"business_type": business_type.value, "industry": industry.value},
                )
            )

        return errors

    except Exception as e:
        logger.error(f"Error validating business type and industry: {e}")
        return [
            ValidationError(
                field="business_type_industry",
                message=f"Error validating business type and industry: {str(e)}",
                value={"business_type": business_type.value, "industry": industry.value},
            )
        ]


def validate_optional_fields(
    employee_count: Optional[int],
    owner_role: Optional[str],
    owner_hours: Optional[int],
    logger,
) -> List[str]:
    """Validate optional fields and return warnings."""
    try:
        warnings = []

        if employee_count is not None:
            if employee_count < 0:
                warnings.append("Employee count should be non-negative")
            elif employee_count > 1000000:
                warnings.append("Employee count seems unreasonably high")

        if owner_hours is not None:
            if owner_hours < 0:
                warnings.append("Owner hours should be non-negative")
            elif owner_hours > 168:
                warnings.append("Owner hours exceed 168 hours per week")

        return warnings

    except Exception as e:
        logger.error(f"Error validating optional fields: {e}")
        return [f"Error validating optional fields: {str(e)}"]


def validate_business_information(
    business_name: str,
    business_type: BusinessType,
    industry: IndustryCategory,
    logger,
) -> List[ValidationError]:
    """Validate business information."""
    try:
        errors = []
        errors.extend(validate_business_name(business_name, logger))
        errors.extend(validate_business_type_industry(business_type, industry, logger))
        return errors

    except Exception as e:
        logger.error(f"Error validating business information: {e}")
        return [
            ValidationError(
                field="business_information",
                message=f"Error validating business information: {str(e)}",
                value={
                    "business_name": business_name,
                    "business_type": business_type.value,
                    "industry": industry.value,
                },
            )
        ]


def validate_market_data(
    market_data: MarketData,
    logger,
) -> List[ValidationError]:
    """Validate market data."""
    try:
        errors = []

        if market_data.pe_ratio < 0:
            errors.append(
                ValidationError(
                    field="market_data.pe_ratio",
                    message="P/E ratio must be non-negative",
                    value=market_data.pe_ratio,
                )
            )

        if market_data.ev_ebitda_ratio < 0:
            errors.append(
                ValidationError(
                    field="market_data.ev_ebitda_ratio",
                    message="EV/EBITDA ratio must be non-negative",
                    value=market_data.ev_ebitda_ratio,
                )
            )

        if market_data.beta < 0 or market_data.beta > 5:
            errors.append(
                ValidationError(
                    field="market_data.beta",
                    message="Beta should be between 0 and 5",
                    value=market_data.beta,
                )
            )

        if market_data.risk_free_rate < 0 or market_data.risk_free_rate > 0.5:
            errors.append(
                ValidationError(
                    field="market_data.risk_free_rate",
                    message="Risk-free rate should be between 0% and 50%",
                    value=market_data.risk_free_rate,
                )
            )

        if market_data.market_risk_premium < 0 or market_data.market_risk_premium > 0.5:
            errors.append(
                ValidationError(
                    field="market_data.market_risk_premium",
                    message="Market risk premium should be between 0% and 50%",
                    value=market_data.market_risk_premium,
                )
            )

        return errors

    except Exception as e:
        logger.error(f"Error validating market data: {e}")
        return [
            ValidationError(
                field="market_data",
                message=f"Error validating market data: {str(e)}",
                value=market_data,
            )
        ]


def validate_methodology(
    methodology: ValuationMethod,
    financial_data: FinancialData,
    business_type: BusinessType,
    logger,
) -> List[ValidationError]:
    """Validate methodology appropriateness."""
    try:
        errors = []
        inappropriate_methodologies = {
            (
                BusinessType.STARTUP,
                ValuationMethod.ASSET_BASED,
            ): "Asset-based valuation not suitable for startups",
            (
                BusinessType.STARTUP,
                ValuationMethod.MARKET,
            ): "Market valuation not suitable for startups",
            (
                BusinessType.MANUFACTURING,
                ValuationMethod.INCOME,
            ): "Income method may not be optimal for manufacturing",
        }

        combination = (business_type, methodology)
        if combination in inappropriate_methodologies:
            errors.append(
                ValidationError(
                    field="methodology",
                    message=inappropriate_methodologies[combination],
                    value=methodology.value,
                )
            )

        if methodology == ValuationMethod.DCF:
            if financial_data.growth_rate is None or financial_data.discount_rate is None:
                errors.append(
                    ValidationError(
                        field="methodology",
                        message="DCF methodology requires growth rate and discount rate",
                        value=methodology.value,
                    )
                )

        return errors

    except Exception as e:
        logger.error(f"Error validating methodology: {e}")
        return [
            ValidationError(
                field="methodology",
                message=f"Error validating methodology: {str(e)}",
                value=methodology.value,
            )
        ]


def validate_assumptions(
    assumptions: Mapping[str, object],
    logger,
) -> List[ValidationError]:
    """Validate valuation assumptions."""
    try:
        errors = []
        required_assumptions = ["time_horizon", "terminal_growth_rate"]
        for assumption in required_assumptions:
            if assumption not in assumptions:
                errors.append(
                    ValidationError(
                        field=f"assumptions.{assumption}",
                        message=f"Required assumption '{assumption}' is missing",
                        value=None,
                    )
                )

        if "time_horizon" in assumptions:
            time_horizon = assumptions["time_horizon"]
            if not isinstance(time_horizon, int) or time_horizon < 1 or time_horizon > 20:
                errors.append(
                    ValidationError(
                        field="assumptions.time_horizon",
                        message="Time horizon should be an integer between 1 and 20 years",
                        value=time_horizon,
                    )
                )

        if "terminal_growth_rate" in assumptions:
            terminal_growth = assumptions["terminal_growth_rate"]
            if (
                not isinstance(terminal_growth, (int, float))
                or terminal_growth < 0
                or terminal_growth > 0.1
            ):
                errors.append(
                    ValidationError(
                        field="assumptions.terminal_growth_rate",
                        message="Terminal growth rate should be between 0% and 10%",
                        value=terminal_growth,
                    )
                )

        return errors

    except Exception as e:
        logger.error(f"Error validating assumptions: {e}")
        return [
            ValidationError(
                field="assumptions",
                message=f"Error validating assumptions: {str(e)}",
                value=assumptions,
            )
        ]


def validate_owner_profile(owner_profile: Mapping[str, object], logger) -> List[str]:
    """Validate owner profile data."""
    try:
        warnings = []
        required_fields = ["role", "experience_years"]
        for field in required_fields:
            if field not in owner_profile:
                warnings.append(f"Owner profile missing '{field}' field")

        if "experience_years" in owner_profile:
            experience = owner_profile["experience_years"]
            if not isinstance(experience, (int, float)) or experience < 0 or experience > 50:
                warnings.append("Owner experience should be between 0 and 50 years")

        return warnings

    except Exception as e:
        logger.error(f"Error validating owner profile: {e}")
        return [f"Error validating owner profile: {str(e)}"]


def validate_business_context(business_context: Mapping[str, object], logger) -> List[str]:
    """Validate business context data."""
    try:
        warnings = []

        if "founded_year" in business_context:
            founded_year = business_context["founded_year"]
            current_year = datetime.now().year
            if (
                not isinstance(founded_year, int)
                or founded_year < 1800
                or founded_year > current_year
            ):
                warnings.append(f"Founded year should be between 1800 and {current_year}")

        return warnings

    except Exception as e:
        logger.error(f"Error validating business context: {e}")
        return [f"Error validating business context: {str(e)}"]


def load_validation_rules() -> dict[str, object]:
    """Load validation rules."""
    return {
        "business_name": {"min_length": 2, "max_length": 100, "required": True},
        "revenue": {"min_value": 0, "max_value": 1000000000000, "required": True},
        "ebitda": {"max_ratio_to_revenue": Decimal("1.0"), "required": True},
        "growth_rate": {"min_value": -Decimal("1.0"), "max_value": Decimal("2.0")},
        "discount_rate": {"min_value": Decimal("0.0"), "max_value": Decimal("1.0")},
    }


def load_business_type_rules() -> dict[str, object]:
    """Load business type validation rules."""
    return {
        "startup": {
            "min_revenue": 0,
            "max_revenue": 10000000,
            "suitable_methodologies": ["dcf", "multiples"],
        },
        "sme": {
            "min_revenue": 100000,
            "max_revenue": 100000000,
            "suitable_methodologies": ["dcf", "multiples", "asset_based"],
        },
        "enterprise": {
            "min_revenue": 10000000,
            "suitable_methodologies": ["dcf", "multiples", "market"],
        },
    }


def load_industry_rules() -> dict[str, object]:
    """Load industry validation rules."""
    return {
        "technology": {
            "typical_multiples": {"pe": 15, "ev_ebitda": 12},
            "growth_expectations": "high",
        },
        "manufacturing": {
            "typical_multiples": {"pe": 12, "ev_ebitda": 8},
            "growth_expectations": "moderate",
        },
        "retail": {
            "typical_multiples": {"pe": 10, "ev_ebitda": 6},
            "growth_expectations": "low",
        },
    }
