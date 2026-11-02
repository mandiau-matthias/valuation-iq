"""
Service Registry

Centralized service registration for the UpSwitch Valuation Engine.

This module provides a convenient way to register all services with the DI container.
"""

from typing import Optional

from src.utils.logging import get_logger

from .container import Container, ServiceLifetime, get_container

logger = get_logger(__name__)


def register_core_services(container: Optional[Container] = None) -> Container:
    """
    Register core valuation engine services with the DI container

    Args:
        container: Optional container instance (uses global if not provided)

    Returns:
        The container with registered services
    """
    if container is None:
        container = get_container()

    logger.info("Registering core services with DI container")

    # Register workflow and orchestration services
    try:
        from src.services.core.orchestration.orchestration_monitor import OrchestrationMonitor
        from src.services.core.processing.result_aggregator import ResultAggregator
        from src.services.core.workflows.workflow_engine import WorkflowEngine

        container.register_singleton(WorkflowEngine)
        container.register_singleton(ResultAggregator)
        container.register_singleton(OrchestrationMonitor)
        logger.debug("Registered workflow and orchestration services")
    except ImportError as e:
        logger.warning(f"Could not register workflow services: {e}")

    # Register validation services
    try:
        from src.validation.anomaly_detector import AnomalyDetector
        from src.validation.validation_engine import ValidationEngine

        container.register_singleton(ValidationEngine)
        container.register_singleton(AnomalyDetector)
        logger.debug("Registered validation services")
    except ImportError as e:
        logger.warning(f"Could not register validation services: {e}")

    # Register infrastructure services
    try:
        from src.services.infrastructure.html_report_service import HTMLReportService
        from src.services.transparency.transparency_service import TransparencyService

        container.register_singleton(HTMLReportService)
        container.register_singleton(TransparencyService)
        logger.debug("Registered infrastructure services")
    except ImportError as e:
        logger.warning(f"Could not register infrastructure services: {e}")

    logger.info("Core services registered successfully")
    return container


def register_valuation_services(container: Optional[Container] = None) -> Container:
    """
    Register valuation-specific services with the DI container

    Args:
        container: Optional container instance (uses global if not provided)

    Returns:
        The container with registered services
    """
    if container is None:
        container = get_container()

    logger.info("Registering valuation services with DI container")

    # Register valuation processors
    try:
        from src.services.core.orchestration.valuation_processor import ValuationProcessor

        container.register_singleton(ValuationProcessor)
        logger.debug("Registered ValuationProcessor")
    except ImportError as e:
        logger.warning(f"Could not register ValuationProcessor: {e}")

    # Register workflow executor components
    try:
        from src.services.core.orchestration.workflow_executor import (
            DCFExecutor,
            MultiplesExecutor,
            ValuationDataPreparer,
            ValuationWorkflowExecutor,
        )
        from src.services.core.processing.result_aggregator import ResultAggregator

        container.register_singleton(ValuationDataPreparer)
        container.register_singleton(DCFExecutor)
        container.register_singleton(MultiplesExecutor)

        # Register workflow executor with factory
        def create_workflow_executor():
            return ValuationWorkflowExecutor(
                data_preparer=container.resolve(ValuationDataPreparer),
                dcf_executor=container.resolve(DCFExecutor),
                multiples_executor=container.resolve(MultiplesExecutor),
                result_aggregator=container.resolve(ResultAggregator),
            )

        container.register_singleton(ValuationWorkflowExecutor, factory=create_workflow_executor)
        logger.debug("Registered workflow executor components")
    except ImportError as e:
        logger.warning(f"Could not register workflow executor: {e}")

    # Register validator
    try:
        from src.services.core.orchestration.valuation_validator import ValuationValidator

        container.register_singleton(ValuationValidator)
        logger.debug("Registered ValuationValidator")
    except ImportError as e:
        logger.warning(f"Could not register validator: {e}")

    # Register progressive valuation services
    try:
        from src.services.progressive.academic_tracker_manager import AcademicTrackerManager
        from src.services.progressive.coordinators import (
            HTMLGenerationCoordinator,
            MockCalculationCoordinator,
            SummaryGenerationCoordinator,
        )
        from src.services.progressive.data_transformer import ProgressiveDataTransformer
        from src.services.progressive.fallback_generator import FallbackValuationGenerator
        from src.services.progressive.phase_calculator import PhaseCalculator
        from src.services.progressive.phase_determiner import PhaseDeterminer

        container.register_singleton(ProgressiveDataTransformer)
        container.register_singleton(FallbackValuationGenerator)
        container.register_singleton(PhaseDeterminer)
        container.register_singleton(AcademicTrackerManager)
        container.register_singleton(HTMLGenerationCoordinator)
        container.register_singleton(MockCalculationCoordinator)
        container.register_singleton(SummaryGenerationCoordinator)

        # Register phase calculator with factory
        def create_phase_calculator():
            return PhaseCalculator(
                html_coordinator=container.resolve(HTMLGenerationCoordinator),
                mock_coordinator=container.resolve(MockCalculationCoordinator),
                summary_coordinator=container.resolve(SummaryGenerationCoordinator),
            )

        container.register_singleton(PhaseCalculator, factory=create_phase_calculator)
        logger.debug("Registered progressive valuation services")
    except ImportError as e:
        logger.warning(f"Could not register progressive services: {e}")

    # BRAIN & MUSCLE ARCHITECTURE:
    # Triage orchestration services have moved to Titan (The Brain)
    # ValuationIQ only provides GapAnalysisService for validation
    try:
        from src.services.triage import GapAnalysisService

        container.register_singleton(GapAnalysisService)
        logger.debug("Registered GapAnalysisService for triage validation")
    except ImportError as e:
        logger.warning(f"Could not register GapAnalysisService: {e}")

    # Register progressive section calculation services
    try:
        from src.services.progressive.business_type_info_extractor import BusinessTypeInfoExtractor
        from src.services.progressive.calculators.industry_helpers import IndustryHelpers

        container.register_singleton(BusinessTypeInfoExtractor)
        container.register_singleton(IndustryHelpers)
        logger.debug("Registered progressive section calculation services")
    except ImportError as e:
        logger.warning(f"Could not register progressive section services: {e}")

    logger.info("Valuation services registered successfully")
    return container
