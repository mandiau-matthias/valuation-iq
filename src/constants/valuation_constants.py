"""
Compatibility facade for valuation constants.

The canonical implementation lives in ``src.config.valuation_constants``.
Keep this module so legacy imports continue to work without carrying a second
copy of methodology constants.
"""

from src.config import valuation_constants as _canonical

__all__ = list(_canonical.__all__)

globals().update({name: getattr(_canonical, name) for name in __all__})
