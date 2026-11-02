"""
Step 8 Ownership Adjustment Modules

Specialized modules for Step 8 ownership adjustment calculation.
"""

# This __init__.py makes step_8_ownership_adjustment a package
# The main Step8OwnershipAdjustment class is in step_8_ownership_adjustment.py (parent directory)

from .._lazy_step_loader import load_step_class


# Import Step8OwnershipAdjustment from the parent file
def __getattr__(name: str) -> object:
    if name == "Step8OwnershipAdjustment":
        return load_step_class(
            __file__,
            "step_8_ownership_adjustment.py",
            "Step8OwnershipAdjustment",
            "_step_file",
        )
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__: list[str] = []
