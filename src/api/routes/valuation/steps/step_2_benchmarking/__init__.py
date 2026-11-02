"""
Step 2: Industry Benchmarking & Multiple Selection

Refactored modular structure for industry benchmarking and multiple selection.

This module provides the main Step2Benchmarking class that orchestrates
specialized collectors, calculators, analyzers, and validators.
"""

from .._lazy_step_loader import load_step_class


# Import Step2Benchmarking from the parent file
def __getattr__(name: str) -> object:
    if name == "Step2Benchmarking":
        return load_step_class(
            __file__, "step_2_benchmarking.py", "Step2Benchmarking", "_step_2_file"
        )
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__: list[str] = ["Step2Benchmarking"]
