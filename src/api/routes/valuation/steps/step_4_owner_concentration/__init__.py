"""
Step 4 Owner Concentration Modules

Specialized modules for Step 4 owner concentration discount calculation.
"""

# This __init__.py makes step_4_owner_concentration a package
# The main Step4OwnerConcentration class is in step_4_owner_concentration.py (parent directory)

from .._lazy_step_loader import load_step_class


# Import Step4OwnerConcentration from the parent file
def __getattr__(name: str) -> object:
    if name == "Step4OwnerConcentration":
        return load_step_class(
            __file__, "step_4_owner_concentration.py", "Step4OwnerConcentration", "_step_file"
        )
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__: list[str] = []
