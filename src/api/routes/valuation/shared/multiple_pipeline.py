"""
Multiple Discount Pipeline Tracker

Tracks how the valuation multiple cascades through each discount stage,
providing complete transparency from initial multiple to final adjusted multiple.

This module implements the "Multiple-First Discounting" feature where all
adjustments (owner concentration, size, liquidity, ownership) are applied to
the multiple itself, not just the final Enterprise Value.
"""

from dataclasses import dataclass, field
from decimal import Decimal
from typing import List, Optional

from src.utils.decimal_helpers import from_decimal, to_decimal


@dataclass
class MultiplePipelineStage:
    """
    Single stage in the multiple discount pipeline.

    Represents one discount adjustment showing how the multiple changes
    from 'multiple_before' to 'multiple_after'.

    Example:
        Step 4 (Owner Concentration): 10.0x → 8.0x (-20%)
    """

    step_number: int
    step_name: str
    discount_type: str  # 'owner_concentration', 'size', 'liquidity', 'ownership'
    discount_percentage: Decimal  # e.g., -Decimal('20.0') for 20% discount
    multiple_before: Decimal  # e.g., Decimal('10.0')
    multiple_after: Decimal  # e.g., Decimal('8.0')
    metric_value: Decimal  # EBITDA or Revenue value used
    ev_before: Decimal  # EV before this discount
    ev_after: Decimal  # EV after this discount
    explanation: str  # Human-readable reason for discount

    def to_dict(self) -> dict:
        """Convert stage to dictionary for API response."""
        return {
            "step_number": self.step_number,
            "step_name": self.step_name,
            "discount_type": self.discount_type,
            "discount_percentage": self.discount_percentage,
            "multiple_before": self.multiple_before,
            "multiple_after": self.multiple_after,
            "metric_value": self.metric_value,
            "ev_before": self.ev_before,
            "ev_after": self.ev_after,
            "explanation": self.explanation,
        }


@dataclass
class MultiplePipeline:
    """
    Complete multiple discount pipeline from initial to final adjusted multiple.

    Tracks the full cascade of discounts showing how the multiple progresses
    through each step: 10x → 8x → 7.2x → 6.48x

    Attributes:
        initial_multiple: Starting multiple from Step 3 (e.g., 10.0x)
        final_multiple: Final adjusted multiple after all discounts (e.g., 6.48x)
        total_reduction_percentage: Cumulative reduction % (e.g., -35.2%)
        metric_type: 'EBITDA' or 'Revenue'
        metric_value: Metric value used for calculations
        stages: List of all discount stages (Steps 4-8)

    Example:
        Initial Multiple: 10x
        Stage 1 (Owner Concentration -20%): 10x → 8x
        Stage 2 (Size Discount -10%): 8x → 7.2x
        Stage 3 (Liquidity -10%): 7.2x → 6.48x
        Final Multiple: 6.48x (-35.2% total reduction)
    """

    initial_multiple: Decimal
    final_multiple: Decimal
    total_reduction_percentage: Decimal
    metric_type: str  # 'EBITDA' or 'Revenue'
    metric_value: Decimal
    stages: List[MultiplePipelineStage] = field(default_factory=list)

    def add_stage(self, stage: MultiplePipelineStage) -> None:
        """
        Add a new discount stage to the pipeline.

        Args:
            stage: MultiplePipelineStage to add
        """
        self.stages.append(stage)

    def get_stage(self, step_number: int) -> Optional[MultiplePipelineStage]:
        """
        Get a specific stage by step number.

        Args:
            step_number: Step number to retrieve (e.g., 4 for owner concentration)

        Returns:
            MultiplePipelineStage if found, None otherwise
        """
        return next((s for s in self.stages if s.step_number == step_number), None)

    def get_stage_count(self) -> int:
        """Get the number of discount stages in the pipeline."""
        return len(self.stages)

    def has_discounts(self) -> bool:
        """Check if any discounts were applied (stages exist)."""
        return len(self.stages) > 0

    def to_dict(self) -> dict:
        """
        Convert pipeline to dictionary for API response.

        Returns:
            Dictionary representation suitable for JSON serialization
        """
        return {
            "initial_multiple": self.initial_multiple,
            "final_multiple": self.final_multiple,
            "total_reduction_percentage": self.total_reduction_percentage,
            "metric_type": self.metric_type,
            "metric_value": self.metric_value,
            "stages": [stage.to_dict() for stage in self.stages],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "MultiplePipeline":
        """
        Create MultiplePipeline from dictionary.

        Args:
            data: Dictionary with pipeline data

        Returns:
            MultiplePipeline instance
        """
        stages = [
            MultiplePipelineStage(
                step_number=s["step_number"],
                step_name=s["step_name"],
                discount_type=s["discount_type"],
                discount_percentage=s["discount_percentage"],
                multiple_before=s["multiple_before"],
                multiple_after=s["multiple_after"],
                metric_value=s["metric_value"],
                ev_before=s["ev_before"],
                ev_after=s["ev_after"],
                explanation=s["explanation"],
            )
            for s in data.get("stages", [])
        ]

        return cls(
            initial_multiple=data["initial_multiple"],
            final_multiple=data["final_multiple"],
            total_reduction_percentage=data["total_reduction_percentage"],
            metric_type=data["metric_type"],
            metric_value=data["metric_value"],
            stages=stages,
        )


def create_pipeline_stage(
    step_number: int,
    step_name: str,
    discount_type: str,
    discount_percentage: Decimal,
    multiple_before: Decimal,
    multiple_after: Decimal,
    metric_value: Decimal,
    explanation: str,
) -> MultiplePipelineStage:
    """
    Factory function to create a pipeline stage.

    Args:
        step_number: Step number (4-8)
        step_name: Human-readable step name
        discount_type: Type of discount
        discount_percentage: Discount as percentage (negative for discount)
        multiple_before: Multiple before discount
        multiple_after: Multiple after discount
        metric_value: EBITDA or Revenue value
        explanation: Human-readable explanation

    Returns:
        MultiplePipelineStage instance
    """
    ev_before = metric_value * multiple_before
    ev_after = metric_value * multiple_after

    return MultiplePipelineStage(
        step_number=step_number,
        step_name=step_name,
        discount_type=discount_type,
        discount_percentage=discount_percentage,
        multiple_before=multiple_before,
        multiple_after=multiple_after,
        metric_value=metric_value,
        ev_before=ev_before,
        ev_after=ev_after,
        explanation=explanation,
    )


def calculate_total_reduction(initial_multiple: Decimal, final_multiple: Decimal) -> Decimal:
    """
    Calculate total reduction percentage from initial to final multiple.

    Args:
        initial_multiple: Starting multiple (e.g., Decimal('10.0'))
        final_multiple: Ending multiple (e.g., Decimal('6.48'))

    Returns:
        Reduction percentage (e.g., -Decimal('35.2') for 35.2% reduction)

    Example:
        >>> calculate_total_reduction(Decimal('10.0'), Decimal('6.48'))
        -Decimal('35.2')
    """
    if initial_multiple == 0:
        return Decimal("0.0")

    return ((final_multiple - initial_multiple) / initial_multiple) * Decimal("100.0")
