"""
Step 11 Final Synthesis Modules

Specialized modules for Step 11 final synthesis calculation.
"""

# This __init__.py makes step_11_final_synthesis a package
# The main Step11FinalSynthesis class is in step_11_final_synthesis.py (parent directory)

from .._lazy_step_loader import load_step_class


# Import Step11FinalSynthesis from the parent file
def __getattr__(name: str) -> object:
    if name == "Step11FinalSynthesis":
        return load_step_class(
            __file__, "step_11_final_synthesis.py", "Step11FinalSynthesis", "_step_file"
        )
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__: list[str] = []
