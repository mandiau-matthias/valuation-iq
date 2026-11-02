"""
Step 10 Range Methodology Modules

Specialized modules for Step 10 range methodology calculation.
"""

# This __init__.py makes step_10_range_methodology a package
# The main Step10RangeMethodology class is in step_10_range_methodology.py (parent directory)

from .._lazy_step_loader import load_step_class


# Import Step10RangeMethodology from the parent file
def __getattr__(name: str) -> object:
    if name == "Step10RangeMethodology":
        return load_step_class(
            __file__, "step_10_range_methodology.py", "Step10RangeMethodology", "_step_file"
        )
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__: list[str] = []
