from src.utils.exceptions import APIError, MultiplesCalculationError

"""
Progressive Data Transformer
Maps conversation context to ValuationRequest and ValuationResponse to template data
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime

from typing import TYPE_CHECKING

# Import runtime types needed for function bodies
from src.api.routes.valuation.valuation_types import QuickValuationRequest, IndustryCategory, BusinessType
from src.api.schemas import ValuationRequest, YearDataInput

if TYPE_CHECKING:
    from src.api.routes.valuation.valuation_types import ValuationResponse

from src.services.interfaces.request_response_protocol import (
    QuickValuationRequestProtocol,
    ValuationResponseProtocol,
    ValuationRequestProtocol,
)
from src.services.interfaces.api_protocols import (
    YearDataInputProtocol,
    IndustryCategoryProtocol,
    BusinessTypeProtocol,
)
from src.domain.models import IndustryCode, BusinessModel
from decimal import Decimal
from src.utils.country_code import normalize_iso3166_alpha2
from src.utils.decimal_helpers import to_decimal, from_decimal
from src.utils.fiscal_year import get_current_filing_year

logger = logging.getLogger(__name__)


class ProgressiveDataTransformer:
    """
    Transforms data between conversation context and valuation services
    """

    @staticmethod
    def conversation_to_quick_request(context: Dict[str, Any]) -> QuickValuationRequest:
        """
        Convert conversation context to ValuationRequest format

        Args:
            context: Conversation context from triage system

        Returns:
            ValuationRequest object for real calculations
        """
        logger.debug(f"[TRANSFORMER] Converting context to QuickValuationRequest | fields={list(context.keys())}")

        try:
            # Extract basic company information
            company_name = context.get('company_name', 'Unknown Company')
            industry_str = context.get('industry', 'technology')

            logger.debug(f"[TRANSFORMER] Extracted company_name: {company_name}")
            logger.debug(f"[TRANSFORMER] Extracted industry: {industry_str}")

            # Map industry string to IndustryCategory enum
            industry_mapping = {
                'technology': IndustryCategory.TECHNOLOGY,
                'software': IndustryCategory.TECHNOLOGY,
                'saas': IndustryCategory.TECHNOLOGY,
                'manufacturing': IndustryCategory.MANUFACTURING,
                'retail': IndustryCategory.RETAIL,
                'healthcare': IndustryCategory.HEALTHCARE,
                'finance': IndustryCategory.FINANCE,
                'consulting': IndustryCategory.SERVICES,
                'services': IndustryCategory.SERVICES,
                'construction': IndustryCategory.CONSTRUCTION,
                'real_estate': IndustryCategory.REAL_ESTATE,
                'transportation': IndustryCategory.TRANSPORTATION,
                'energy': IndustryCategory.UTILITIES,
                'education': IndustryCategory.EDUCATION,
                'entertainment': IndustryCategory.ENTERTAINMENT,
                'agriculture': IndustryCategory.AGRICULTURE,
                'other': IndustryCategory.OTHER
            }

            industry = industry_mapping.get(industry_str.lower(), IndustryCategory.OTHER)
            logger.debug(f"[TRANSFORMER] Mapped industry: {industry_str} -> {industry}")

            # Extract financial data
            revenue = to_decimal(context.get('revenue', 0))
            ebitda = to_decimal(context.get('ebitda', 0))
            net_income = to_decimal(context.get('net_income', 0))
            total_assets = to_decimal(context.get('total_assets', 0))
            total_debt = to_decimal(context.get('total_debt', 0))
            cash = to_decimal(context.get('cash', 0))

            logger.debug(f"[TRANSFORMER] Extracted financial data | revenue={revenue}, ebitda={ebitda}")

            # Missing fields
            if context.get('revenue') is None:
                logger.warning(f"[TRANSFORMER] Missing revenue, using default: 0")

            # Extract growth and projections
            growth_rate = to_decimal(context.get('growth_rate', Decimal('0.05')))  # Default 5%
            projection_years = int(context.get('projection_years', 5))
            terminal_growth_rate = to_decimal(context.get('terminal_growth_rate', Decimal('0.03')))  # Default 3%

            # Extract business type
            business_type_str = context.get('business_type', 'service')
            business_type_mapping = {
                'product': BusinessType.STARTUP,
                'service': BusinessType.SERVICES,
                'saas': BusinessType.STARTUP,
                'ecommerce': BusinessType.E_COMMERCE,
                'marketplace': BusinessType.STARTUP,
                'consulting': BusinessType.CONSULTING,
                'agency': BusinessType.SERVICES,
                'other': BusinessType.SME
            }

            business_type = business_type_mapping.get(business_type_str.lower(), BusinessType.SERVICES)
            logger.debug(f"[TRANSFORMER] Mapped business_type: {business_type_str} -> {business_type}")

            # Extract owner information
            owner_salary = to_decimal(context.get('owner_salary', 0))
            owner_commitment = context.get('owner_commitment', 'full_time')
            owner_dependency = context.get('owner_dependency', 'high')
            benchmark_contract = context.get('benchmark_contract') or context.get('benchmarkContract')
            multiples_metadata = dict(context.get('multiples_metadata') or {})
            if benchmark_contract and not multiples_metadata.get('benchmark_contract'):
                multiples_metadata['benchmark_contract'] = benchmark_contract

            logger.debug(f"[TRANSFORMER] Creating QuickValuationRequest | business_name={company_name} | industry={industry} | revenue={revenue}")

            # Create QuickValuationRequest
            valuation_request = QuickValuationRequest(
                business_name=company_name,
                revenue=revenue,
                ebitda=ebitda,
                industry=industry_str,  # Use string, not enum
                country_code=normalize_iso3166_alpha2(context.get('country_code')),
                business_type=business_type,
                business_type_id=context.get('business_type_id'),
                benchmark_contract=benchmark_contract,
                multiples_metadata=multiples_metadata or None,
                allow_untrusted_multiples_fallback=(
                    context.get('allow_untrusted_multiples_fallback') is True
                ),
                employee_count=context.get('employee_count'),
                owner_role=context.get('owner_role'),
                owner_hours=context.get('owner_hours')
            )

            logger.info(f"Transformed conversation context to ValuationRequest: {company_name}")
            return valuation_request

        except (ValueError, KeyError, AttributeError) as e:
            logger.error(f"Type conversion error: {e}")
            # Return minimal valid request
            return QuickValuationRequest(
                business_name=context.get('company_name', 'Unknown'),
                revenue=0,
                ebitda=0,
                industry='other',
                country_code=normalize_iso3166_alpha2(context.get('country_code')),
                business_type=BusinessType.SERVICES
            )
        except APIError as e:
            logger.error(f"Unexpected error transforming conversation context: {e}")
            # Return minimal request to prevent failures
            return QuickValuationRequest(
                business_name=context.get('company_name', 'Unknown'),
                revenue=0,
                ebitda=0,
                industry='other',
                country_code=normalize_iso3166_alpha2(context.get('country_code')),
                business_type=BusinessType.SERVICES
            )

    @staticmethod
    def conversation_to_comprehensive_request(context: Dict[str, Any]) -> ValuationRequest:
        """
        Convert conversation context to comprehensive ValuationRequest for Phases 3-4

        Args:
            context: Conversation context from triage system

        Returns:
            Comprehensive ValuationRequest object for advanced calculations
        """
        try:
            # Extract all required fields
            company_name = context.get('company_name', 'Unknown Company')
            revenue = to_decimal(context.get('revenue', 0))
            ebitda = to_decimal(context.get('ebitda', 0))
            net_income = to_decimal(context.get('net_income', 0))

            # Map to proper enums
            industry_str = context.get('industry', 'technology')
            industry = _map_to_industry_code(industry_str)

            business_type_str = context.get('business_type', 'sme')
            business_model = _map_to_business_model(business_type_str)

            # Build YearDataInput for current year
            current_year = get_current_filing_year()
            current_year_data = YearDataInput(
                year=current_year,
                revenue=revenue,
                ebitda=ebitda,
                net_income=net_income,
                cogs=context.get('cogs'),
                operating_expenses=context.get('operating_expenses'),
                total_assets=context.get('total_assets', 0),
                total_debt=context.get('total_debt', 0),
                cash=context.get('cash', 0),
                capex=context.get('capex', 0)
            )

            # Build historical data if available
            historical_years_data = []
            if 'historical_data' in context:
                for year_data in context['historical_data']:
                    historical_years_data.append(YearDataInput(**year_data))
            benchmark_contract = context.get('benchmark_contract') or context.get('benchmarkContract')
            multiples_metadata = dict(context.get('multiples_metadata') or {})
            if benchmark_contract and not multiples_metadata.get('benchmark_contract'):
                multiples_metadata['benchmark_contract'] = benchmark_contract
            metadata = dict(context.get('metadata') or {})
            if benchmark_contract and not metadata.get('benchmark_contract'):
                metadata['benchmark_contract'] = benchmark_contract

            # Create comprehensive request
            return ValuationRequest(
                company_name=company_name,
                country_code=normalize_iso3166_alpha2(context.get('country_code')),
                industry=industry,
                business_model=business_model,
                founding_year=context.get('founding_year', current_year - 5),
                current_year_data=current_year_data,
                historical_years_data=historical_years_data,
                number_of_employees=context.get('employee_count'),
                recurring_revenue_percentage=context.get('recurring_revenue_pct', Decimal('0.0')),
                business_type=context.get('business_type'),
                multiples_metadata=multiples_metadata or None,
                metadata=metadata or None,
                allow_untrusted_multiples_fallback=(
                    context.get('allow_untrusted_multiples_fallback') is True
                ),
                revenue=revenue,  # Backward compatibility
                employee_count=context.get('employee_count'),
                methodology='HYBRID'
            )

        except (ValueError, KeyError, AttributeError) as e:
            logger.error(f"Failed to build comprehensive request: {e}")
            # Return minimal valid request
            return _build_minimal_comprehensive_request(context)
        except APIError as e:
            logger.error(f"Unexpected error: {e}", exc_info=True)
            raise

    @staticmethod
    def valuation_result_to_progressive_data(
        result: ValuationResponseProtocol, 
        phase: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Transform ValuationResponse to template data format for progressive rendering

        Args:
            result: ValuationResponse from real calculations
            phase: Current phase (phase_1, phase_2, phase_3, phase_4)
            context: Original conversation context

        Returns:
            Template data dictionary
        """
        try:
            # Base template data
            template_data = {
                'company_name': result.company_name,
                'industry': result.industry.value if hasattr(result.industry, 'value') else str(result.industry),
                'report_date': datetime.now().strftime("%Y-%m-%d"),
                'valuation_id': result.valuation_id,
                'phase': phase,
                'render_timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }

            # Phase-specific data
            if phase == 'phase_1':
                # Quick preview data
                template_data.update({
                    'value_low': result.equity_value_low,
                    'value_mid': result.equity_value_mid,
                    'value_high': result.equity_value_high,
                    'confidence_score': result.confidence_score / Decimal('100.0'),  # Convert to decimal
                    'confidence_level': result.overall_confidence.value if hasattr(result.overall_confidence, 'value') else str(result.overall_confidence),
                    'methodology': 'Industry Multiples',
                    'multiple_low': getattr(result, 'revenue_multiple', Decimal('1.5')),
                    'multiple_high': getattr(result, 'revenue_multiple', Decimal('3.0')),
                    'data_completeness': Decimal('0.25'),  # 25% for phase 1
                    'industry_benchmark': getattr(result, 'industry_benchmark', 'Standard industry multiples applied')
                })

            elif phase == 'phase_2':
                # DCF and Multiples basic data
                template_data.update({
                    'dcf_data': {
                        'value_low': getattr(result, 'dcf_value_low', result.equity_value_low),
                        'value_mid': getattr(result, 'dcf_value_mid', result.equity_value_mid),
                        'value_high': getattr(result, 'dcf_value_high', result.equity_value_high),
                        'discount_rate': getattr(result, 'discount_rate', Decimal('0.10')),
                        'terminal_growth': getattr(result, 'terminal_growth_rate', Decimal('0.03'))
                    },
                    'multiples_data': {
                        'value_low': getattr(result, 'multiples_value_low', result.equity_value_low),
                        'value_mid': getattr(result, 'multiples_value_mid', result.equity_value_mid),
                        'value_high': getattr(result, 'multiples_value_high', result.equity_value_high),
                        'revenue_multiple': getattr(result, 'revenue_multiple', Decimal('2.5')),
                        'ebitda_multiple': getattr(result, 'ebitda_multiple', Decimal('8.0'))
                    },
                    'combined_value_low': result.equity_value_low,
                    'combined_value_mid': result.equity_value_mid,
                    'combined_value_high': result.equity_value_high,
                    'confidence_score': result.confidence_score / Decimal('100.0'),
                    # Read weights from the response; fall back to 0.5/0.5 only
                    # for progressive phase-2 approximations.  The production
                    # pipeline uses valuation_contract.extract_methodology_weights().
                    'methodology_weights': {
                        'dcf': getattr(result, 'dcf_weight', Decimal('0.5')),
                        'multiples': getattr(result, 'multiples_weight', Decimal('0.5'))
                    },
                    'data_completeness': Decimal('0.5')  # 50% for phase 2
                })

            elif phase == 'phase_3':
                # Advanced DCF and adjustments
                template_data.update({
                    'dcf_complete': {
                        'value_low': getattr(result, 'dcf_value_low', result.equity_value_low),
                        'value_mid': getattr(result, 'dcf_value_mid', result.equity_value_mid),
                        'value_high': getattr(result, 'dcf_value_high', result.equity_value_high),
                        'projected_cash_flows': getattr(result, 'projected_cash_flows', []),
                        'terminal_value': getattr(result, 'terminal_value', 0),
                        'discount_rate': getattr(result, 'discount_rate', Decimal('0.10')),
                        'terminal_growth_rate': getattr(result, 'terminal_growth_rate', Decimal('0.03'))
                    },
                    'adjustments': {
                        'market_adjustments': getattr(result, 'market_adjustments', {}),
                        'risk_adjustments': getattr(result, 'risk_adjustments', {}),
                        'liquidity_adjustments': getattr(result, 'liquidity_adjustments', {})
                    },
                    'final_value_low': result.equity_value_low,
                    'final_value_mid': result.equity_value_mid,
                    'final_value_high': result.equity_value_high,
                    'confidence_score': result.confidence_score / Decimal('100.0'),
                    'risk_factors': getattr(result, 'risk_factors', []),
                    'value_drivers': getattr(result, 'key_value_drivers', []),
                    'data_completeness': Decimal('0.75')  # 75% for phase 3
                })

            elif phase == 'phase_4':
                # Complete with owner analysis
                template_data.update({
                    'owner_analysis': {
                        'dependency_score': getattr(result, 'owner_dependency_score', Decimal('0.7')),
                        'risk_level': getattr(result, 'owner_risk_level', 'medium'),
                        'adjustment_factor': getattr(result, 'owner_adjustment_factor', Decimal('0.9')),
                        'recommendations': getattr(result, 'owner_recommendations', [])
                    },
                    'final_valuation': {
                        'value_low': result.equity_value_low,
                        'value_mid': result.equity_value_mid,
                        'value_high': result.equity_value_high,
                        'confidence_score': result.confidence_score / Decimal('100.0'),
                        'methodology_breakdown': getattr(result, 'methodology_breakdown', {}),
                        'sensitivity_analysis': getattr(result, 'sensitivity_analysis', {})
                    },
                    'executive_summary': getattr(result, 'valuation_summary', ''),
                    'recommendations': getattr(result, 'recommendations', []),
                    'data_completeness': Decimal('1.0')  # 100% for phase 4
                })

            # Add common fields
            template_data.update({
                'confidence_score': result.confidence_score / Decimal('100.0'),
                'confidence_level': result.overall_confidence.value if hasattr(result.overall_confidence, 'value') else str(result.overall_confidence),
                'methodology_notes': getattr(result, 'methodology_notes', ''),
                'risk_factors': getattr(result, 'risk_factors', []),
                'value_drivers': getattr(result, 'key_value_drivers', []),
                'market_insights': getattr(result, 'market_insights', 'Market analysis based on industry benchmarks')
            })

            logger.debug(f"Transformed ValuationResponse to template data for {phase}")
            return template_data

        except MultiplesCalculationError as e:
            logger.error(f"Error transforming ValuationResponse: {e}")
            # Return minimal template data
            return {
                'company_name': getattr(result, 'company_name', 'Unknown'),
                'industry': 'Unknown',
                'phase': phase,
                'value_mid': getattr(result, 'equity_value_mid', 0),
                'confidence_score': Decimal('0.5'),
                'error': str(e)
            }

    @staticmethod
    def extract_conversation_context(session_id: str, conversation_history: list) -> Dict[str, Any]:
        """
        Extract structured data from conversation history

        Args:
            session_id: Conversation session ID
            conversation_history: List of conversation steps

        Returns:
            Structured context dictionary
        """
        context = {
            'session_id': session_id,
            'company_name': None,
            'industry': None,
            'revenue': None,
            'ebitda': None,
            'growth_rate': None,
            'business_type': None,
            'owner_salary': None,
            'owner_commitment': None,
            'owner_dependency': None
        }

        try:
            # Extract data from conversation history
            for step in conversation_history:
                if step.get('type') == 'user' and step.get('field'):
                    field = step['field']
                    value = step['value']

                    # Map conversation fields to context
                    field_mapping = {
                        'company_name': 'company_name',
                        'industry': 'industry',
                        'revenue': 'revenue',
                        'ebitda': 'ebitda',
                        'net_income': 'net_income',
                        'growth_rate': 'growth_rate',
                        'business_type': 'business_type',
                        'owner_salary': 'owner_salary',
                        'owner_commitment': 'owner_commitment',
                        'owner_dependency': 'owner_dependency',
                        'total_assets': 'total_assets',
                        'total_debt': 'total_debt',
                        'cash': 'cash'
                    }

                    if field in field_mapping:
                        context[field_mapping[field]] = value

            logger.info(f"Extracted context from conversation history: {len([k for k, v in context.items() if v])} fields")
            return context

        except ValuationEngineError as e:
            logger.error(f"Error extracting conversation context: {e}")
            return context


def _map_to_industry_code(industry_str: str) -> IndustryCode:
    """Map conversation industry to IndustryCode enum"""
    mapping = {
        'technology': IndustryCode.TECHNOLOGY,
        'software': IndustryCode.TECHNOLOGY,
        'saas': IndustryCode.TECHNOLOGY,
        'manufacturing': IndustryCode.MANUFACTURING,
        'retail': IndustryCode.RETAIL,
        'healthcare': IndustryCode.HEALTHCARE,
        'finance': IndustryCode.FINANCE,
        'consulting': IndustryCode.SERVICES,
        'services': IndustryCode.SERVICES,
        'construction': IndustryCode.CONSTRUCTION,
        'real_estate': IndustryCode.REAL_ESTATE,
        'hospitality': IndustryCode.HOSPITALITY,
        'other': IndustryCode.OTHER
    }
    return mapping.get(industry_str.lower(), IndustryCode.OTHER)


def _map_to_business_model(business_type_str: str) -> BusinessModel:
    """Map conversation business type to BusinessModel enum"""
    mapping = {
        'saas': BusinessModel.B2B_SAAS,
        'b2b': BusinessModel.B2B_SAAS,
        'b2c': BusinessModel.B2C,
        'marketplace': BusinessModel.MARKETPLACE,
        'ecommerce': BusinessModel.ECOMMERCE,
        'services': BusinessModel.SERVICES,
        'manufacturing': BusinessModel.MANUFACTURING,
        'other': BusinessModel.OTHER
    }
    return mapping.get(business_type_str.lower(), BusinessModel.OTHER)


def _build_minimal_comprehensive_request(context: Dict[str, Any]) -> ValuationRequest:
    """Build minimal valid request when data is incomplete"""
    current_year = get_current_filing_year()
    return ValuationRequest(
        company_name=context.get('company_name', 'Unknown'),
        country_code=normalize_iso3166_alpha2(context.get('country_code')),
        industry=IndustryCode.OTHER,
        business_model=BusinessModel.OTHER,
        founding_year=current_year - 5,
        current_year_data=YearDataInput(
            year=current_year,
            revenue=to_decimal(context.get('revenue', 0)),
            ebitda=to_decimal(context.get('ebitda', 0)),
            net_income=0
        ),
        historical_years_data=[],
        methodology='HYBRID'
    )
