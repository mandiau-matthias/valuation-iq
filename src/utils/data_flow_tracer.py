"""
DataFlowTracer: Track revenue_multiple through the pipeline

CTO-LEVEL ROBUSTNESS:
- Tracks revenue_multiple value at every transformation point
- Stores trace in request context for debugging
- Returns trace in response metadata (dev/staging only)
- Helps identify exact point where value is lost

Concurrency:
    The active tracer is stored in a :class:`contextvars.ContextVar`, so concurrent asyncio
    tasks each see their own tracer (same pattern as ``logging_context``). Work running in a
    thread pool without a copied context will not see the tracer from the originating task.

USAGE:
    Construct DataFlowTracer (or use get_tracer), call checkpoint at pipeline steps with
    revenue_multiple / ev_ebitda_ratio as needed, then get_trace() for the full trace payload.
"""

import json
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional


@dataclass
class Checkpoint:
    """Represents a checkpoint in the data flow"""

    name: str
    timestamp: datetime
    revenue_multiple: Optional[Decimal]
    ev_ebitda_ratio: Optional[Decimal]
    context: Dict[str, Any] = field(default_factory=dict)
    notes: Optional[str] = None


class DataFlowTracer:
    """
    Tracks revenue_multiple through the valuation pipeline.

    This tracer helps identify exactly where the value is lost
    by recording checkpoints at every transformation point.
    """

    def __init__(self, request_id: Optional[str] = None):
        self.request_id = request_id
        self.checkpoints: List[Checkpoint] = []
        self.start_time = datetime.now(timezone.utc)

    def checkpoint(
        self,
        name: str,
        revenue_multiple: Optional[Decimal] = None,
        ev_ebitda_ratio: Optional[Decimal] = None,
        context: Optional[Dict[str, Any]] = None,
        notes: Optional[str] = None,
    ):
        """
        Record a checkpoint in the data flow.

        Args:
            name: Checkpoint name (e.g., "step_2_start", "db_lookup", "mapping")
            revenue_multiple: Current value of revenue_multiple
            ev_ebitda_ratio: Current value of ev_ebitda_ratio
            context: Additional context data
            notes: Optional notes about this checkpoint
        """
        checkpoint = Checkpoint(
            name=name,
            timestamp=datetime.now(timezone.utc),
            revenue_multiple=revenue_multiple,
            ev_ebitda_ratio=ev_ebitda_ratio,
            context=context or {},
            notes=notes,
        )
        self.checkpoints.append(checkpoint)

    def get_trace(self) -> Dict[str, Any]:
        """
        Get the full trace as a dictionary.

        Returns:
            Dictionary with trace information including all checkpoints
        """
        return {
            "request_id": self.request_id,
            "start_time": self.start_time.isoformat(),
            "end_time": datetime.now(timezone.utc).isoformat(),
            "checkpoints": [
                {
                    "name": cp.name,
                    "timestamp": cp.timestamp.isoformat(),
                    "revenue_multiple": cp.revenue_multiple,
                    "ev_ebitda_ratio": cp.ev_ebitda_ratio,
                    "revenue_multiple_valid": cp.revenue_multiple is not None
                    and cp.revenue_multiple > 0,
                    "context": cp.context,
                    "notes": cp.notes,
                }
                for cp in self.checkpoints
            ],
            "summary": self._generate_summary(),
        }

    def _generate_summary(self) -> Dict[str, Any]:
        """Generate a summary of the trace"""
        if not self.checkpoints:
            return {"status": "no_checkpoints"}

        first = self.checkpoints[0]
        last = self.checkpoints[-1]

        # Find where revenue_multiple was lost (if it was)
        lost_at = None
        for i, cp in enumerate(self.checkpoints):
            if cp.revenue_multiple is None or cp.revenue_multiple <= 0:
                if i > 0:
                    prev = self.checkpoints[i - 1]
                    if prev.revenue_multiple is not None and prev.revenue_multiple > 0:
                        lost_at = cp.name
                        break

        return {
            "total_checkpoints": len(self.checkpoints),
            "first_revenue_multiple": first.revenue_multiple,
            "last_revenue_multiple": last.revenue_multiple,
            "revenue_multiple_lost_at": lost_at,
            "revenue_multiple_consistent": (
                all(
                    cp.revenue_multiple is not None
                    and cp.revenue_multiple == first.revenue_multiple
                    for cp in self.checkpoints
                )
                if first.revenue_multiple is not None
                else False
            ),
        }

    def to_json(self) -> str:
        """Serialize trace to JSON"""
        return json.dumps(self.get_trace(), default=str, indent=2)


_tracer_var: ContextVar[Optional[DataFlowTracer]] = ContextVar("data_flow_tracer", default=None)


def get_tracer(request_id: Optional[str] = None) -> DataFlowTracer:
    """
    Get or create a DataFlowTracer for the current request.

    Args:
        request_id: Optional request ID for correlation

    Returns:
        DataFlowTracer instance
    """
    tracer = _tracer_var.get()
    if tracer is None:
        tracer = DataFlowTracer(request_id=request_id)
        _tracer_var.set(tracer)
    return tracer


def set_tracer(tracer: DataFlowTracer):
    """Set the tracer for the current context"""
    _tracer_var.set(tracer)


def clear_tracer():
    """Clear the tracer for the current context"""
    _tracer_var.set(None)
