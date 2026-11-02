"""
Basic Data Builder

Extracts basic response data into template data dictionary.

SOURCE TRACING:
- Extracts business_type_benchmarks from step results for template rendering
- Provides data_source and academic_source tracing to templates

ALIGNMENT WITH UPSWITCH PRIMITIVES:
- Primitive 2: Algorithmic Defensibility - every calculation traceable
- Primitive 4: Shared Reality Layer - same data visible to all parties
"""

from typing import Dict, Any, TYPE_CHECKING, Union, Optional

if TYPE_CHECKING:
    from src.api.schemas import ValuationResponse

from src.services.interfaces.request_response_protocol import ValuationResponseProtocol
from decimal import Decimal
from src.services.infrastructure.report_confidence import confidence_score_percent
from src.utils.decimal_helpers import to_decimal, from_decimal
from pydantic import BaseModel


class BasicDataBuilder:
    """
    Extracts basic response data into template data dictionary.
    """

    _REQUIRED_BENCHMARK_PROVENANCE_FIELDS = (
        "benchmark_id",
        "dataset_version_id",
        "country_code",
        "region_key",
        "tier",
        "sample_size",
        "confidence_band",
        "source_mix",
        "evidence_summary",
        "published_at",
        "methodology_version",
        "scope_stage",
    )

    @staticmethod
    def _has_value(value: Any) -> bool:
        if value is None:
            return False
        if isinstance(value, str):
            return bool(value.strip())
        if isinstance(value, (dict, list, tuple, set)):
            return len(value) > 0
        return True

    @classmethod
    def _has_complete_benchmark_contract(cls, contract: Any) -> bool:
        if not isinstance(contract, dict):
            return False
        status = contract.get("status")
        if status is not None and str(status).strip().lower() != "resolved":
            return False
        if "walk_step" not in contract:
            return False
        for field in cls._REQUIRED_BENCHMARK_PROVENANCE_FIELDS:
            if not cls._has_value(contract.get(field)):
                return False
        try:
            return Decimal(str(contract.get("sample_size"))) > 0
        except Exception:
            return False
    
    @staticmethod
    def _convert_financial_metrics_to_dict(financial_metrics: Any) -> Union[Dict[str, Any], None]:
        """
        Convert financial_metrics from Pydantic model to dictionary.
        
        BANK-GRADE: Ensures financial_metrics is always a dict for template rendering.
        Templates use .get() which requires dict, not Pydantic model.
        
        Args:
            financial_metrics: Pydantic model, dict, or None
            
        Returns:
            Dictionary representation or None
        """
        if financial_metrics is None:
            return None
        
        # Already a dict - return as-is
        if isinstance(financial_metrics, dict):
            return financial_metrics
        
        # Pydantic model - convert to dict
        if isinstance(financial_metrics, BaseModel):
            try:
                # Try Pydantic v2 model_dump() first
                if hasattr(financial_metrics, 'model_dump'):
                    return financial_metrics.model_dump()
                # Fallback to Pydantic v1 dict()
                elif hasattr(financial_metrics, 'dict'):
                    return financial_metrics.dict()
                else:
                    # Last resort: try to convert to dict
                    return dict(financial_metrics)
            except Exception as e:
                # If conversion fails, log and return None
                # This prevents template errors but logs the issue
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(
                    f"Failed to convert financial_metrics to dict: {e}",
                    extra={"financial_metrics_type": type(financial_metrics).__name__}
                )
                return None
        
        # Try to convert other types to dict
        try:
            return dict(financial_metrics)
        except (TypeError, ValueError):
            return None
    
    @staticmethod
    def extract_basic_response_data(response: ValuationResponseProtocol) -> Dict[str, Any]:
        """
        Extract basic response data into template data dictionary.
        
        Args:
            response: ValuationResponse to extract data from
            
        Returns:
            Dictionary with basic response data
        """
        # Extract financial metrics for easier template access
        financial_metrics_dict = BasicDataBuilder._convert_financial_metrics_to_dict(response.financial_metrics)
        ebitda_margin = financial_metrics_dict.get('ebitda_margin') if financial_metrics_dict else None
        revenue_growth = financial_metrics_dict.get('revenue_growth') if financial_metrics_dict else None
        financial_health_score = financial_metrics_dict.get('financial_health_score') if financial_metrics_dict else None
        
        # Extract core metrics for direct template access
        ebitda = None
        revenue = None
        normalized_ebitda = None
        number_of_employees = None
        if response.current_year_data:
            ebitda = getattr(response.current_year_data, 'ebitda', None)
            revenue = getattr(response.current_year_data, 'revenue', None)
        
        # Try to find number_of_employees from request or response
        if hasattr(response, 'number_of_employees'):
            number_of_employees = response.number_of_employees
        
        # Try to find normalized_ebitda from detailed results if available
        reported_ebitda = None
        ebitda_adjustments = []
        if hasattr(response, 'detailed_results') and response.detailed_results:
            detailed = response.detailed_results
            if isinstance(detailed, dict):
                # Check detailed_results.ebitda_normalization.normalized_ebitda
                norm_res = detailed.get('ebitda_normalization')
                if norm_res and isinstance(norm_res, dict):
                    normalized_ebitda = norm_res.get('normalized_ebitda')
                    reported_ebitda = norm_res.get('reported_ebitda')
                    ebitda_adjustments = norm_res.get('ebitda_adjustments', [])
                
                # Check detailed_results.step_results[2.5].result.normalized_ebitda
                if normalized_ebitda is None:
                    step_results = detailed.get('step_results', {})
                    step_2_5 = step_results.get('2.5') or step_results.get(2.5)
                    if step_2_5:
                        res = getattr(step_2_5, 'result', None) or (step_2_5.get('result') if isinstance(step_2_5, dict) else None)
                        if res and isinstance(res, dict):
                            normalized_ebitda = res.get('normalized_ebitda')
                            reported_ebitda = res.get('reported_ebitda')
                            ebitda_adjustments = res.get('ebitda_adjustments', [])
        
        return {
            'company_name': response.company_name,
            'valuation_date': response.valuation_date,
            'valuation_id': response.valuation_id,
            'equity_value_low': response.equity_value_low,
            'equity_value_mid': response.equity_value_mid,
            'equity_value_high': response.equity_value_high,
            'range_methodology': response.range_methodology,
            'recommended_asking_price': getattr(response, 'recommended_asking_price', None),
            'recommended_asking_multiple': getattr(response, 'recommended_asking_multiple', None),
            'dcf_weight': response.dcf_weight if response.dcf_weight is not None else 0.0,
            'multiples_weight': response.multiples_weight if response.multiples_weight is not None else 0.0,
            'confidence_score': confidence_score_percent(response.confidence_score),
            'overall_confidence': response.overall_confidence,
            'valuation_summary': response.valuation_summary,
            'key_value_drivers': response.key_value_drivers,
            'risk_factors': response.risk_factors,
            'methodology_notes': response.methodology_notes,
            'dcf_valuation': response.dcf_valuation,
            'financial_metrics': financial_metrics_dict,
            'dcf_exclusion_reason': response.dcf_exclusion_reason,
            'methodology_downgrade_reason': response.methodology_downgrade_reason,
            'owner_dependency_adjustment': response.owner_dependency_adjustment,
            'multiple_pipeline': None,  # Will be converted to dict below
            'current_year_data': response.current_year_data,
            
            # 🔧 FIX: Add template-friendly aliases for info tab
            'final_equity_value': response.equity_value_mid,  # Template expects this name
            'valuation_range_low': response.equity_value_low,  # Template expects this name
            'valuation_range_high': response.equity_value_high,  # Template expects this name
            'value_drivers': response.key_value_drivers,  # Template expects this name
            'ebitda': ebitda,  # Template expects this name
            'reported_ebitda': reported_ebitda,  # NEW: For normalization bridge
            'ebitda_adjustments': ebitda_adjustments,  # NEW: For normalization bridge
            'revenue': revenue,  # Template expects this name
            'normalized_ebitda': normalized_ebitda,  # Template expects this name
            'number_of_employees': number_of_employees,  # Template expects this name
            
            # 🔧 FIX: Extract metrics for direct template access (no need to navigate nested objects)
            'ebitda_margin': ebitda_margin,  # From financial_metrics
            'revenue_growth': revenue_growth,  # From financial_metrics
            'financial_health_score': financial_health_score,  # From financial_metrics
        }
    
    @staticmethod
    def extract_business_type_benchmarks(response: ValuationResponseProtocol) -> Dict[str, Any]:
        """
        Extract business_type_benchmarks from Step 2 results for template rendering.
        
        SOURCE TRACING: Provides industry benchmarks with data source metadata
        
        Args:
            response: ValuationResponse containing detailed_results
            
        Returns:
            Dictionary with business_type_benchmarks data:
            - ev_ebitda_median: Median EV/EBITDA multiple for industry
            - ev_ebitda_p25: 25th percentile
            - ev_ebitda_p75: 75th percentile
            - ev_revenue_median: Median EV/Revenue multiple
            - data_source: Source of multiples (e.g., "TITAN_BUSINESS_TYPES_DB")
            - data_source_name: Human-readable source name
            - source_confidence: Confidence level (HIGH, MEDIUM, LOW)
            - academic_sources: List of academic citations backing the multiples
            - sme_sample_size: Number of transactions in sample (if available)
            - last_updated: Timestamp of data update
        """
        benchmarks = {}
        
        if not hasattr(response, 'detailed_results') or not response.detailed_results:
            return benchmarks
        
        step_results = response.detailed_results.get('step_results', {})
        
        # Extract from Step 2 (Industry Benchmarking)
        step_2 = step_results.get(2)
        if step_2:
            result = getattr(step_2, 'result', None) or (step_2.get('result') if isinstance(step_2, dict) else None)
            metadata = getattr(step_2, 'metadata', None) or (step_2.get('metadata') if isinstance(step_2, dict) else None)
            
            if isinstance(result, dict):
                benchmark_contract = (
                    result.get('benchmark_contract')
                    or result.get('benchmark_provenance')
                    or (metadata.get('benchmark_contract') if isinstance(metadata, dict) else None)
                )
                if not BasicDataBuilder._has_complete_benchmark_contract(benchmark_contract):
                    return benchmarks

                # Extract multiples
                _eb_p50 = result.get('ev_ebitda_p50')
                benchmarks['ev_ebitda_median'] = _eb_p50 if _eb_p50 is not None else result.get('ev_ebitda_multiple')
                benchmarks['ev_ebitda_p25'] = result.get('ev_ebitda_p25')
                benchmarks['ev_ebitda_p75'] = result.get('ev_ebitda_p75')
                _er_p50 = result.get('ev_revenue_p50')
                benchmarks['ev_revenue_median'] = _er_p50 if _er_p50 is not None else result.get('ev_revenue_multiple')
                benchmarks['ev_revenue_p25'] = result.get('ev_revenue_p25')
                benchmarks['ev_revenue_p75'] = result.get('ev_revenue_p75')
                benchmarks['pe_ratio'] = result.get('pe_ratio')
                
                # Extract data source info
                benchmarks['data_source'] = result.get('data_source', 'unknown')
                benchmarks['data_source_display'] = result.get('data_source_display')
                benchmarks['data_source_academic_citations'] = result.get('data_source_academic_citations')
                benchmarks['benchmark_contract'] = benchmark_contract
                for key in (
                    'benchmark_id',
                    'dataset_version_id',
                    'country_code',
                    'region_key',
                    'tier',
                    'walk_step',
                    'sample_size',
                    'confidence_band',
                    'source_mix',
                    'evidence_summary',
                    'published_at',
                    'methodology_version',
                    'scope_stage',
                ):
                    benchmarks[key] = benchmark_contract.get(key)
                
                # Extract SME calibration data if available
                sme_calibration = result.get('sme_calibration', {})
                if isinstance(sme_calibration, dict):
                    benchmarks['sme_sample_size'] = sme_calibration.get('sample_size')
                    benchmarks['sme_calibration_factor'] = sme_calibration.get('calibration_factor')
            
            if isinstance(metadata, dict):
                # Extract source tracing from metadata
                benchmarks['data_source'] = metadata.get('data_source', benchmarks.get('data_source', 'unknown'))
                benchmarks['data_source_name'] = metadata.get('data_source_name')
                benchmarks['source_confidence'] = metadata.get('source_confidence', 'MEDIUM')
                benchmarks['academic_sources'] = metadata.get('academic_sources', [])
                benchmarks['primary_citation'] = metadata.get('primary_citation')
        
        return benchmarks
    
    @staticmethod
    def extract_step_source_metadata(response: ValuationResponseProtocol, step_number: float) -> Dict[str, Any]:
        """
        Extract source metadata from a specific step's metadata.
        
        Args:
            response: ValuationResponse containing detailed_results
            step_number: Step number to extract from (e.g., 2, 3, 2.7)
            
        Returns:
            Dictionary with source tracing data:
            - data_source: Source identifier
            - data_source_name: Human-readable name
            - source_confidence: Confidence level
            - academic_sources: List of academic citations
            - primary_citation: Primary academic reference
        """
        source_metadata = {}
        
        if not hasattr(response, 'detailed_results') or not response.detailed_results:
            return source_metadata
        
        step_results = response.detailed_results.get('step_results', {})
        step = step_results.get(step_number)
        
        if step:
            metadata = getattr(step, 'metadata', None) or (step.get('metadata') if isinstance(step, dict) else None)
            
            if isinstance(metadata, dict):
                source_metadata['data_source'] = metadata.get('data_source')
                source_metadata['data_source_name'] = metadata.get('data_source_name')
                source_metadata['source_confidence'] = metadata.get('source_confidence')
                source_metadata['academic_sources'] = metadata.get('academic_sources', [])
                source_metadata['primary_citation'] = metadata.get('primary_citation')
        
        return source_metadata
