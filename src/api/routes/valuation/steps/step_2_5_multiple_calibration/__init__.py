"""
Step 2.5: Multiple Calibration

MULTIPLE-FIRST METHODOLOGY:
Adjusts comparables-derived base multiple for subject company quality factors.
All adjustments to the multiple, not EBITDA, preventing double-counting.
"""

from .._lazy_step_loader import load_step_class

# NOTE: The Step25MultipleCalibration class is defined in ../step_2_5_multiple_calibration.py
# This directory contains supporting modules (calculators, orchestrators, etc.)


# Export the step class from the parent file to avoid import conflicts
# Similar pattern to step_0_data_quality
def __getattr__(name: str) -> object:
    """Lazy load Step25MultipleCalibration to avoid circular imports."""
    if name == "Step25MultipleCalibration":
        return load_step_class(
            __file__,
            "step_2_5_multiple_calibration.py",
            "Step25MultipleCalibration",
            "_step_2_5_file",
        )

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__: list[str] = ["Step25MultipleCalibration"]
