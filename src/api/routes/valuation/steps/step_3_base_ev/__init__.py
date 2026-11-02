"""
Step 3 Base EV Modules

Specialized modules for Step 3 base enterprise value calculation.
"""

# This __init__.py makes step_3_base_ev a package
# The main Step3BaseEV class is in step_3_base_ev.py (parent directory)

from .._lazy_step_loader import load_step_class


# Import Step3BaseEV from the parent file
def __getattr__(name: str) -> object:
    if name == "Step3BaseEV":
        return load_step_class(__file__, "step_3_base_ev.py", "Step3BaseEV", "_step_3_file")
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__: list[str] = []
