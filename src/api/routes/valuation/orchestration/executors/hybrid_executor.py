"""
Hybrid Executor

Executes Hybrid valuation methodology combining DCF and Multiples.
Delegates to HybridMethodologyOrchestrator for actual execution.
"""

from typing import Any, Dict, Optional

from src.api.schemas import ValuationRequest
from src.utils.valuation_logger import ValuationLogger

from .methodology_executor import MethodologyExecutor


class HybridExecutor(MethodologyExecutor):
    """
    Executor for Hybrid valuation methodology.

    Responsibilities:
    - Execute Hybrid valuation via HybridMethodologyOrchestrator
    - Coordinate DCF and Multiples execution
    - Handle weight calculation and result synthesis
    """

    def __init__(self, hybrid_orchestrator, logger: Optional[ValuationLogger] = None):
        """
        Initialize Hybrid executor.

        Args:
            hybrid_orchestrator: HybridMethodologyOrchestrator instance
            logger: Optional logger instance
        """
        super().__init__(logger)
        self.hybrid_orchestrator = hybrid_orchestrator
        self.logger.debug("✅ HybridExecutor initialized")

    async def execute(
        self, request: ValuationRequest, context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Execute Hybrid valuation.

        Delegates to HybridMethodologyOrchestrator which handles:
        - DCF eligibility determination
        - Weight calculation (priority cascade)
        - Result aggregation
        - Synthesis logic

        Args:
            request: Valuation request
            context: Optional processing context

        Returns:
            Dictionary with Hybrid valuation results
        """
        self.validate_request(request)

        try:
            self.logger.info("📊 Executing Hybrid valuation")

            # Delegate to hybrid orchestrator
            detailed_results = await self.hybrid_orchestrator.execute_hybrid(request, context)

            # Log execution summary
            dcf_created = detailed_results.get("dcf_valuation") is not None
            self.logger.info(
                "📊 Hybrid Methodology Execution Summary",
                extra={
                    "dcf_executed": dcf_created,
                    "dcf_equity_value": (
                        detailed_results.get("dcf_valuation", {}).get("equity_value")
                        if dcf_created
                        else None
                    ),
                    "multiples_executed": detailed_results.get("multiples_valuation") is not None,
                    "multiples_equity_value": (
                        detailed_results.get("multiples_valuation", {}).get("equity_value")
                        if detailed_results.get("multiples_valuation")
                        else None
                    ),
                    "dcf_weight": detailed_results.get("dcf_weight", 0.0),
                    "multiples_weight": detailed_results.get("multiples_weight", 0.0),
                    "final_equity_value_mid": detailed_results.get("equity_value_mid"),
                },
            )

            self.logger.info("✅ Hybrid valuation completed")
            return detailed_results

        except Exception as e:
            self.handle_execution_error(e, request, context)
            raise
