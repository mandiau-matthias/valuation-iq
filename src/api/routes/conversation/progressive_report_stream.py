"""Retired progressive-report conversation streaming compatibility boundary.

Titan owns interactive conversation and progressive-report orchestration.
ValuationIQ is the stateless valuation/report engine. This module remains only
so stale imports fail closed without importing the removed conversation stack.
"""

import json
from datetime import datetime, timezone
from typing import Any, AsyncGenerator, Dict, Optional

from fastapi import HTTPException
from fastapi.responses import StreamingResponse

from src.api.streaming.sse import get_sse_headers

LEGACY_PROGRESSIVE_REPORT_STREAM_STATUS_CODE = 410
LEGACY_PROGRESSIVE_REPORT_STREAM_EVENT = "legacy_progressive_report_stream_removed"
LEGACY_PROGRESSIVE_REPORT_STREAM_MESSAGE = (
    "ValuationIQ no longer owns progressive conversation report streaming. "
    "Use Titan-owned conversation/report orchestration APIs for interactive flows."
)


def legacy_progressive_report_stream_payload(session_id: Optional[str] = None) -> Dict[str, Any]:
    """Build a stable machine-readable payload for retired progressive streams."""
    payload: Dict[str, Any] = {
        "event": LEGACY_PROGRESSIVE_REPORT_STREAM_EVENT,
        "type": "error",
        "status_code": LEGACY_PROGRESSIVE_REPORT_STREAM_STATUS_CODE,
        "message": LEGACY_PROGRESSIVE_REPORT_STREAM_MESSAGE,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    if session_id:
        payload["session_id"] = session_id
    return payload


def legacy_progressive_report_stream_exception() -> HTTPException:
    """Return the canonical HTTP exception for retired progressive stream APIs."""
    return HTTPException(
        status_code=LEGACY_PROGRESSIVE_REPORT_STREAM_STATUS_CODE,
        detail=LEGACY_PROGRESSIVE_REPORT_STREAM_MESSAGE,
    )


async def stream_progressive_report(
    session_id: str,
    conversation_context: Optional[Dict[str, Any]] = None,
) -> AsyncGenerator[str, None]:
    """Yield one explicit retirement event for stale streaming callers."""
    del conversation_context
    yield json.dumps(legacy_progressive_report_stream_payload(session_id))


def create_streaming_response(
    session_id: str,
    conversation_context: Optional[Dict[str, Any]] = None,
) -> StreamingResponse:
    """Return a fail-closed SSE response for stale progressive stream callers."""

    async def generate() -> AsyncGenerator[str, None]:
        async for chunk in stream_progressive_report(session_id, conversation_context):
            yield f"data: {chunk}\n\n"

    return StreamingResponse(
        generate(),
        status_code=LEGACY_PROGRESSIVE_REPORT_STREAM_STATUS_CODE,
        media_type="text/event-stream",
        headers=get_sse_headers(),
    )


async def get_report_progress(session_id: str) -> Dict[str, Any]:
    """Progress tracking moved to Titan with the rest of conversation state."""
    del session_id
    raise legacy_progressive_report_stream_exception()


async def stream_report(
    session_id: str,
    conversation_context: Optional[Dict[str, Any]] = None,
) -> StreamingResponse:
    """FastAPI-compatible stale endpoint shim."""
    return create_streaming_response(session_id, conversation_context)


async def get_progress(session_id: str) -> Dict[str, Any]:
    """FastAPI-compatible stale progress endpoint shim."""
    return await get_report_progress(session_id)
