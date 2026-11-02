from typing import Any, Dict

from src.utils.logging import get_logger

from ..subcalculators.subcalculation_registry import Step0SubcalculationRegistry

logger = get_logger(__name__)


class Step0SubcalculationExecutor:
    def __init__(self, registry: Step0SubcalculationRegistry):
        self.registry = registry

    def execute(self, request: Any, step_number: int = 0) -> Dict[str, Any]:
        results: Dict[str, Any] = {}

        for calculator in self.registry.get_applicable(request):
            try:
                payload = calculator.calculate(request)
                if payload:
                    results[calculator.key] = payload
            except Exception as exc:  # pragma: no cover - defensive orchestration
                logger.warning(
                    "⚠️ Step 0 sub-calculation failed",
                    extra={
                        "step_number": step_number,
                        "subcalculator": getattr(calculator, "key", calculator.__class__.__name__),
                        "error": str(exc),
                    },
                    exc_info=True,
                )

        return results
