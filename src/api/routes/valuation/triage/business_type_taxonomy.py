"""Compatibility facade for domain-owned business-type taxonomy."""

from src.domain import business_type_taxonomy as _taxonomy

__all__ = list(_taxonomy.__all__)

globals().update({name: getattr(_taxonomy, name) for name in __all__})
