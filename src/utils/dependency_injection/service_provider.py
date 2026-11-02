"""
Service Provider Interface

Defines the service provider protocol for dependency resolution.
"""

from typing import Optional, Protocol, Type, TypeVar

T = TypeVar("T")


class ServiceProvider(Protocol):
    """Protocol for service providers that can resolve dependencies"""

    def resolve(self, service_type: Type[T]) -> T:
        """Resolve a service instance"""
        ...

    def try_resolve(self, service_type: Type[T]) -> Optional[T]:
        """Try to resolve a service, returning None if not registered"""
        ...

    def is_registered(self, service_type: Type) -> bool:
        """Check if a service is registered"""
        ...
