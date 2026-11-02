"""
Schema Adapter for Valuation API

This module provides transformation between the new unified schema (schemas.py)
and the legacy internal schema (valuation_types.py) to maintain backward
compatibility with existing orchestrator and processor components.

Author: Upswitch Engineering Team
Date: October 2025
Status: Production Ready
"""

from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from src.api.schemas import QuickValuationRequest, ValuationRequest
from src.utils.decimal_helpers import from_decimal, to_decimal
from src.utils.exceptions import DataQualityError, ValidationError
from src.utils.fiscal_year import get_current_filing_year
from src.utils.logging import get_logger

from .valuation_types import (
    BusinessType,
    FinancialData,
    IndustryCategory,
    MarketData,
    ValuationMethod,
)

# Built-in exceptions (AttributeError, KeyError, TypeError, ValueError) are imported directly


logger = get_logger(__name__)


def _default_market_data() -> MarketData:
    """Build default market assumptions for legacy valuation requests."""
    return MarketData(
        industry_multiple=Decimal("8.0"),  # Default EV/EBITDA multiple
        market_cap=Decimal("0.0"),  # Will be calculated
        enterprise_value=Decimal("0.0"),  # Will be calculated
        pe_ratio=Decimal("15.0"),  # Default P/E ratio
        ev_ebitda_ratio=Decimal("8.0"),  # EV/EBITDA ratio
        price_to_sales=Decimal("2.0"),  # Price to sales ratio
        price_to_book=Decimal("1.5"),  # Price to book ratio
        dividend_yield=Decimal("0.03"),  # Dividend yield
        beta=Decimal("1.0"),  # Beta coefficient
        risk_free_rate=Decimal("0.05"),  # Risk-free rate
        market_risk_premium=Decimal("0.07"),  # Market risk premium
    )


class SchemaAdapter:
    """Transforms new schema to legacy format for internal processing"""

    @staticmethod
    def transform_valuation_request(new_request: ValuationRequest) -> Dict[str, Any]:
        """
        Transform new ValuationRequest to legacy format expected by orchestrator

        Args:
            new_request: New schema ValuationRequest

        Returns:
            Dict with legacy format data
        """
        try:
            logger.info(
                "Transforming valuation request to legacy format",
                company_name=new_request.company_name,
            )

            # Transform current year data to FinancialData format
            current_data = new_request.current_year_data
            financial_data = FinancialData(
                revenue=current_data.revenue,
                ebitda=current_data.ebitda,
                net_income=current_data.net_income or Decimal("0.0"),
                total_assets=current_data.total_assets or Decimal("0.0"),
                total_debt=current_data.total_debt or Decimal("0.0"),
                cash=current_data.cash or Decimal("0.0"),
                working_capital=current_data.current_assets or Decimal("0.0"),
                capex=current_data.capex or Decimal("0.0"),
                depreciation=current_data.depreciation or Decimal("0.0"),
                tax_rate=Decimal("0.25"),  # Default tax rate
                growth_rate=Decimal("0.1"),  # Default growth rate
                discount_rate=Decimal("0.12"),  # Default discount rate
                terminal_growth_rate=Decimal("0.03"),  # Default terminal growth
                year=current_data.year,
            )

            # Generate market data with reasonable defaults
            market_data = _default_market_data()

            # Determine methodology based on available data
            methodology = SchemaAdapter._determine_methodology(new_request)

            # Transform business type
            business_type = SchemaAdapter._map_business_type(new_request.business_model)

            # Transform industry
            industry = SchemaAdapter._map_industry(new_request.industry)
            business_context = (
                dict(new_request.business_context)
                if isinstance(getattr(new_request, "business_context", None), dict)
                else {}
            )
            business_context.update(
                {
                    "founding_year": new_request.founding_year,
                    "country_code": new_request.country_code,
                    "comparables": new_request.comparables or [],
                }
            )

            # Create a simple object that mimics the legacy ValuationRequest structure
            class LegacyValuationRequest:
                def __init__(self, **kwargs):
                    for key, value in kwargs.items():
                        setattr(self, key, value)

            # Build legacy request format
            legacy_request = LegacyValuationRequest(
                company_name=new_request.company_name,
                business_name=new_request.company_name,
                country_code=new_request.country_code,
                registration_number=getattr(new_request, "registration_number", None),
                kbo_number=getattr(new_request, "kbo_number", None),
                kvk_number=getattr(new_request, "kvk_number", None),
                vat_number=getattr(new_request, "vat_number", None),
                legal_form=getattr(new_request, "legal_form", None),
                postal_code=getattr(new_request, "postal_code", None),
                city=getattr(new_request, "city", None),
                business_type=business_type,
                industry=industry,
                financial_data=financial_data,
                market_data=market_data,
                methodology=methodology,
                assumptions={
                    "projection_years": new_request.projection_years,
                    "use_dcf": new_request.use_dcf,
                    "use_multiples": new_request.use_multiples,
                    "recurring_revenue_percentage": new_request.recurring_revenue_percentage,
                    "number_of_employees": new_request.number_of_employees,
                    "time_horizon": new_request.projection_years,
                    "terminal_growth_rate": Decimal("0.03"),
                    "discount_rate": Decimal("0.12"),
                    "risk_free_rate": Decimal("0.05"),
                    "market_risk_premium": Decimal("0.07"),
                    "beta": Decimal("1.0"),
                },
                owner_profile=None,  # Not provided in new schema
                business_context=business_context,
            )

            logger.info(
                "Successfully transformed valuation request",
                business_name=new_request.company_name,
                methodology=methodology.value,
            )

            return legacy_request

        except (
            ValidationError,
            DataQualityError,
            ValueError,
            TypeError,
            AttributeError,
            KeyError,
        ) as e:
            logger.error(
                f"Error transforming valuation request: {e}",
                extra={"error_type": type(e).__name__},
                exc_info=True,
            )
            raise ValidationError(f"Failed to transform valuation request: {str(e)}") from e

    @staticmethod
    def transform_quick_valuation_request(new_request: QuickValuationRequest) -> Dict[str, Any]:
        """
        Transform new QuickValuationRequest to legacy format

        Args:
            new_request: New schema QuickValuationRequest

        Returns:
            Dict with legacy format data
        """
        try:
            logger.info(
                "Transforming quick valuation request to legacy format",
                company_name=getattr(new_request, "company_name", "Unknown"),
            )

            # Create minimal financial data
            financial_data = FinancialData(
                revenue=new_request.revenue,
                ebitda=new_request.ebitda,
                net_income=new_request.ebitda * Decimal("0.7"),  # Estimate
                total_assets=new_request.revenue * Decimal("2.0"),  # Estimate
                total_debt=new_request.total_debt or Decimal("0.0"),
                cash=new_request.cash or Decimal("0.0"),
                working_capital=new_request.revenue * Decimal("0.1"),  # Estimate
                capex=new_request.revenue * Decimal("0.05"),  # Estimate
                depreciation=new_request.revenue * Decimal("0.03"),  # Estimate
                tax_rate=Decimal("0.25"),
                growth_rate=Decimal("0.1"),
                discount_rate=Decimal("0.12"),
                terminal_growth_rate=Decimal("0.03"),
                year=get_current_filing_year(),
            )

            # Create a simple object that mimics the original QuickValuationRequest structure
            class LegacyQuickValuationRequest:
                def __init__(self, **kwargs):
                    for key, value in kwargs.items():
                        setattr(self, key, value)

            # Build legacy request format that matches the original QuickValuationRequest
            company_name = getattr(new_request, "company_name", None) or "Quick Valuation"
            legacy_request = LegacyQuickValuationRequest(
                company_name=company_name,
                business_type=BusinessType.SME,
                industry=SchemaAdapter._map_industry(new_request.industry),
                revenue=new_request.revenue,
                ebitda=new_request.ebitda,
                country_code=new_request.country_code,
                registration_number=getattr(new_request, "registration_number", None),
                kbo_number=getattr(new_request, "kbo_number", None),
                kvk_number=getattr(new_request, "kvk_number", None),
                vat_number=getattr(new_request, "vat_number", None),
                legal_form=getattr(new_request, "legal_form", None),
                postal_code=getattr(new_request, "postal_code", None),
                city=getattr(new_request, "city", None),
                business_type_id=getattr(new_request, "business_type_id", None),
                owner_role=None,
                owner_hours=None,
                employee_count=None,
            )

            logger.info("Successfully transformed quick valuation request")
            return legacy_request

        except (
            ValidationError,
            DataQualityError,
            ValueError,
            TypeError,
            AttributeError,
            KeyError,
        ) as e:
            logger.error(
                f"Error transforming quick valuation request: {e}",
                extra={"error_type": type(e).__name__},
                exc_info=True,
            )
            raise ValidationError(f"Failed to transform quick valuation request: {str(e)}") from e

    @staticmethod
    def _determine_methodology(request: ValuationRequest) -> ValuationMethod:
        """Determine the best valuation methodology based on available data"""
        if request.use_dcf and request.use_multiples:
            return ValuationMethod.HYBRID
        elif request.use_dcf:
            return ValuationMethod.DCF
        elif request.use_multiples:
            return ValuationMethod.MULTIPLES
        else:
            # Default to hybrid for comprehensive valuations
            return ValuationMethod.HYBRID

    @staticmethod
    def _map_business_type(business_model) -> BusinessType:
        """Map business model to business type"""
        if hasattr(business_model, "value"):
            business_model = business_model.value

        mapping = {
            "b2b_saas": BusinessType.STARTUP,
            "b2c": BusinessType.SME,
            "marketplace": BusinessType.STARTUP,
            "ecommerce": BusinessType.SME,
            "manufacturing": BusinessType.MANUFACTURING,
            "services": BusinessType.SERVICES,
            "other": BusinessType.SME,
        }

        return mapping.get(business_model, BusinessType.SME)

    @staticmethod
    def _map_industry(industry) -> IndustryCategory:
        """Map industry to industry category"""
        if hasattr(industry, "value"):
            industry = industry.value

        mapping = {
            "technology": IndustryCategory.TECHNOLOGY,
            "manufacturing": IndustryCategory.MANUFACTURING,
            "retail": IndustryCategory.RETAIL,
            "services": IndustryCategory.SERVICES,
            "healthcare": IndustryCategory.HEALTHCARE,
            "finance": IndustryCategory.FINANCE,
            "real_estate": IndustryCategory.REAL_ESTATE,
            "hospitality": IndustryCategory.HOSPITALITY,
            "construction": IndustryCategory.CONSTRUCTION,
            "other": IndustryCategory.OTHER,
        }

        return mapping.get(industry, IndustryCategory.OTHER)
