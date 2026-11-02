"""
Valuation Workflow Executor — DEPRECATED / LEGACY

.. deprecated::
    Production workflow is driven by
    ``ComprehensiveValuationOrchestrator`` in
    ``src.api.routes.valuation.orchestration.executors``.
    This module belongs to the legacy ``services/core/orchestration/``
    stack.
"""

from typing import Dict, Any, Optional
from datetime import datetime
from src.utils.logging import get_logger
from .orchestrator_types import ValuationContext, ProcessingMetrics, ValuationResult
from src.services.interfaces.request_response_protocol import ValuationRequestProtocol
from src.utils.exceptions import (
    CalculationError,
    ValidationError,
    DataQualityError,
    DatabaseError,
    MarketDataError,
)

logger = get_logger(__name__)


class ValuationWorkflowExecutor:
    """
    Executes valuation workflows with parallel processing.
    
    Single Responsibility: Workflow execution coordination only.
    """

    def __init__(
        self,
        data_preparer: "ValuationDataPreparer",
        dcf_executor: "DCFExecutor",
        multiples_executor: "MultiplesExecutor",
        result_aggregator: "ResultAggregator",
    ):
        """
        Initialize workflow executor with dependencies
        
        Args:
            data_preparer: Service for preparing financial data
            dcf_executor: Service for executing DCF valuations
            multiples_executor: Service for executing multiples valuations
            result_aggregator: Service for aggregating results
        """
        self.data_preparer = data_preparer
        self.dcf_executor = dcf_executor
        self.multiples_executor = multiples_executor
        self.result_aggregator = result_aggregator
        self.logger = logger

    async def execute_workflow(
        self,
        request: ValuationRequestProtocol,
        context: ValuationContext,
        metrics: ProcessingMetrics,
        enable_dcf: bool = True,
        enable_multiples: bool = True,
    ) -> ValuationResult:
        """
        Execute the main valuation workflow with parallel processing
        
        Args:
            request: Original valuation request
            context: Processing context with metadata
            metrics: Performance tracking object
            enable_dcf: Whether to execute DCF valuation
            enable_multiples: Whether to execute multiples valuation
            
        Returns:
            Aggregated valuation result with confidence scores
        """
        try:
            # Step 1: Prepare data
            data_start = datetime.utcnow()
            financial_data = await self.data_preparer.prepare_financial_data(request, context)
            metrics.data_preparation_time = (datetime.utcnow() - data_start).total_seconds()

            # Step 2: Execute valuations in parallel
            valuation_start = datetime.utcnow()
            dcf_result = None
            multiples_result = None

            if enable_dcf:
                dcf_result = await self.dcf_executor.execute(financial_data, context)

            if enable_multiples:
                multiples_result = await self.multiples_executor.execute(financial_data, context)

            metrics.valuation_calculation_time = (datetime.utcnow() - valuation_start).total_seconds()

            # Step 3: Aggregate results
            synthesis_start = datetime.utcnow()
            result = self.result_aggregator.aggregate_valuations(
                dcf_result, multiples_result, context
            )
            metrics.synthesis_time = (datetime.utcnow() - synthesis_start).total_seconds()

            return result

        except (CalculationError, ValidationError, DataQualityError, DatabaseError, MarketDataError) as e:
            self.logger.error(
                f"Valuation workflow execution failed: {e}",
                extra={'error_type': type(e).__name__},
                exc_info=True
            )
            raise


class ValuationDataPreparer:
    """
    Prepares financial data for valuation calculations.
    
    Single Responsibility: Data preparation only.
    """

    def __init__(self):
        self.logger = logger

    async def prepare_financial_data(
        self,
        request: ValuationRequestProtocol,
        context: ValuationContext,
    ) -> Dict[str, Any]:
        """
        Prepare financial data from request
        
        Args:
            request: Valuation request
            context: Processing context
            
        Returns:
            Prepared financial data dictionary
        """
        # Extract financial data from request
        financial_data = {
            "revenue": getattr(request.current_year_data, "revenue", None) if hasattr(request, "current_year_data") else None,
            "ebitda": getattr(request.current_year_data, "ebitda", None) if hasattr(request, "current_year_data") else None,
            "industry": getattr(request, "industry", None),
            "country_code": getattr(request, "country_code", None),
        }
        
        self.logger.debug(
            "Financial data prepared",
            extra={'request_id': context.request_id}
        )
        
        return financial_data


class DCFExecutor:
    """
    Executes DCF (Discounted Cash Flow) valuations.
    
    Single Responsibility: DCF calculation execution only.
    """

    def __init__(self):
        self.logger = logger

    async def execute(
        self,
        financial_data: Dict[str, Any],
        context: ValuationContext,
    ) -> Optional[Dict[str, Any]]:
        """
        Execute DCF valuation
        
        Args:
            financial_data: Prepared financial data
            context: Processing context
            
        Returns:
            DCF valuation result or None if calculation fails
        """
        # Placeholder - actual DCF execution would go here
        self.logger.debug(
            "DCF valuation executed",
            extra={'request_id': context.request_id}
        )
        return None


class MultiplesExecutor:
    """
    Executes multiples-based valuations.
    
    Single Responsibility: Multiples calculation execution only.
    """

    def __init__(self):
        self.logger = logger

    async def execute(
        self,
        financial_data: Dict[str, Any],
        context: ValuationContext,
    ) -> Optional[Dict[str, Any]]:
        """
        Execute multiples valuation
        
        Args:
            financial_data: Prepared financial data
            context: Processing context
            
        Returns:
            Multiples valuation result or None if calculation fails
        """
        # Placeholder - actual multiples execution would go here
        self.logger.debug(
            "Multiples valuation executed",
            extra={'request_id': context.request_id}
        )
        return None

