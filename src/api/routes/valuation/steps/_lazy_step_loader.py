"""Typed helpers for legacy valuation-step package shims."""

from __future__ import annotations

import importlib.util
import hashlib
import sys
from pathlib import Path
from threading import RLock

_STEPS_PACKAGE = "src.api.routes.valuation.steps"
_load_lock = RLock()
_loaded_classes: dict[tuple[str, str], object] = {}


def load_step_class(
    package_file: str,
    step_filename: str,
    class_name: str,
    module_name: str,
) -> object:
    """Load a legacy step class from the sibling module file."""
    step_file = (Path(package_file).parent.parent / step_filename).resolve()
    cache_key = (str(step_file), class_name)

    with _load_lock:
        cached = _loaded_classes.get(cache_key)
        if cached is not None:
            return cached

        if not step_file.exists():
            raise ImportError(f"Cannot find {step_filename}")

        path_digest = hashlib.sha1(
            str(step_file).encode("utf-8"),
            usedforsecurity=False,
        ).hexdigest()[:12]
        qualified_module_name = (
            f"{_STEPS_PACKAGE}._legacy_{step_file.stem}_{module_name}_{path_digest}"
        )
        mod = sys.modules.get(qualified_module_name)
        if mod is None:
            spec = importlib.util.spec_from_file_location(qualified_module_name, step_file)
            if spec is None or spec.loader is None:
                raise ImportError(f"Cannot load {class_name} from {step_file}")

            mod = importlib.util.module_from_spec(spec)
            mod.__package__ = _STEPS_PACKAGE
            sys.modules[qualified_module_name] = mod
            try:
                spec.loader.exec_module(mod)
            except Exception:
                sys.modules.pop(qualified_module_name, None)
                raise

        value: object = getattr(mod, class_name)
        _loaded_classes[cache_key] = value
        return value
