"""
Step 7 EV to Equity Modules

Specialized modules for Step 7 EV to equity conversion.
"""

# This __init__.py makes step_7_ev_to_equity a package
# The main Step7EVToEquity class is in step_7_ev_to_equity.py (parent directory)

from .._lazy_step_loader import load_step_class


# Import Step7EVToEquity from the parent file
def __getattr__(name: str) -> object:
    if name == "Step7EVToEquity":
        return load_step_class(__file__, "step_7_ev_to_equity.py", "Step7EVToEquity", "_step_file")
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__: list[str] = []
