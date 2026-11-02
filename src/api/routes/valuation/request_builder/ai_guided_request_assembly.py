"""Request assembly helpers for AI-guided valuation conversion."""

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Dict, List, Optional

from src.api.schemas import ValuationRequest, YearDataInput
from src.domain.models import BusinessModel

from .ai_guided_normalization import RegistryIdentity
from .ai_guided_partial import optional_amount
from .valuation_request_builder import ValuationRequestBuilder


@dataclass(frozen=True)
class AIGuidedRequestParts:
    company_name: str
    country_code: str
    industry: str
    business_model: BusinessModel
    founding_year: int
    current_year: int
    revenue: Decimal
    ebitda: Decimal
    current_year_data: YearDataInput
    number_of_employees: Optional[int]
    number_of_owners: Optional[int]
    recurring_revenue_percentage: Decimal
    business_type_id: object
    business_type: object
    shares_for_sale: Decimal
    registry_identity: RegistryIdentity
    business_context: Optional[Dict[str, Any]]
    is_sole_trader: object
    historical_years_data: List[YearDataInput]


def build_current_year_data(
    *,
    collected_data: Dict[str, Any],
    current_year: int,
    revenue: Decimal,
    ebitda: Decimal,
) -> YearDataInput:
    return YearDataInput(
        year=current_year,
        revenue=revenue,
        ebitda=ebitda,
        financial_observations=collected_data.get("financial_observations", {}),
        accounting_basis_policy=collected_data.get("accounting_basis_policy"),
        **{
            field: optional_amount(collected_data, field)
            for field in (
                "operating_impairments",
                "operating_provisions",
                "non_recurring_operating_expenses",
                "non_recurring_financial_expenses",
                "unclassified_pnl_expenses",
                "total_operating_income",
                "non_recurring_operating_income",
                "non_recurring_financial_income",
                "unclassified_pnl_income",
                "operating_revenue",
                "financial_income",
                "extraordinary_income",
                "cogs",
                "gross_profit",
                "operating_expenses",
                "ebit",
                "depreciation",
                "amortization",
                "depreciation_amortization",
                "interest_expense",
                "tax_expense",
                "owner_director_compensation",
                "personnel_costs",
                "rent_expense",
                "net_income",
                "total_assets",
                "current_assets",
                "fixed_assets",
                "cash",
                "accounts_receivable",
                "accounts_payable",
                "inventory",
                "total_liabilities",
                "current_liabilities",
                "short_term_debt",
                "total_debt",
                "total_equity",
            )
        },
    )


def build_ai_guided_request(parts: AIGuidedRequestParts) -> ValuationRequest:
    identity = parts.registry_identity
    request_builder = (
        ValuationRequestBuilder()
        .with_company_info(
            parts.company_name,
            parts.country_code,
            parts.industry,
            parts.business_model,
        )
        .with_registry_identity(
            registration_number=identity.registration_number,
            kbo_number=identity.kbo_number,
            kvk_number=identity.kvk_number,
            vat_number=identity.vat_number,
            legal_form=identity.legal_form,
            postal_code=identity.postal_code,
            city=identity.city,
        )
        .with_current_year_data(**parts.current_year_data.model_dump())
        .with_founding_year(parts.founding_year)
        .with_employees(parts.number_of_employees, parts.number_of_owners)
        .with_recurring_revenue(parts.recurring_revenue_percentage)
        .with_business_type_id(parts.business_type_id)
        .with_business_type(parts.business_type)
        .with_shares_for_sale(parts.shares_for_sale)
        .with_methodology(use_dcf=True, use_multiples=True)
    )

    if parts.business_context is not None:
        request_builder = request_builder.with_business_context(parts.business_context)
    if parts.is_sole_trader is not None:
        request_builder = request_builder.with_is_sole_trader(bool(parts.is_sole_trader))
    if parts.historical_years_data:
        request_builder = request_builder.with_historical_data(parts.historical_years_data)

    return request_builder.build()


def business_model_log_value(business_model: BusinessModel) -> object:
    return business_model.value if hasattr(business_model, "value") else str(business_model)


def request_input_log_context(parts: AIGuidedRequestParts) -> Dict[str, object]:
    return {
        "company_name": parts.company_name,
        "country_code": parts.country_code,
        "industry": parts.industry,
        "business_model": business_model_log_value(parts.business_model),
        "founding_year": parts.founding_year,
        "revenue": parts.revenue,
        "ebitda": parts.ebitda,
        "is_sole_trader": parts.is_sole_trader,
        "shares_for_sale": parts.shares_for_sale,
        "number_of_employees": parts.number_of_employees,
        "number_of_owners": parts.number_of_owners,
    }


def conversion_log_context(parts: AIGuidedRequestParts) -> Dict[str, object]:
    return {
        "company_name": parts.company_name,
        "industry": parts.industry,
        "country_code": parts.country_code,
        "revenue": parts.revenue,
        "ebitda": parts.ebitda,
        "founding_year": parts.founding_year,
        "number_of_employees": parts.number_of_employees,
        "number_of_owners": parts.number_of_owners,
        "shares_for_sale": parts.shares_for_sale,
        "recurring_revenue_percentage": parts.recurring_revenue_percentage,
        "business_type": parts.business_type,
        "is_sole_trader": parts.is_sole_trader,
        "business_type_id": parts.business_type_id,
        "has_historical_data": len(parts.historical_years_data) > 0,
        "historical_years_count": len(parts.historical_years_data),
        "source": "ai_guided_conversation",
    }
