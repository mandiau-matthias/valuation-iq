"""
Template Components Package

Component-based template rendering system for Upswitch Valuation Engine.
Provides reusable, cacheable, and composable HTML components.
"""

from .base import ComponentBase, ComponentConfig
from .registry import ComponentRegistry, register_component, get_component, get_registry
from .cache import TemplateCacheService
from .minification import MinificationService

__all__ = [
    "ComponentBase",
    "ComponentConfig", 
    "ComponentRegistry",
    "register_component",
    "get_component",
    "get_registry",
    "TemplateCacheService",
    "MinificationService"
]
