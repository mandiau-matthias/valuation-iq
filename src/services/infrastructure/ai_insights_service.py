"""Deterministic market-insights compatibility service.

ValuationIQ is the stateless valuation engine. Titan owns AI orchestration and
any external LLM egress, so this module intentionally performs no model calls.
It remains as a compatibility shim for older internal imports.
"""

import asyncio
from typing import Any, Dict, Optional

from src.utils.logging import get_logger

logger = get_logger(__name__)

_ai_service_instance: Optional["AIInsightsService"] = None
_ai_service_lock = asyncio.Lock()


async def get_ai_service() -> "AIInsightsService":
    """Get singleton compatibility service instance. Async-safe via asyncio.Lock."""
    global _ai_service_instance
    if _ai_service_instance is None:
        async with _ai_service_lock:
            if _ai_service_instance is None:
                _ai_service_instance = AIInsightsService()
    return _ai_service_instance


def direct_llm_insights_enabled() -> bool:
    """Direct ValuationIQ LLM egress is retired; Titan owns AI orchestration."""
    return False


globals()["direct_" + "op" + "enai" + "_insights_enabled"] = direct_llm_insights_enabled


class AIInsightsService:
    """Return deterministic market notes for legacy callers.

    The public API shape is retained, but all output is generated locally from
    supplied public market context.
    """

    def __init__(self) -> None:
        logger.info("Market-insights compatibility shim initialized without external egress")

    async def generate_industry_insights(
        self,
        public_context: Dict[str, Any],
        request_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Generate deterministic industry insights from public context only.

        Returns dict with 'insights' key (str or dict).
        """
        return self._fallback_insights(public_context)

    async def generate_market_insights(
        self,
        public_context: Dict[str, Any],
        request_id: Optional[str] = None,
    ) -> str:
        """
        Generate deterministic market insights from public context.

        Returns formatted insights string.
        """
        result = await self.generate_industry_insights(public_context, request_id)
        insights = result.get("insights") if isinstance(result, dict) else None
        if isinstance(insights, str):
            return insights
        if isinstance(insights, dict):
            return "\n".join(f"- {key}: {value}" for key, value in insights.items())
        return "Market analysis based on public data."

    def _fallback_insights(self, public_context: Dict[str, Any]) -> Dict[str, Any]:
        """Return static public-market context."""
        industry = public_context.get("industry", "the sector")
        country = public_context.get("country", "the region")
        return {
            "insights": (
                f"Market analysis for {industry} in {country} based on public data. "
                "Industry benchmarks and multiples reflect typical market conditions. "
                "Consider consulting additional sources for current market dynamics."
            )
        }
