"""
Request Builder Coordinator

Coordinates building valuation requests from conversation context,
using the AIGuidedAdapter for data transformation.
"""

import logging
from typing import Any, Dict

from src.utils.exceptions import ValuationEngineError


class RequestBuilderCoordinator:
    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    async def build_valuation_request(self, context: Any) -> Dict[str, Any]:
        collected_data = getattr(context, "collected_data", None)
        company_info = getattr(context, "company_info", None) or {}
        session_id = getattr(context, "session_id", "unknown")

        if collected_data is None:
            raise ValuationEngineError("No collected data available to build request")

        from src.api.routes.valuation.request_builder import AIGuidedAdapter

        adapter = AIGuidedAdapter()
        base_request = adapter.convert(collected_data, company_info)

        from src.api.schemas.partial_valuation import PartialValuationRequest

        if isinstance(base_request, PartialValuationRequest):
            # Dispatch is explicit; callers must use the shared /calculate-partial
            # contract instead of projecting absent fields into a legacy request.
            result = {
                "request_kind": "partial_valuation",
                "input": base_request.model_dump(mode="json"),
            }
        else:
            result = dict(base_request)
        result["business_context"] = {
            "session_id": session_id,
            "data_source": "ai_guided_conversation",
        }

        owner_profile = (
            collected_data.get("owner_profile") if isinstance(collected_data, dict) else None
        )
        if owner_profile:
            result["business_context"]["owner_profile"] = owner_profile

        self.logger.info(
            "Built valuation request for session %s with %d fields",
            session_id,
            len(result),
        )

        return result
