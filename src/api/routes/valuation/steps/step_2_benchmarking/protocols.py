"""
Step 2 Protocols (Interfaces)

Protocol definitions for Step 2 components following dependency inversion principle.
This allows for better testability and loose coupling.
"""

from typing import Any, Dict, Optional, Protocol

from src.api.routes.valuation.triage.business_type_triage import BusinessTypeCategory


class IMultiplesCollector(Protocol):
    """Protocol for multiples collection."""
    
    async def select_multiples(
        self,
        request: Any,
        ebitda: Optional[Any],
        ebitda_margin: Any,
        business_category: Optional[BusinessTypeCategory],
        comparables_data: Dict[str, Any],
        correlation_id: Optional[str] = None,
        market_data_collector: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """
        Select multiples using priority cascade.
        
        Returns:
            Dictionary with multiples data including:
            - ev_ebitda: EV/EBITDA multiple
            - ev_revenue: EV/Revenue multiple
            - pe_ratio: PE ratio
            - data_source: Source of the multiples
            - data_source_details: Additional source information
        """
        ...


class IErrorHandler(Protocol):
    """Protocol for error handling."""
    
    def handle_execution_exception(
        self,
        exception: Exception,
        request: Any,
        result_dict: Optional[Dict[str, Any]] = None,
        multiples_data_backup: Optional[Dict[str, Any]] = None,
        correlation_id: Optional[str] = None,
    ) -> Any:
        """
        Handle exceptions during execution.
        
        Returns:
            StepOutput with recovered or fallback data
        """
        ...


class IResultBuilder(Protocol):
    """Protocol for result building."""
    
    def build_result_dict(
        self,
        request: Any,
        primary_method: str,
        multiples_data: Dict[str, Any],
        comparables_data: Dict[str, Any],
        eligibility_result: Any,
        business_category: Optional[BusinessTypeCategory],
        business_type_id: Optional[int],
        data_quality_warnings: list,
        sme_calibration_data: Dict[str, Any],
        correlation_id: Optional[str],
    ) -> Dict[str, Any]:
        """
        Build comprehensive result dictionary.
        
        Returns:
            Complete result dictionary with all Step 2 outputs
        """
        ...


class IRecoveryService(Protocol):
    """Protocol for recovery service."""
    
    def recover_result_dict(
        self,
        backup: Optional[Dict[str, Any]],
        error: Exception,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Recover result dictionary from backup or defaults.
        
        Returns:
            Recovered result dictionary with recovery_applied=True
        """
        ...

