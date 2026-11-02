"""
Step 9 Confidence Score Modules

Specialized modules for Step 9 confidence score calculation.
"""

# This __init__.py makes step_9_confidence_score a package
# The main Step9ConfidenceScore class is in step_9_confidence_score.py (parent directory)

from .._lazy_step_loader import load_step_class


# Import Step9ConfidenceScore from the parent file
def __getattr__(name: str) -> object:
    if name == "Step9ConfidenceScore":
        return load_step_class(
            __file__, "step_9_confidence_score.py", "Step9ConfidenceScore", "_step_file"
        )
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__: list[str] = []
