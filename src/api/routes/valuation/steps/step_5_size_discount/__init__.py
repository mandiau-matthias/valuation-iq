"""
Step 5 Size Discount Modules

Specialized modules for Step 5 size discount calculation.
"""

# This __init__.py makes step_5_size_discount a package
# The main Step5SizeDiscount class is in step_5_size_discount.py (parent directory)

from .._lazy_step_loader import load_step_class


# Import Step5SizeDiscount from the parent file
def __getattr__(name: str) -> object:
    if name == "Step5SizeDiscount":
        return load_step_class(
            __file__, "step_5_size_discount.py", "Step5SizeDiscount", "_step_file"
        )
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__: list[str] = []
