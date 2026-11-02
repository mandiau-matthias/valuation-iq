"""
Step 2 Orchestrator - Refactored (Coordinator Pattern)

Orchestrates the main execution flow for Step 2 benchmarking.

Architecture:
- SMECalibrationCoordinator: SME calibration, margin premium, and growth risk adjustments
- ResultBuildingCoordinator: Result and metadata dictionary building
- DataQualityCoordinator: Data quality warnings, validation, and checksum generation
- fallback_services: optional-module fallback implementations
- methodology_eligibility: methodology decision boundary
- multiples_processing: calibration, validation, and checksum generation
- primary_method_selection: primary method selection with current-year override
"""

from decimal import Decimal
from typing import Any, Dict, Optional, Tuple

from src.api.routes.valuation.triage.business_type_triage import BusinessTypeCategory
from src.domain.methodology_eligibility_decider import MethodologyEligibilityDecider
from src.utils.exceptions import (
    MultiplesCalculationError,
    StepExecutionError,
    DataQualityError,
    DataValidationError,
    InvalidMultipleError,
)
from src.utils.valuation_logger import ValuationLogger

from ...base_step import StepInput
from .business_category_selection import determine_business_category
from .coordinators import (
    SMECalibrationCoordinator,
    ResultBuildingCoordinator,
    DataQualityCoordinator,
)
from .fallback_services import (
    create_fallback_provenance_tracker,
    create_fallback_recovery_service,
)
from .methodology_eligibility import determine_methodology_eligibility
from .multiples_collection import collect_multiples
from .multiples_processing import process_multiples
from .primary_method_selection import determine_primary_method_for_request

# Import new modules with fallback handling
try:
    from ..services import Step2RecoveryService
except ImportError:
    # Fallback for development - create a minimal recovery service
    Step2RecoveryService = None

try:
    from ..utils.provenance_tracker import Step2ProvenanceTracker
except ImportError:
    Step2ProvenanceTracker = None

try:
    from ..utils.validators import Step2InputValidator
except ImportError:
    Step2InputValidator = None


class Step2Orchestrator:
    """
    Orchestrates the main execution flow for Step 2 (Coordinator Pattern).
    
    Delegates complex operations to specialized coordinators:
    - SMECalibrationCoordinator: SME calibration and adjustments
    - ResultBuildingCoordinator: Result and metadata building
    - DataQualityCoordinator: Data quality warnings and validation
    """

    def __init__(
        self,
        industry_benchmark_collector,
        comparable_companies_collector,
        market_data_collector,
        multiples_calculator,
        business_type_triage,
        methodology_decider: MethodologyEligibilityDecider,
        insights_generator,
        validator,
        step_name: str,
        logger: ValuationLogger,
    ):
        """
        Initialize the orchestrator.

        Args:
            industry_benchmark_collector: Industry benchmark collector instance
            comparable_companies_collector: Comparable companies collector instance
            market_data_collector: Market data collector instance
            multiples_calculator: Multiples calculator instance
            business_type_triage: Business type triage engine instance
            methodology_decider: Methodology eligibility decider instance
            insights_generator: Insights generator instance
            validator: Validator instance
            step_name: Step name for StepOutput
            logger: Logger instance
        """
        self.industry_benchmark_collector = industry_benchmark_collector
        self.comparable_companies_collector = comparable_companies_collector
        self.market_data_collector = market_data_collector
        self.multiples_calculator = multiples_calculator
        self.business_type_triage = business_type_triage
        self.methodology_decider = methodology_decider
        self.insights_generator = insights_generator
        self.validator = validator
        self.step_name = step_name
        self.logger = logger
        
        # Initialize coordinators
        self.sme_calibration_coordinator = SMECalibrationCoordinator(logger_instance=logger)
        self.result_building_coordinator = ResultBuildingCoordinator(
            insights_generator=insights_generator,
            validator=validator,
            logger_instance=logger
        )
        self.data_quality_coordinator = DataQualityCoordinator(logger_instance=logger)
        
        # Initialize recovery service (with fallback if import failed)
        if Step2RecoveryService:
            self.recovery_service = Step2RecoveryService(logger)
        else:
            logger.warning("Step2RecoveryService not available, using inline recovery")
            self.recovery_service = create_fallback_recovery_service(logger)
        
        # Validate dependencies
        self._validate_dependencies()

    def _validate_dependencies(self) -> None:
        """Validate that all required dependencies are provided."""
        if not self.industry_benchmark_collector:
            raise ValueError("industry_benchmark_collector is required")
        if not self.comparable_companies_collector:
            raise ValueError("comparable_companies_collector is required")
        if not self.multiples_calculator:
            raise ValueError("multiples_calculator is required")
        if not self.business_type_triage:
            raise ValueError("business_type_triage is required")
        if not self.methodology_decider:
            raise ValueError("methodology_decider is required")
        if not self.logger:
            raise ValueError("logger is required")

    async def orchestrate_execution(
        self,
        input_data: StepInput,
        step0_result: Dict[str, Any],
        step1_result: Dict[str, Any],
        correlation_id: Optional[str] = None,
    ) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
        """
        Orchestrate the main execution flow.

        Args:
            input_data: Step input data
            step0_result: Step 0 result dictionary
            step1_result: Step 1 result dictionary
            correlation_id: Correlation ID for logging

        Returns:
            Tuple of (result_dict, metadata_dict, multiples_data_backup):
            - result_dict: Complete result dictionary
            - metadata_dict: Complete metadata dictionary
            - multiples_data_backup: Backup multiples data
        """
        # DEBUG: orchestrate_execution is one of the 12 sub-steps under Step 2;
        # the canonical Step 2 entry is the orchestrator-level "Starting Step 2".
        self.logger.debug(
            "Step 2: Orchestrate execution started",
            extra={
                "step_number": 2,
                "correlation_id": correlation_id,
                "has_request": input_data.request is not None,
                "has_step0_result": step0_result is not None,
                "has_step0": bool(step0_result),
                "has_step1_result": step1_result is not None,
                "has_step1": bool(step1_result),
                "operation": "orchestrate_execution_start",
            },
        )
        
        # Initialize provenance tracker (with fallback if import failed)
        if Step2ProvenanceTracker:
            provenance_tracker = Step2ProvenanceTracker(correlation_id=correlation_id)
        else:
            provenance_tracker = self._create_fallback_provenance_tracker(correlation_id)
        
        # Validate inputs at boundary (with fallback if import failed)
        if Step2InputValidator:
            try:
                Step2InputValidator.validate_step1_result(step1_result)
            except Exception as validation_error:
                self.logger.warning(
                    "Step 2: Input validation failed, continuing anyway",
                    extra={
                        "step_number": 2,
                        "correlation_id": correlation_id,
                        "error_type": type(validation_error).__name__,
                        "error_message": str(validation_error),
                    },
                )
        
        request = input_data.request
        _raw_revenue = step1_result.get("revenue", 0) or 0
        _raw_ebitda = step1_result.get("ebitda")
        _raw_ebitda_margin = step1_result.get("ebitda_margin", 0) or 0

        from src.utils.decimal_helpers import to_decimal
        revenue = to_decimal(_raw_revenue) if _raw_revenue else Decimal("0")
        ebitda = to_decimal(_raw_ebitda) if _raw_ebitda is not None else None
        ebitda_margin = to_decimal(_raw_ebitda_margin) if _raw_ebitda_margin else Decimal("0")

        # Phase 1: Business Type Integration
        try:
            category_result = await self._determine_business_category(request)
            # Defensive unpacking: ensure we get exactly 2 values
            if isinstance(category_result, tuple) and len(category_result) == 2:
                business_category, business_type_id = category_result
            else:
                self.logger.error(
                    "Step 2: _determine_business_category returned unexpected format",
                    extra={
                        "step_number": 2,
                        "correlation_id": correlation_id,
                        "return_type": type(category_result).__name__,
                        "return_length": len(category_result) if isinstance(category_result, tuple) else None,
                    },
                )
                # Fallback: try to extract values safely
                if isinstance(category_result, tuple):
                    business_category = category_result[0] if len(category_result) > 0 else None
                    business_type_id = category_result[1] if len(category_result) > 1 else None
                else:
                    business_category = category_result if category_result else None
                    business_type_id = None
        except ValueError as unpack_error:
            # Catch "too many values to unpack" errors specifically
            self.logger.error(
                "Step 2: Unpacking error in _determine_business_category",
                extra={
                    "step_number": 2,
                    "correlation_id": correlation_id,
                    "error_type": type(unpack_error).__name__,
                    "error_message": str(unpack_error),
                },
                exc_info=True,
            )
            # Fallback: use None values and let recovery handle it
            business_category = None
            business_type_id = None

        # Phase 2: DCF Eligibility
        eligibility_result = await self._determine_methodology_eligibility(request, step0_result)

        # Ensure DatabaseDrivenDefaults is initialized from Titan sme_calibration
        # so Priority 4 fallback (get_business_type_defaults) can use real data.
        sme_calibration = getattr(request, "sme_calibration", None)
        if sme_calibration and isinstance(sme_calibration, dict):
            try:
                from src.services.business_intelligence.database_driven_defaults import DatabaseDrivenDefaults
                DatabaseDrivenDefaults.initialize(sme_calibration)
            except (ImportError, ValueError, TypeError, KeyError) as e:
                self.logger.warning(
                    "Step 2: DatabaseDrivenDefaults.initialize failed — Priority 4 fallback may use generic defaults",
                    extra={"error": str(e), "error_type": type(e).__name__},
                )

        # Phase 3-4: Collect multiples and comparables
        comparables_data = await self._collect_comparables(request, revenue)
        try:
            multiples_result = await self._collect_multiples(
                request, ebitda, ebitda_margin, business_category, comparables_data, correlation_id
            )
            # Defensive unpacking: ensure we get exactly 2 values
            if isinstance(multiples_result, tuple) and len(multiples_result) == 2:
                multiples_data, multiples_data_backup = multiples_result
            else:
                self.logger.error(
                    "Step 2: _collect_multiples returned unexpected format",
                    extra={
                        "step_number": 2,
                        "correlation_id": correlation_id,
                        "return_type": type(multiples_result).__name__,
                        "return_length": len(multiples_result) if isinstance(multiples_result, tuple) else None,
                        "return_value": str(multiples_result)[:200] if multiples_result else None,
                    },
                )
                # Fallback: try to extract values safely
                if isinstance(multiples_result, tuple):
                    multiples_data = multiples_result[0] if len(multiples_result) > 0 else {}
                    multiples_data_backup = multiples_result[1] if len(multiples_result) > 1 else {}
                else:
                    multiples_data = multiples_result if isinstance(multiples_result, dict) else {}
                    multiples_data_backup = {}
        except ValueError as unpack_error:
            # Catch "too many values to unpack" errors specifically
            self.logger.error(
                "Step 2: Unpacking error in _collect_multiples",
                extra={
                    "step_number": 2,
                    "correlation_id": correlation_id,
                    "error_type": type(unpack_error).__name__,
                    "error_message": str(unpack_error),
                },
                exc_info=True,
            )
            # Fallback: use empty dicts and let recovery handle it
            multiples_data = {}
            multiples_data_backup = {}
        
        # Track multiples selection provenance (if tracker available)
        if multiples_data and hasattr(provenance_tracker, 'track_multiples_selection'):
            try:
                provenance_tracker.track_multiples_selection(
                    data_source=multiples_data.get("data_source", "unknown"),
                    multiples_data=multiples_data,
                    fallback_used=multiples_data.get("data_source") == "fallback_defaults",
                )
            except Exception as e:
                self.logger.debug(
                    "Step 2: Provenance tracking failed (non-critical)",
                    extra={"error": str(e)},
                )
        
        # Validate multiples ranges (with fallback if import failed)
        if multiples_data and Step2InputValidator:
            try:
                Step2InputValidator.validate_multiples_data(multiples_data)
            except (InvalidMultipleError, DataValidationError) as e:
                self.logger.warning(
                    "Step 2: Multiples validation failed, will use recovery if needed",
                    extra={
                        "step_number": 2,
                        "correlation_id": correlation_id,
                        "error_type": type(e).__name__,
                        "error_message": str(e),
                    },
                )

        # Phase 5: Process and validate multiples
        try:
            process_result = await self._process_multiples(
                request, multiples_data, multiples_data_backup, revenue, ebitda_margin, business_category, correlation_id
            )
            # Defensive unpacking: ensure we get exactly 3 values
            if isinstance(process_result, tuple) and len(process_result) == 3:
                multiples_data, sme_calibration_data, multiples_checksum = process_result
            else:
                self.logger.error(
                    "Step 2: _process_multiples returned unexpected format",
                    extra={
                        "step_number": 2,
                        "correlation_id": correlation_id,
                        "return_type": type(process_result).__name__,
                        "return_length": len(process_result) if isinstance(process_result, tuple) else None,
                    },
                )
                # Fallback: try to extract values safely
                if isinstance(process_result, tuple):
                    multiples_data = process_result[0] if len(process_result) > 0 else {}
                    sme_calibration_data = process_result[1] if len(process_result) > 1 else {}
                    multiples_checksum = process_result[2] if len(process_result) > 2 else ""
                else:
                    multiples_data = process_result if isinstance(process_result, dict) else {}
                    sme_calibration_data = {}
                    multiples_checksum = ""
        except ValueError as unpack_error:
            # Catch "too many values to unpack" errors specifically
            self.logger.error(
                "Step 2: Unpacking error in _process_multiples",
                extra={
                    "step_number": 2,
                    "correlation_id": correlation_id,
                    "error_type": type(unpack_error).__name__,
                    "error_message": str(unpack_error),
                },
                exc_info=True,
            )
            # Fallback: use defaults and let recovery handle it
            sme_calibration_data = {}
            multiples_checksum = ""
        
        # Track SME calibration provenance (if tracker available)
        if sme_calibration_data and hasattr(provenance_tracker, 'track_sme_calibration'):
            try:
                provenance_tracker.track_sme_calibration(
                    calibration_applied=bool(sme_calibration_data),
                    calibration_data=sme_calibration_data,
                )
            except Exception:
                pass  # Non-critical
        
        # Phase 6: Determine primary method and generate warnings
        primary_method = await self._determine_primary_method(
            request, ebitda, ebitda_margin, revenue, business_type_id, business_category
        )
        
        # Track primary method selection (if tracker available)
        if hasattr(provenance_tracker, 'track_primary_method_selection'):
            try:
                provenance_tracker.track_primary_method_selection(
                    primary_method=primary_method,
                    factors={
                        "ebitda_available": bool(ebitda),
                        "revenue_available": bool(revenue),
                        "business_type_id": business_type_id,
                        "business_category": getattr(business_category, "value", None),
                    },
                )
            except Exception:
                pass  # Non-critical
        
        # BANK-GRADE: Pass industry benchmarks from Titan enrichment for deviation warnings
        # These warnings are INFORMATIONAL ONLY - they do NOT block valuations
        titan_benchmarks = getattr(request, "industry_benchmarks", None)
        data_quality_warnings = self.data_quality_coordinator.generate_data_quality_warnings(
            revenue=revenue,
            ebitda=ebitda,
            ebitda_margin=ebitda_margin,
            titan_benchmarks=titan_benchmarks,
            multiples_data=multiples_data,
            # ebitda_margin above comes from Step 1, so the warning can name the
            # earnings basis it was computed on. metrics_builder derives the same
            # label from the same Step 1 flag — that is what makes
            # financial_metrics.ebitda_margin and the warning's actual_margin_pct
            # provably the same measurement rather than two rival numbers.
            margin_basis=(
                "step_1_weighted_earnings_basis"
                if step1_result.get("using_weighted_metrics")
                else "current_year_reported"
            ),
            current_year_data=getattr(request, "current_year_data", None),
        )

        # Log before building result dict
        self.logger.debug(
            "Step 2: About to build result dict",
            extra={
                "step_number": 2,
                "correlation_id": correlation_id,
                "multiples_data_keys": list(multiples_data.keys()) if multiples_data else [],
                "multiples_data_size": len(multiples_data) if multiples_data else 0,
                "has_ev_ebitda": "ev_ebitda" in multiples_data if multiples_data else False,
                "has_ev_revenue": "ev_revenue" in multiples_data if multiples_data else False,
                "ev_ebitda_value": str(multiples_data.get("ev_ebitda")) if multiples_data else None,
                "ev_revenue_value": str(multiples_data.get("ev_revenue")) if multiples_data else None,
                "data_source": multiples_data.get("data_source") if multiples_data else None,
            },
        )

        # Build result dictionary using coordinator
        try:
            result_dict = self.result_building_coordinator.build_result_dict(
                request=request,
                primary_method=primary_method,
                multiples_data=multiples_data,
                comparables_data=comparables_data,
                eligibility_result=eligibility_result,
                business_category=business_category,
                business_type_id=business_type_id,
                data_quality_warnings=data_quality_warnings,
                sme_calibration_data=sme_calibration_data,
                correlation_id=correlation_id,
            )
            
            # Log result dict after building
            self.logger.debug(
                "Step 2: Result dict built successfully",
                extra={
                    "step_number": 2,
                    "correlation_id": correlation_id,
                    "result_dict_size": len(result_dict) if result_dict else 0,
                    "result_dict_keys": list(result_dict.keys()) if result_dict else [],
                    "ev_ebitda_multiple": str(result_dict.get("ev_ebitda_multiple")) if result_dict else None,
                    "ev_revenue_multiple": str(result_dict.get("ev_revenue_multiple")) if result_dict else None,
                    "data_source": result_dict.get("data_source") if result_dict else None,
                },
            )
        except (MultiplesCalculationError, DataQualityError) as e:
            # Specific exceptions - use recovery service
            self.logger.warning(
                "Step 2: Result building failed, attempting recovery",
                extra={
                    "step_number": 2,
                    "correlation_id": correlation_id,
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                    "multiples_data_keys": list(multiples_data.keys()) if multiples_data else [],
                    "multiples_data_source": multiples_data.get("data_source") if multiples_data else None,
                    "has_multiples_backup": multiples_data_backup is not None and len(multiples_data_backup) > 0,
                },
                exc_info=True,
            )
            
            # Track recovery provenance (if tracker available)
            if hasattr(provenance_tracker, 'track_recovery'):
                try:
                    provenance_tracker.track_recovery(
                        recovery_method="recovery_service",
                        backup_available=bool(multiples_data_backup),
                        error_type=type(e).__name__,
                    )
                except Exception:
                    pass  # Non-critical
            
            # Use recovery service with full business context for SME-aware defaults
            result_dict = self.recovery_service.recover_result_dict(
                backup=multiples_data_backup,
                error=e,
                context={
                    "correlation_id": correlation_id,
                    "primary_method": primary_method,
                    "business_type_id": business_type_id,
                    "business_category": business_category,
                    "industry": getattr(request, "industry", None),
                    "allow_untrusted_multiples_fallback": getattr(
                        request, "allow_untrusted_multiples_fallback", False
                    ) is True
                    or (
                        isinstance(getattr(request, "metadata", None), dict)
                        and getattr(request, "metadata", {}).get(
                            "allow_untrusted_multiples_fallback"
                        )
                        is True
                    ),
                }
            )
        except Exception as e:
            # Unexpected error - log and re-raise
            self.logger.critical(
                "Step 2: Unexpected error in result building",
                extra={
                    "step_number": 2,
                    "correlation_id": correlation_id,
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                },
                exc_info=True,
            )
            raise StepExecutionError(
                f"Step 2 failed unexpectedly: {str(e)}",
                step_number=2,
                step_name=self.step_name,
                context={"correlation_id": correlation_id}
            ) from e

        # Build metadata using coordinator
        try:
            metadata_dict = self.result_building_coordinator.build_metadata_dict(
                request=request,
                result_dict=result_dict,
                eligibility_result=eligibility_result,
                comparables_data=comparables_data,
                business_category=business_category,
                multiples_checksum=multiples_checksum,
                previous_results=input_data.previous_results,
            )
        except (MultiplesCalculationError, DataQualityError) as e:
            self.logger.warning(
                "Step 2: Failed to build metadata dict, using empty metadata",
                extra={
                    "step_number": 2,
                    "correlation_id": correlation_id,
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                    "result_dict_size": len(result_dict) if result_dict else 0,
                },
                exc_info=True,
            )
            # Return empty metadata dict - non-critical
            metadata_dict = {}
        except Exception as e:
            self.logger.error(
                "Step 2: Unexpected error building metadata dict",
                extra={
                    "step_number": 2,
                    "correlation_id": correlation_id,
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                },
                exc_info=True,
            )
            # Return empty metadata dict - non-critical, don't fail the step
            metadata_dict = {}

        # Final validation before return - attempt recovery if empty or None
        # Ensure result_dict is initialized as empty dict if None
        if result_dict is None:
            result_dict = {}
        
        if not result_dict or len(result_dict) == 0:
            self.logger.warning(
                "Step 2: Result dict is empty, attempting recovery from multiples_data_backup",
                extra={
                    "step_number": 2,
                    "correlation_id": correlation_id,
                    "multiples_data_keys": list(multiples_data.keys()) if multiples_data else [],
                    "multiples_data_size": len(multiples_data) if multiples_data else 0,
                    "multiples_data_backup_keys": list(multiples_data_backup.keys()) if multiples_data_backup else [],
                    "multiples_data_backup_size": len(multiples_data_backup) if multiples_data_backup else 0,
                    "multiples_data_backup_type": type(multiples_data_backup).__name__ if multiples_data_backup else None,
                    "multiples_data_backup_is_none": multiples_data_backup is None,
                    "has_metadata": metadata_dict is not None,
                    "result_dict_type": type(result_dict).__name__,
                    "result_dict_is_none": result_dict is None,
                },
            )
            
            # Track recovery provenance (if tracker available)
            if hasattr(provenance_tracker, 'track_recovery'):
                try:
                    provenance_tracker.track_recovery(
                        recovery_method="recovery_service_empty_dict",
                        backup_available=bool(multiples_data_backup),
                        error_type="EmptyResultDict",
                    )
                except Exception:
                    pass  # Non-critical
            
            # Use recovery service for empty dict case with full business context
            result_dict = self.recovery_service.recover_result_dict(
                backup=multiples_data_backup,
                error=Exception("Result dict is empty"),
                context={
                    "correlation_id": correlation_id,
                    "primary_method": primary_method,
                    "business_type_id": business_type_id,
                    "business_category": business_category,
                    "industry": getattr(request, "industry", None),
                    "allow_untrusted_multiples_fallback": getattr(
                        request, "allow_untrusted_multiples_fallback", False
                    ) is True
                    or (
                        isinstance(getattr(request, "metadata", None), dict)
                        and getattr(request, "metadata", {}).get(
                            "allow_untrusted_multiples_fallback"
                        )
                        is True
                    ),
                }
            )
        else:
            self.logger.debug(
                "Step 2: Result dict built successfully",
                extra={
                    "step_number": 2,
                    "correlation_id": correlation_id,
                    "result_dict_size": len(result_dict),
                    "result_dict_keys": list(result_dict.keys())[:10],  # First 10 keys
                },
            )
        
        # Add provenance to result dict (if tracker available)
        if hasattr(provenance_tracker, 'add_to_result_dict'):
            try:
                result_dict = provenance_tracker.add_to_result_dict(result_dict)
            except Exception:
                # Non-critical - continue without provenance
                pass

        return result_dict, metadata_dict, multiples_data_backup
    
    def _create_fallback_recovery_service(self, logger):
        """Create a minimal fallback recovery service if import failed."""
        return create_fallback_recovery_service(logger)
    
    def _create_fallback_provenance_tracker(self, correlation_id):
        """Create a minimal fallback provenance tracker if import failed."""
        return create_fallback_provenance_tracker(correlation_id)

    async def _determine_business_category(
        self, request: Any
    ) -> Tuple[Optional[BusinessTypeCategory], Optional[str]]:
        """
        Determine business category and type ID.
        
        Returns:
            Tuple of (business_category, business_type_id)
        """
        return await determine_business_category(
            request=request,
            business_type_triage=self.business_type_triage,
            logger=self.logger,
        )

    async def _determine_methodology_eligibility(
        self, request: Any, step0_result: Dict[str, Any]
    ) -> Any:
        """
        Determine methodology eligibility (DCF vs Multiples).
        
        Returns:
            Eligibility result object
        """
        return determine_methodology_eligibility(
            request=request,
            step0_result=step0_result,
            methodology_decider=self.methodology_decider,
            logger=self.logger,
        )

    async def _collect_comparables(
        self, request: Any, revenue: Any
    ) -> Dict[str, Any]:
        """
        Collect comparable companies data.
        
        Returns:
            Comparables data dictionary
        """
        comparables_data = await self.comparable_companies_collector.find_comparable_companies(
            request, revenue
        )
        return comparables_data

    async def _collect_multiples(
        self,
        request: Any,
        ebitda: Optional[Any],
        ebitda_margin: Any,
        business_category: Optional[BusinessTypeCategory],
        comparables_data: Dict[str, Any],
        correlation_id: Optional[str],
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """
        Collect multiples using priority cascade and store backup.
        
        Returns:
            Tuple of (multiples_data, multiples_data_backup)
        """
        return await collect_multiples(
            request=request,
            ebitda=ebitda,
            ebitda_margin=ebitda_margin,
            business_category=business_category,
            comparables_data=comparables_data,
            correlation_id=correlation_id,
            industry_benchmark_collector=self.industry_benchmark_collector,
            market_data_collector=self.market_data_collector,
            logger=self.logger,
        )

    async def _process_multiples(
        self,
        request: Any,
        multiples_data: Dict[str, Any],
        multiples_data_backup: Dict[str, Any],
        revenue: Any,
        ebitda_margin: Any,
        business_category: Optional[BusinessTypeCategory],
        correlation_id: Optional[str],
    ) -> Tuple[Dict[str, Any], Dict[str, Any], str]:
        """
        Process multiples: apply calibration, validate, and generate checksum.
        
        Returns:
            Tuple of (validated_multiples_data, sme_calibration_data, multiples_checksum)
        """
        return await process_multiples(
            request=request,
            multiples_data=multiples_data,
            multiples_data_backup=multiples_data_backup,
            revenue=revenue,
            ebitda_margin=ebitda_margin,
            business_category=business_category,
            correlation_id=correlation_id,
            sme_calibration_coordinator=self.sme_calibration_coordinator,
            data_quality_coordinator=self.data_quality_coordinator,
            logger=self.logger,
        )

    async def _determine_primary_method(
        self,
        request: Any,
        ebitda: Optional[Any],
        ebitda_margin: Any,
        revenue: Any,
        business_type_id: Optional[str],
        business_category: Optional[BusinessTypeCategory],
    ) -> str:
        """
        Determine primary valuation method.
        
        Returns:
            Primary method string (e.g., "EV/EBITDA", "EV/Revenue")
        """
        return await determine_primary_method_for_request(
            request=request,
            ebitda=ebitda,
            ebitda_margin=ebitda_margin,
            revenue=revenue,
            business_type_id=business_type_id,
            business_category=business_category,
            data_quality_coordinator=self.data_quality_coordinator,
            multiples_calculator=self.multiples_calculator,
            logger=self.logger,
        )
