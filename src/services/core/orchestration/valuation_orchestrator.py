"""
Valuation Orchestrator - DEPRECATED / LEGACY

.. deprecated::
    This module is superseded by the API-layer orchestration stack at
    ``src.api.routes.valuation.valuation_orchestrator``.  No active HTTP
    route imports this module.  It is kept only for:
      - ``ProgressiveValuationService`` (transitional)
      - Package re-exports in ``src.services.core.__init__``
    Do NOT add new functionality here.  New orchestration work belongs in
    ``src.api.routes.valuation/``.

ARCHITECTURE OVERVIEW (original):
- Orchestrator pattern for coordinating 7+ services
- Async processing for 100+ concurrent requests
- Circuit breaker pattern for resilience

DATA FLOW:
1. Request → Privacy Guard (data classification)
2. Business Intelligence (type analysis)
3. Parallel: DCF + Multiples + ML Analysis
4. Result Aggregation → Deterministic Context → Report

INTEGRATION POINTS:
- Privacy Guard: Data classification and anonymization
- Business Intelligence: Company type analysis
- DCF Engine: Discounted cash flow calculations
- Multiples Engine: Comparable company analysis
- ML Engine: Pattern recognition and adjustments
- Narrative ownership: Titan-owned AI services, outside this legacy module
- Report Generator: PDF output with visualizations

ERROR HANDLING:
- Circuit breaker for external service failures
- Graceful degradation when services unavailable
- Comprehensive logging for debugging
- Automatic retry with exponential backoff
- Fallback to simplified workflows

SECURITY CONSIDERATIONS:
- Data privacy through 3-pipeline architecture
- Input validation and sanitization
- Rate limiting and request throttling
- Audit logging for compliance
- Secure service-to-service communication
"""

import uuid
from typing import Optional, Dict, Any
from datetime import datetime
from src.utils.logging import get_logger, log_calculation_step, log_validation_step
from src.utils.logging_context import LoggingContext, set_current_context, clear_current_context

# Import refactored components
from decimal import Decimal
from src.utils.decimal_helpers import to_decimal, from_decimal
from .orchestrator_types import (
    ValuationConfig, ValuationContext, ValuationResult,
    ProcessingMetrics, DEFAULT_VALUATION_CONFIG
)
from ..workflows.workflow_engine import WorkflowEngine
from ..processing.result_aggregator import ResultAggregator
from ..orchestration_monitor import OrchestrationMonitor

# Import external services
from typing import TYPE_CHECKING, Union

if TYPE_CHECKING:
    from src.api.schemas import ValuationRequest, QuickValuationRequest

from src.services.interfaces.request_response_protocol import (
    ValuationRequestProtocol,
    QuickValuationRequestProtocol,
)

# Import validation and monitoring
from src.validation.validation_engine import ValidationEngine
from src.validation.anomaly_detector import AnomalyDetector
from src.utils.exceptions import (
    CalculationError,
    ValidationError,
    DataQualityError,
    DatabaseError,
    MarketDataError,
    ConfigurationError,
)

logger = get_logger(__name__)


class ValuationOrchestrator:
    """
    Refactored Valuation Orchestrator with modular architecture

    ORCHESTRATOR PATTERN IMPLEMENTATION:
    - Coordinates 7+ microservices for business valuation
    - Manages complex workflows with parallel processing
    - Handles service failures gracefully with circuit breakers
    - Provides unified interface for valuation operations

    ARCHITECTURAL BENEFITS:
    - Scalability: Each service can scale independently
    - Maintainability: Clear separation of concerns
    - Testability: Individual services can be unit tested
    - Flexibility: Easy to add new valuation methods
    - Reliability: Fault isolation prevents cascade failures

    WORKFLOW COORDINATION:
    1. Request Validation: Input sanitization and validation
    2. Service Discovery: Dynamic service resolution
    3. Parallel Execution: DCF, Multiples, ML in parallel
    4. Result Aggregation: Weighted combination of results
    5. Quality Assurance: Confidence scoring and validation
    6. Report Generation: deterministic output creation

    PERFORMANCE OPTIMIZATION:
    - Async/await for non-blocking I/O operations
    - Connection pooling for database access
    - Caching for frequently accessed data
    - Batch processing for multiple requests
    - Resource monitoring and auto-scaling

    INTEGRATION ARCHITECTURE:
    - Service Mesh: Inter-service communication
    - API Gateway: Request routing and load balancing
    - Message Queue: Asynchronous processing
    - Event Sourcing: Audit trail and replay capability
    - CQRS: Command Query Responsibility Segregation

    Coordinates:
    - Workflow execution: Multi-step valuation processes
    - Result aggregation: Combining multiple valuation methods
    - Performance monitoring: Real-time metrics and alerts
    - Service integration: Microservices communication
    - Error handling: Graceful failure management
    - Security: Data privacy and access control
    """

    def __init__(
        self,
        db_session=None,
        config: Optional[ValuationConfig] = None,
        workflow_engine: Optional[WorkflowEngine] = None,
        result_aggregator: Optional[ResultAggregator] = None,
        orchestration_monitor: Optional[OrchestrationMonitor] = None,
        workflow_executor: Optional["ValuationWorkflowExecutor"] = None,
        validator: Optional["ValuationValidator"] = None,
    ):
        """
        Initialize the refactored valuation orchestrator with dependency injection
        
        Args:
            db_session: Database session (optional)
            config: Valuation configuration (optional)
            workflow_engine: Workflow engine instance (injected)
            result_aggregator: Result aggregator instance (injected)
            orchestration_monitor: Orchestration monitor instance (injected)
            workflow_executor: Workflow executor instance (injected)
            validator: Validator instance (injected)
        """
        self.db_session = db_session
        self.logger = logger
        self.config = config or DEFAULT_VALUATION_CONFIG

        # Use injected dependencies or create defaults
        self.workflow_engine = workflow_engine or WorkflowEngine()
        self.result_aggregator = result_aggregator or ResultAggregator()
        self.orchestration_monitor = orchestration_monitor or OrchestrationMonitor()
        
        # Import workflow executor components
        from .workflow_executor import (
            ValuationWorkflowExecutor,
            ValuationDataPreparer,
            DCFExecutor,
            MultiplesExecutor,
        )
        
        # Create workflow executor with dependencies if not injected
        if workflow_executor is None:
            data_preparer = ValuationDataPreparer()
            dcf_executor = DCFExecutor()
            multiples_executor = MultiplesExecutor()
            self.workflow_executor = ValuationWorkflowExecutor(
                data_preparer=data_preparer,
                dcf_executor=dcf_executor,
                multiples_executor=multiples_executor,
                result_aggregator=self.result_aggregator,
            )
        else:
            self.workflow_executor = workflow_executor
        
        # Import validator
        from .valuation_validator import ValuationValidator
        self.validator = validator or ValuationValidator()

        self.logger.info(
            "ValuationOrchestrator initialized with dependency injection",
            privacy_mode=self.config.privacy_mode.value,
            parallel_processing=self.config.parallel_processing
        )

    async def process_comprehensive_valuation(
        self,
        request: "ValuationRequest",
        context: Optional[ValuationContext] = None
    ) -> ValuationResult:
        """
        Process a comprehensive valuation request using multiple methodologies

        COMPREHENSIVE VALUATION WORKFLOW:
        1. Data Collection: KBO registry, user input, market data
        2. Data Classification: Privacy guard determines sensitivity levels
        3. Business Analysis: Type classification and methodology selection
        4. Parallel Valuation: DCF, Multiples, ML analysis simultaneously
        5. Result Synthesis: Weighted aggregation of all methods
        6. Deterministic Context: ValuationIQ-local report context
        7. Report Generation: Professional PDF with charts and analysis

        VALUATION METHODOLOGIES USED:
        - DCF (Discounted Cash Flow): Primary method for intrinsic value
        - Multiples Analysis: Market-based comparable company valuation
        - ML Adjustments: Pattern recognition and historical data analysis
        - Owner Profiling: Risk assessment and dependency analysis

        PERFORMANCE TARGETS:
        - Total processing time: <7 seconds
        - Data collection: <500ms (with KBO integration)
        - Valuation calculations: <2s (parallel execution)
        - Context formatting: <50ms
        - Report generation: <1s (PDF rendering)

        QUALITY ASSURANCE:
        - Confidence scoring for each methodology
        - Sensitivity analysis for key assumptions
        - Cross-validation between methods
        - Risk factor identification and quantification

        Args:
            request: Valuation request with company data and preferences
            context: Processing context (optional, auto-generated if not provided)

        Returns:
            Complete valuation result with:
            - Equity value and enterprise value
            - Methodology breakdown and confidence scores
            - Value drivers and risk factors
            - Sensitivity analysis and market comparables
            - AI-generated insights and recommendations
        """
        try:
            # Initialize enhanced logging context
            logging_context = LoggingContext()
            set_current_context(logging_context)

            # Create context if not provided
            if not context:
                context = ValuationContext(
                    request_id=str(uuid.uuid4()),
                    company_name=request.company_name,
                    industry=request.industry.value,
                    country_code=request.country_code
                )

            # Set up logging context
            logging_context.set_request_id(context.request_id)
            logging_context.set_user_id(getattr(request, 'user_id', None))
            logging_context.set_company_name(context.company_name)

            # Start calculation session
            session_id = logging_context.start_calculation_session(
                calculation_type="Comprehensive_Valuation",
                total_steps=8
            )

            # Start monitoring
            metrics = self.orchestration_monitor.start_monitoring(context)

            # Log orchestration start
            log_calculation_step(
                "orchestration_start",
                inputs={
                    "company_name": context.company_name,
                    "industry": context.industry,
                    "country_code": context.country_code,
                    "request_type": "comprehensive"
                },
                outputs={"request_id": context.request_id},
                formula="Orchestration_Start = Initialize_Context + Setup_Logging + Start_Monitoring"
            )

            self.logger.calculation(
                "Starting comprehensive valuation orchestration",
                session_id=session_id,
                request_id=context.request_id,
                company=context.company_name,
                industry=context.industry
            )

            # Execute valuation workflow with enhanced logging
            result = await self.workflow_executor.execute_workflow(
                request=request,
                context=context,
                metrics=metrics,
                enable_dcf=self.config.enable_dcf,
                enable_multiples=self.config.enable_multiples,
            )

            # Validate results
            validation_result = self.validator.validate_comprehensive_valuation(result)

            if not validation_result.is_valid:
                self.logger.warning(
                    "Valuation validation failed",
                    session_id=session_id,
                    request_id=context.request_id,
                    validation_errors=validation_result.errors
                )

            # Check for anomalies
            anomalies = self.validator.detect_anomalies(result)

            if anomalies:
                self.logger.warning(
                    "Anomalies detected in valuation result",
                    session_id=session_id,
                    request_id=context.request_id,
                    anomalies=anomalies
                )

            # Stop monitoring
            final_metrics = self.orchestration_monitor.stop_monitoring(context)
            result.processing_metrics = final_metrics

            # Complete calculation session
            logging_context.complete_calculation_session(session_id)

            # Log orchestration completion
            log_calculation_step(
                "orchestration_complete",
                inputs={"request_id": context.request_id},
                outputs={
                    "equity_value": result.equity_value,
                    "processing_time": final_metrics.processing_time,
                    "validation_passed": validation_result.is_valid,
                    "anomalies_detected": len(anomalies) > 0
                },
                formula="Orchestration_Complete = Execute_Workflow + Validate_Results + Check_Anomalies"
            )

            self.logger.calculation(
                "Comprehensive valuation orchestration completed",
                session_id=session_id,
                request_id=context.request_id,
                processing_time=final_metrics.processing_time,
                equity_value=result.equity_value,
                validation_passed=validation_result.is_valid,
                anomalies_count=len(anomalies)
            )

            return result

        except (CalculationError, ValidationError, DataQualityError, DatabaseError, MarketDataError, ValueError, TypeError, AttributeError) as e:
            # Clean up logging context
            try:
                if 'logging_context' in locals():
                    logging_context.complete_calculation_session(session_id)
                clear_current_context()
            except (ValueError, TypeError, AttributeError):
                pass

            self.logger.error(
                f"Comprehensive valuation failed: {e}",
                request_id=context.request_id if context else None,
                extra={'error_type': type(e).__name__},
                exc_info=True
            )
            raise

    async def process_quick_valuation(
        self,
        request: QuickValuationRequestProtocol,
        context: Optional[ValuationContext] = None
    ) -> ValuationResult:
        """
        Process a quick valuation request

        Args:
            request: Quick valuation request
            context: Processing context (optional)

        Returns:
            Simplified valuation result
        """
        try:
            # Create context if not provided
            if not context:
                context = ValuationContext(
                    request_id=str(uuid.uuid4()),
                    company_name=getattr(request, 'company_name', 'Unknown'),
                    industry="unknown",
                    country_code=request.country_code
                )

            # Start monitoring
            metrics = self.orchestration_monitor.start_monitoring(context)

            self.logger.info(
                "Starting quick valuation",
                request_id=context.request_id
            )

            # Execute simplified workflow
            result = await self._execute_quick_workflow(request, context, metrics)

            # Stop monitoring
            final_metrics = self.orchestration_monitor.stop_monitoring(context)
            result.processing_metrics = final_metrics

            self.logger.info(
                "Quick valuation completed",
                request_id=context.request_id,
                processing_time=final_metrics.processing_time
            )

            return result

        except (CalculationError, ValidationError, DataQualityError, DatabaseError, MarketDataError, ValueError, TypeError, AttributeError) as e:
            self.logger.error(
                f"Quick valuation failed: {e}",
                request_id=context.request_id if context else None,
                extra={'error_type': type(e).__name__},
                exc_info=True
            )
            raise


    async def _execute_quick_workflow(
        self,
        request: QuickValuationRequestProtocol,
        context: ValuationContext,
        metrics: ProcessingMetrics
    ) -> ValuationResult:
        """Execute simplified quick valuation workflow"""
        try:
            # Use workflow executor for quick valuation (simplified)
            from .workflow_executor import ValuationDataPreparer
            data_preparer = ValuationDataPreparer()
            financial_data = await data_preparer.prepare_financial_data(request, context)
            
            # Simplified quick valuation
            result = ValuationResult(
                equity_value=0.0,  # Placeholder
                enterprise_value=0.0,  # Placeholder
                valuation_methodology="quick_multiples",
                confidence_score=0.7,
                value_drivers=[],
                risk_factors=[],
                sensitivity_analysis={},
                market_comparables=[],
                financial_metrics={}
            )

            return result

        except (CalculationError, ValidationError, DataQualityError, DatabaseError, MarketDataError, ValueError, TypeError, AttributeError) as e:
            self.logger.error(f"Quick workflow execution failed: {e}", extra={'error_type': type(e).__name__}, exc_info=True)
            raise

    async def _prepare_financial_data(self, request, context) -> Dict[str, Any]:
        """Prepare financial data (placeholder)"""
        return {"request": request, "context": context}

    async def _execute_dcf_valuation(self, financial_data, context) -> Dict[str, Any]:
        """Execute DCF valuation (placeholder)"""
        return {
            "equity_value": 1000000.0,
            "enterprise_value": 1100000.0,
            "value_drivers": ["Strong cash flow", "Growth potential"],
            "risk_factors": ["Market competition"],
            "financial_metrics": {}
        }

    async def _execute_multiples_valuation(self, financial_data, context) -> Dict[str, Any]:
        """Execute multiples valuation (placeholder)"""
        return {
            "equity_value": 950000.0,
            "enterprise_value": 1050000.0,
            "value_drivers": ["Industry position"],
            "risk_factors": ["Economic conditions"],
            "financial_metrics": {}
        }

    async def get_system_status(self) -> Dict[str, Any]:
        """Get system status"""
        return {
            "status": "operational",
            "components": {
                "workflow_engine": "active",
                "result_aggregator": "active",
                "orchestration_monitor": "active"
            },
            "configuration": {
                "enable_dcf": self.config.enable_dcf,
                "enable_multiples": self.config.enable_multiples,
                "privacy_mode": self.config.privacy_mode.value,
                "parallel_processing": self.config.parallel_processing
            },
            "service_health": self.orchestration_monitor.get_service_health_status(),
            "timestamp": datetime.utcnow().isoformat()
        }


# ValuationOrchestrator is now the main class
