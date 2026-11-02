"""
Request Data Extractor

WHAT: Extracts data from ValuationRequest for report generation
WHY: Separates data extraction logic from transformation (SRP compliance)
HOW: Pure extraction - pulls specific fields from request object

SINGLE RESPONSIBILITY: Data extraction from ValuationRequest ONLY
"""

from typing import Dict, Any, Optional, TYPE_CHECKING
from src.utils.logging import get_logger
from src.utils.registry_identity_context import resolve_business_type_id

if TYPE_CHECKING:
    from src.api.schemas import ValuationRequest

from src.services.interfaces.request_response_protocol import ValuationRequestProtocol

logger = get_logger(__name__)


class RequestDataExtractor:
    """
    Extracts data from ValuationRequest for report generation.
    
    SINGLE RESPONSIBILITY: Request data extraction ONLY
    
    This service extracts:
    - Financial data (revenue, EBITDA, etc.)
    - Company data (name, employees, industry, etc.)
    - Historical data (years of historical data)
    - Business context (business type, location)
    
    NO transformation, NO validation, NO enrichment - pure extraction only.
    """
    
    def __init__(self):
        """Initialize request data extractor."""
        self.logger = logger
    
    def extract_financial_data(self, request: ValuationRequestProtocol) -> Dict[str, Any]:
        """
        Extract financial data from request.
        
        WHAT: Pulls revenue, EBITDA, and other financial metrics
        WHY: Financial data needed for template calculations
        HOW: Checks current_year_data and top-level fields
        
        Args:
            request: ValuationRequest
        
        Returns:
            Dict with financial data:
            - revenue: Current year revenue
            - ebitda: Current year EBITDA
            - step_1_inputs: Financial inputs for template fallback
        
        Example:
            >>> extractor = RequestDataExtractor()
            >>> financial = extractor.extract_financial_data(request)
            >>> print(financial['revenue'])  # Decimal('1000000')
        """
        financial_data = {}
        
        # Extract revenue (try current_year_data first, then top-level)
        revenue = None
        if hasattr(request, 'current_year_data') and request.current_year_data:
            revenue = getattr(request.current_year_data, 'revenue', None)
        if revenue is None and hasattr(request, 'revenue'):
            revenue = getattr(request, 'revenue', None)
        financial_data['revenue'] = revenue
        
        # Extract EBITDA
        ebitda = None
        if hasattr(request, 'current_year_data') and request.current_year_data:
            ebitda = getattr(request.current_year_data, 'ebitda', None)
        if ebitda is None and hasattr(request, 'ebitda'):
            ebitda = getattr(request, 'ebitda', None)
        financial_data['ebitda'] = ebitda
        
        # Extract step 1 inputs (financials) for template fallback calculations
        step_1_inputs = None
        if hasattr(request, 'current_year_data') and request.current_year_data:
            step_1_inputs = {
                'revenue': getattr(request.current_year_data, 'revenue', 0),
                'ebitda': getattr(request.current_year_data, 'ebitda', 0)
            }
        elif hasattr(request, 'financials') and request.financials:
            step_1_inputs = {
                'revenue': getattr(request.financials, 'revenue', 0),
                'ebitda': getattr(request.financials, 'ebitda', 0)
            }
        financial_data['step_1_inputs'] = step_1_inputs
        
        self.logger.debug(
            "Financial data extracted",
            extra={
                'has_revenue': revenue is not None,
                'has_ebitda': ebitda is not None,
                'has_step_1_inputs': step_1_inputs is not None
            }
        )
        
        return financial_data
    
    def extract_company_data(self, request: ValuationRequestProtocol) -> Dict[str, Any]:
        """
        Extract company data from request.
        
        WHAT: Pulls company name, employees, industry, etc.
        WHY: Company data needed for report header and context
        HOW: Extracts from request attributes
        
        Args:
            request: ValuationRequest
        
        Returns:
            Dict with company data:
            - company_name: Company name
            - number_of_employees: Employee count
            - industry: Industry code/name
        
        Example:
            >>> extractor = RequestDataExtractor()
            >>> company = extractor.extract_company_data(request)
            >>> print(company['company_name'])  # "Acme Corp"
        """
        company_data = {}
        
        # Extract company name
        company_data['company_name'] = getattr(request, 'company_name', None)
        
        # Extract number of employees
        number_of_employees = getattr(request, 'number_of_employees', None)
        if number_of_employees is None:
            number_of_employees = getattr(request, 'employee_count', None)
        company_data['number_of_employees'] = number_of_employees
        
        # Extract industry
        industry = None
        if hasattr(request, 'industry') and request.industry:
            if hasattr(request.industry, 'value'):
                industry = request.industry.value
            else:
                industry = str(request.industry)
        company_data['industry'] = industry
        
        self.logger.debug(
            "Company data extracted",
            extra={
                'company_name': company_data['company_name'],
                'has_employees': number_of_employees is not None,
                'has_industry': industry is not None
            }
        )
        
        return company_data
    
    def extract_historical_data(self, request: ValuationRequestProtocol) -> Dict[str, Any]:
        """
        Extract historical data information from request.
        
        WHAT: Gets count of historical years and data quality info
        WHY: Historical data affects confidence and template rendering
        HOW: Counts historical_years_data list
        
        Args:
            request: ValuationRequest
        
        Returns:
            Dict with historical data info:
            - years_of_data: Number of historical years
            - historical_years_data: Raw historical data list
        
        Example:
            >>> extractor = RequestDataExtractor()
            >>> historical = extractor.extract_historical_data(request)
            >>> print(historical['years_of_data'])  # 3
        """
        historical_data = {}
        
        # Extract historical years count
        historical_years_data = getattr(request, 'historical_years_data', [])
        years_of_data = len(historical_years_data) if historical_years_data else 0
        
        historical_data['years_of_data'] = years_of_data
        historical_data['historical_years_data'] = historical_years_data
        
        self.logger.debug(
            "Historical data extracted",
            extra={'years_of_data': years_of_data}
        )
        
        return historical_data
    
    def extract_business_context(self, request: ValuationRequestProtocol) -> Dict[str, Any]:
        """
        Extract business context (business type, location) from request.
        
        WHAT: Gets business type, business type ID, country code
        WHY: Business context needed for enrichment and characteristics
        HOW: Extracts from request attributes
        
        Args:
            request: ValuationRequest
        
        Returns:
            Dict with business context:
            - business_type: Business type display name
            - business_type_id: Business type identifier
            - country_code: Country code
        
        Example:
            >>> extractor = RequestDataExtractor()
            >>> context = extractor.extract_business_context(request)
            >>> print(context['business_type_id'])  # "restaurant"
        """
        business_context = {}
        
        # Extract business type and ID
        business_context['business_type'] = getattr(request, 'business_type', None)
        business_context['business_type_id'] = resolve_business_type_id(
            business_context=getattr(request, 'business_context', None),
            business_type_id=getattr(request, 'business_type_id', None),
        )
        
        # Extract country code
        business_context['country_code'] = getattr(request, 'country_code', None)
        
        self.logger.debug(
            "Business context extracted",
            extra={
                'business_type_id': business_context['business_type_id'],
                'country_code': business_context['country_code']
            }
        )
        
        return business_context
    
    def extract_all_request_data(self, request: ValuationRequestProtocol) -> Dict[str, Any]:
        """
        Extract all request data in one call.
        
        WHAT: Combines all extraction methods
        WHY: Convenience method for full extraction
        HOW: Calls all extraction methods and merges results
        
        Args:
            request: ValuationRequest
        
        Returns:
            Dict with all extracted data (financial, company, historical, business context)
        
        Example:
            >>> extractor = RequestDataExtractor()
            >>> all_data = extractor.extract_all_request_data(request)
            >>> print(all_data.keys())
            # dict_keys(['revenue', 'ebitda', 'step_1_inputs', 'company_name', 
            #            'number_of_employees', 'industry', 'years_of_data', ...])
        """
        all_data = {}
        
        # Extract all data types
        all_data.update(self.extract_financial_data(request))
        all_data.update(self.extract_company_data(request))
        all_data.update(self.extract_historical_data(request))
        all_data.update(self.extract_business_context(request))
        
        self.logger.info(
            "All request data extracted",
            extra={
                'extracted_fields': len(all_data),
                'has_revenue': all_data.get('revenue') is not None,
                'has_company_name': all_data.get('company_name') is not None,
                'years_of_data': all_data.get('years_of_data', 0)
            }
        )
        
        return all_data
