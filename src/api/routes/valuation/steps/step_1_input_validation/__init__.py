"""
Step 1 Input Validation Modules

Specialized modules for Step 1 input validation and normalization.
"""

# This __init__.py makes step_1_input_validation a package
# The main Step1InputValidation class is in step_1_input_validation.py (parent directory)

from .._lazy_step_loader import load_step_class


# Import Step1InputValidation from the parent file
def __getattr__(name: str) -> object:
    if name == "Step1InputValidation":
        return load_step_class(
            __file__, "step_1_input_validation.py", "Step1InputValidation", "_step_1_file"
        )
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__: list[str] = []
