"""
Dependency Injection Framework

Provides a lightweight, type-safe dependency injection container for the UpSwitch Valuation Engine.

Features:
- Service registration and resolution
- Singleton and transient lifecycle management
- Factory pattern support
- Type-safe dependency resolution
- Lazy initialization support
- Service provider pattern

Usage:
    Use Container and ServiceLifetime to register services (singleton or transient) and resolve
    concrete implementations by type (for example WorkflowEngine, ResultAggregator).
"""

from .container import Container, ServiceDescriptor, ServiceLifetime
from .decorators import inject, singleton, transient
from .service_provider import ServiceProvider

__all__ = [
    "Container",
    "ServiceLifetime",
    "ServiceDescriptor",
    "ServiceProvider",
    "inject",
    "singleton",
    "transient",
]
