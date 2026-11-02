"""
Step 0 Data Quality — package shim.

This package exists only because Python cannot resolve both ``step_0_data_quality.py``
(module) and ``step_0_data_quality/`` (package) at the same level: the package wins.
To keep the historical import path ``from ...steps.step_0_data_quality import Step0DataQuality``
working, this ``__init__.py`` lazy-loads the sibling ``.py`` file via PEP 562
``__getattr__`` and caches the resolved class on this module so subsequent
attribute lookups bypass the file load entirely.

The canonical implementation modules (executors, handlers, utils, validators)
live under ``step_0_modules/`` — this shim does NOT re-export them. If you need
``QualityAssessmentExecutor``, ``RequestValidator``, etc., import directly from
``src.api.routes.valuation.steps.step_0_modules.<subpackage>.<module>``.
"""

import importlib.util
import sys
from pathlib import Path

__all__ = ["Step0DataQuality"]


# Step0DataQuality lives in step_0_data_quality.py (parent directory).
# Lazy-import via PEP 562 __getattr__ to break the package/module name clash.
def __getattr__(name: str):
    if name != "Step0DataQuality":
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    step_0_file = Path(__file__).resolve().parent.parent / "step_0_data_quality.py"
    if not step_0_file.exists():
        raise ImportError(f"Cannot find {step_0_file}")

    # Stable module name keyed on the resolved path string, so concurrent
    # imports across test sessions/threads share a single execution and Python's
    # sys.modules cache is honoured on subsequent lookups.
    module_key = f"_step_0_file_{step_0_file.as_posix()}"
    mod = sys.modules.get(module_key)
    if mod is None:
        spec = importlib.util.spec_from_file_location(module_key, step_0_file)
        if spec is None or spec.loader is None:
            raise ImportError(f"Cannot load spec for {step_0_file}")
        mod = importlib.util.module_from_spec(spec)
        mod.__package__ = "src.api.routes.valuation.steps"
        sys.modules[module_key] = mod
        spec.loader.exec_module(mod)

    cls = mod.Step0DataQuality
    # Cache on the shim module so PEP 562 lookup short-circuits next time.
    globals()["Step0DataQuality"] = cls
    return cls
