"""
SSE streaming utilities.

RESPONSIBILITIES:
- SSE header generation with proper configuration
- Stream validation and error recovery
- Keepalive ping management
- CORS and proxy buffer handling

CRITICAL BUG FIXES:
- ✅ X-Accel-Buffering: no header (prevents Railway/nginx buffering)
- ✅ Proper CORS headers for production
- ✅ Keepalive mechanism to prevent timeouts
- ✅ SSE format validation

These helpers are intentionally not tied to conversation routes. ValuationIQ
uses them for stateless valuation streaming; Titan owns conversation streams.
"""

import json
import asyncio
from typing import Dict, Any, Optional, AsyncGenerator, List
from datetime import datetime

from src.utils.logging import get_logger
from decimal import Decimal
from src.utils.decimal_helpers import to_decimal, from_decimal
from src.utils.exceptions import ValuationEngineError

logger = get_logger(__name__)


def get_sse_headers(origin: Optional[str] = None) -> Dict[str, str]:
    """
    Returns proper SSE headers including critical proxy buffer fix

    CRITICAL FIXES:
    - X-Accel-Buffering: no → Prevents Railway/nginx from buffering SSE responses
    - Connection: keep-alive → Maintains persistent connection
    - Cache-Control: no-cache → Prevents caching of streaming responses
    - CORS headers → Uses provided origin or defaults to allow all (for non-credential requests)

    Args:
        origin: Optional origin to allow in CORS headers. If None, uses wildcard.
                Note: When credentials are required, origin must be explicitly set.

    Returns:
        Dictionary of HTTP headers for SSE streaming
    """
    from src.config import get_settings

    settings = get_settings()

    # Determine allowed origin
    # If origin is provided and is in allowed_origins, use it
    # Otherwise, let CORS middleware handle it (don't set Access-Control-Allow-Origin here)
    # The CORS middleware will set the appropriate headers
    headers = {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",  # ← CRITICAL FIX: Prevents proxy buffering
        "Access-Control-Allow-Headers": "Cache-Control, Content-Type, Authorization, X-Correlation-ID",
        "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
        "Content-Type": "text/event-stream; charset=utf-8",
    }

    # Only set Access-Control-Allow-Origin if origin is explicitly provided and allowed
    # Otherwise, let the CORS middleware handle it
    if origin:
        # Normalize allowed_origins to list if it's a string
        allowed_origins = settings.allowed_origins
        if isinstance(allowed_origins, str):
            allowed_origins = [o.strip() for o in allowed_origins.split(",") if o.strip()]

        # Check if origin is in allowed list
        if origin in allowed_origins or "*" in allowed_origins:
            headers["Access-Control-Allow-Origin"] = origin
            headers["Access-Control-Allow-Credentials"] = "true"

    return headers


def format_sse_event(event_type: str, data: Any, event_id: Optional[str] = None) -> str:
    """
    Format data as Server-Sent Event (SSE) with proper structure

    SSE Format:
    ```
    data: {json_data}

    ```

    Args:
        event_type: Type of event (used within JSON data)
        data: Data to send (will be JSON serialized)
        event_id: Optional event ID for client-side tracking

    Returns:
        Properly formatted SSE string
    """
    try:
        # Ensure data is dict
        event_data: Dict[str, Any] = data if isinstance(data, dict) else {"content": str(data)}

        # Add event type to data
        event_data["type"] = event_type

        # Defensive check: Remove any ConversationContext objects that might be accidentally included
        def clean_for_json(obj: Any) -> Any:
            """Recursively clean object for JSON serialization"""
            # Handle Decimal objects first (convert to string to maintain precision)
            if isinstance(obj, Decimal):
                return str(obj)
            elif isinstance(obj, dict):
                return {k: clean_for_json(v) for k, v in obj.items() if not k.startswith("_")}
            elif isinstance(obj, list):
                return [clean_for_json(item) for item in obj]
            elif isinstance(obj, (str, int, float, bool, type(None))):
                return obj
            elif hasattr(obj, "__dict__"):
                # Skip complex objects that aren't JSON serializable
                return str(obj)
            else:
                return obj

        # Clean data before serialization
        cleaned_data = clean_for_json(event_data)

        # JSON serialize
        json_data = json.dumps(cleaned_data, ensure_ascii=False)

        # Format as SSE
        sse_lines = []
        if event_id:
            sse_lines.append(f"id: {event_id}")
        sse_lines.append(f"data: {json_data}")
        sse_lines.append("")  # Empty line terminates event

        return "\n".join(sse_lines) + "\n"

    except Exception as e:
        logger.error(
            "Failed to format SSE event", extra={"event_type": event_type, "error": str(e)}
        )
        # Return error event
        error_data = {"type": "error", "message": "Failed to format event", "error": str(e)}
        return f"data: {json.dumps(error_data)}\n\n"


def validate_sse_format(event_string: str) -> bool:
    """
    Validate that a string is properly formatted as SSE

    Args:
        event_string: String to validate

    Returns:
        True if properly formatted, False otherwise
    """
    try:
        # SSE must start with "data: "
        if not event_string.startswith("data: "):
            return False

        # SSE must end with double newline
        if not event_string.endswith("\n\n"):
            return False

        # Extract JSON data
        lines = event_string.strip().split("\n")
        data_line = next((line for line in lines if line.startswith("data: ")), None)

        if not data_line:
            return False

        # Validate JSON
        json_str = data_line[6:]  # Remove "data: " prefix
        json.loads(json_str)

        return True

    except json.JSONDecodeError:
        return False
    except Exception as e:
        logger.debug("SSE validation failed", extra={"error": str(e)})
        return False


async def send_keepalive(
    session_id: str, interval: Decimal = Decimal("15.0")
) -> AsyncGenerator[str, None]:
    """
    Send periodic keepalive pings to prevent connection timeout

    Args:
        session_id: Session identifier for logging
        interval: Seconds between pings (default 15s)

    Yields:
        Keepalive SSE events
    """
    try:
        while True:
            # Convert Decimal to float for asyncio.sleep
            await asyncio.sleep(float(interval))

            # Send keepalive comment (SSE standard)
            yield f": keepalive {datetime.utcnow().isoformat()}\n\n"

            logger.debug("Keepalive ping sent", extra={"session_id": session_id})

    except asyncio.CancelledError:
        logger.info("Keepalive cancelled", extra={"session_id": session_id})
        raise
    except ValuationEngineError as e:
        logger.error("Keepalive error", extra={"session_id": session_id, "error": str(e)})


def create_error_event(error: Exception, session_id: str) -> str:
    """
    Create a properly formatted error event for streaming

    Args:
        error: Exception that occurred
        session_id: Session identifier

    Returns:
        Formatted SSE error event
    """
    error_data = {
        "type": "error",
        "message": f"An error occurred: {str(error)}",
        "error_type": type(error).__name__,
        "session_id": session_id,
        "timestamp": datetime.utcnow().isoformat(),
    }

    return format_sse_event("error", error_data)


def create_completion_event(session_id: str, metadata: Optional[Dict[str, Any]] = None) -> str:
    """
    Create a completion event to signal end of stream

    Args:
        session_id: Session identifier
        metadata: Optional metadata to include

    Returns:
        Formatted SSE completion event
    """
    completion_data = {
        "type": "complete",
        "session_id": session_id,
        "timestamp": datetime.utcnow().isoformat(),
        **(metadata or {}),
    }

    return format_sse_event("complete", completion_data)


async def handle_stream_error(
    error: Exception, session_id: str, context: Optional[Dict[str, Any]] = None
) -> AsyncGenerator[str, None]:
    """
    Handle streaming errors gracefully with proper error events

    Args:
        error: Exception that occurred
        session_id: Session identifier
        context: Optional context for debugging

    Yields:
        Error event and completion event
    """
    try:
        # Log error with full context
        logger.error(
            "Stream error occurred",
            extra={
                "session_id": session_id,
                "error_type": type(error).__name__,
                "error_message": str(error),
                "context": context,
            },
            exc_info=True,
        )

        # Send error event to client
        yield create_error_event(error, session_id)

        # Send completion event
        yield create_completion_event(
            session_id, {"terminated_by_error": True, "error_type": type(error).__name__}
        )

    except ValuationEngineError as e:
        # If error handling fails, send minimal error event
        logger.critical(
            "Error handler failed",
            extra={"session_id": session_id, "original_error": str(error), "handler_error": str(e)},
        )
        yield f"data: {json.dumps({'type': 'error', 'message': 'Critical error occurred'})}\n\n"


def chunk_large_content(content: str, chunk_size: int = 1000) -> List[str]:
    """
    Split large content into smaller chunks for streaming

    Args:
        content: Content to chunk
        chunk_size: Maximum characters per chunk

    Returns:
        List of content chunks
    """
    if len(content) <= chunk_size:
        return [content]

    # Split on word boundaries when possible
    chunks = []
    current_chunk = ""

    words = content.split()
    for word in words:
        if len(current_chunk) + len(word) + 1 <= chunk_size:
            current_chunk += (" " if current_chunk else "") + word
        else:
            if current_chunk:
                chunks.append(current_chunk)
            current_chunk = word

    if current_chunk:
        chunks.append(current_chunk)

    return chunks


def sanitize_for_sse(text: str) -> str:
    """
    Sanitize text for safe SSE transmission

    Args:
        text: Text to sanitize

    Returns:
        Sanitized text safe for SSE
    """
    # Remove or escape problematic characters
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # Ensure no "data: " appears in content (would break SSE format)
    text = text.replace("data: ", "data_ ")

    return text


def estimate_stream_duration(content_length: int) -> Decimal:
    """
    Estimate streaming duration based on content length

    Args:
        content_length: Length of content to stream

    Returns:
        Estimated duration in seconds
    """
    # Assume ~100 characters per second (typical reading speed)
    return content_length / Decimal("100.0")


# Context manager for SSE streaming
class SSEStream:
    """
    Context manager for SSE streaming with automatic resource cleanup

    Usage:
    ```python
    async with SSEStream(session_id) as stream:
        async for event in generate_events():
            await stream.send(event)
    ```
    """

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.start_time: Optional[datetime] = None
        self.event_count = 0
        self.keepalive_task: Optional[asyncio.Task[Any]] = None

    async def __aenter__(self) -> "SSEStream":
        """Enter context - start streaming"""
        self.start_time = datetime.utcnow()
        logger.info("SSE stream started", extra={"session_id": self.session_id})
        return self

    async def __aexit__(
        self,
        exc_type: Optional[type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Any,
    ) -> None:
        """Exit context - cleanup resources"""
        del exc_val, exc_tb
        if self.keepalive_task:
            self.keepalive_task.cancel()
            try:
                await self.keepalive_task
            except asyncio.CancelledError:
                pass

        duration = (
            (datetime.utcnow() - self.start_time).total_seconds()
            if self.start_time is not None
            else 0.0
        )

        logger.info(
            "SSE stream ended",
            extra={
                "session_id": self.session_id,
                "duration_seconds": duration,
                "event_count": self.event_count,
                "had_error": exc_type is not None,
            },
        )

    async def send(self, event: str) -> str:
        """Send an SSE event"""
        self.event_count += 1
        return event
