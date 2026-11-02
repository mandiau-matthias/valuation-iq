"""
Component Registry

Registry system for managing and discovering template components.
"""

from typing import Dict, Type, List, Optional, Any
import logging

from .base import ComponentBase

logger = logging.getLogger(__name__)


class ComponentRegistry:
    """Registry for all available components"""

    def __init__(self):
        self._components: Dict[str, Type[ComponentBase]] = {}
        self._metadata: Dict[str, Dict[str, Any]] = {}
        self.logger = logging.getLogger(f"{__name__}.ComponentRegistry")

    def register(self, name: str, component_class: Type[ComponentBase], metadata: Optional[Dict[str, Any]] = None):
        """Register a component"""
        if not issubclass(component_class, ComponentBase):
            raise ValueError(f"Component {name} must inherit from ComponentBase")

        self._components[name] = component_class
        self._metadata[name] = metadata or {}

        self.logger.info(f"Registered component: {name}")

    def get(self, name: str) -> Type[ComponentBase]:
        """Get component class by name"""
        if name not in self._components:
            available = ", ".join(self._components.keys())
            raise ValueError(f"Component not found: {name}. Available: {available}")
        return self._components[name]

    def get_instance(self, name: str, config=None) -> ComponentBase:
        """Get component instance"""
        component_class = self.get(name)
        return component_class(config)

    def list_components(self) -> List[str]:
        """List all registered components"""
        return list(self._components.keys())

    def get_metadata(self, name: str) -> Dict[str, Any]:
        """Get component metadata"""
        return self._metadata.get(name, {})

    def is_registered(self, name: str) -> bool:
        """Check if component is registered"""
        return name in self._components

    def unregister(self, name: str):
        """Unregister a component"""
        if name in self._components:
            del self._components[name]
            del self._metadata[name]
            self.logger.info(f"Unregistered component: {name}")

    def clear(self):
        """Clear all components"""
        self._components.clear()
        self._metadata.clear()
        self.logger.info("Cleared all components")

    def get_stats(self) -> Dict[str, Any]:
        """Get registry statistics"""
        return {
            "total_components": len(self._components),
            "component_names": list(self._components.keys()),
            "metadata_keys": list(self._metadata.keys())
        }


# Global registry instance
_registry = ComponentRegistry()


def register_component(name: str, metadata: Optional[Dict[str, Any]] = None):
    """Decorator to register components"""
    def decorator(cls):
        _registry.register(name, cls, metadata)
        return cls
    return decorator


def get_component(name: str) -> Type[ComponentBase]:
    """Get component from registry"""
    return _registry.get(name)


def get_component_instance(name: str, config=None) -> ComponentBase:
    """Get component instance from registry"""
    return _registry.get_instance(name, config)


def list_components() -> List[str]:
    """List all registered components"""
    return _registry.list_components()


def get_registry() -> ComponentRegistry:
    """Get the global registry instance"""
    return _registry
