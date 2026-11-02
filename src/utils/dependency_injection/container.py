"""
Dependency Injection Container

A lightweight, type-safe dependency injection container implementing the service locator pattern
with support for singleton and transient service lifetimes.

Author: UpSwitch Engineering Team
Date: December 2025
Status: P0 Implementation
"""

import inspect
import logging
import threading
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Dict, Optional, Type, TypeVar, Union, get_type_hints

logger = logging.getLogger(__name__)

T = TypeVar("T")


class ServiceLifetime(Enum):
    """Service lifetime management options"""

    SINGLETON = "singleton"  # Single instance shared across all requests
    TRANSIENT = "transient"  # New instance created for each resolution
    SCOPED = "scoped"  # Single instance per scope (e.g., per request)


@dataclass
class ServiceDescriptor:
    """Descriptor for a registered service"""

    service_type: Type
    implementation: Optional[Union[Type, Callable]] = None
    factory: Optional[Callable[[], Any]] = None
    instance: Optional[Any] = None
    lifetime: ServiceLifetime = ServiceLifetime.TRANSIENT
    dependencies: Optional[Dict[str, Type]] = None

    def __post_init__(self):
        """Set implementation to service_type if not provided"""
        if self.implementation is None:
            self.implementation = self.service_type


class Container:
    """
    Dependency Injection Container

    Manages service registration and resolution with support for:
    - Singleton and transient lifetimes
    - Factory-based registration
    - Instance-based registration
    - Automatic dependency resolution
    - Type-safe service resolution

    Example:
        container = Container()
        container.register(WorkflowEngine, lifetime=ServiceLifetime.SINGLETON)
        container.register(ResultAggregator, lifetime=ServiceLifetime.SINGLETON)

        # Resolve with automatic dependency injection
        workflow_engine = container.resolve(WorkflowEngine)
    """

    def __init__(self):
        """Initialize the container"""
        self._services: Dict[Type, ServiceDescriptor] = {}
        self._singletons: Dict[Type, Any] = {}
        self._scoped_instances: Dict[Type, Any] = {}
        self._resolve_lock = threading.Lock()
        self.logger = logger

    def register(
        self,
        service_type: Type[T],
        implementation: Optional[Union[Type[T], Callable[[], T]]] = None,
        factory: Optional[Callable[[], T]] = None,
        instance: Optional[T] = None,
        lifetime: ServiceLifetime = ServiceLifetime.TRANSIENT,
    ) -> "Container":
        """
        Register a service with the container

        Args:
            service_type: The type/interface to register
            implementation: The concrete implementation class (defaults to service_type)
            factory: Factory function to create instances
            instance: Pre-created instance (for singleton)
            lifetime: Service lifetime (SINGLETON, TRANSIENT, or SCOPED)

        Returns:
            Self for method chaining

        Example:
            # Register a singleton
            container.register(WorkflowEngine, lifetime=ServiceLifetime.SINGLETON)

            # Register with factory
            container.register(
                DatabaseService,
                factory=lambda: DatabaseService(connection_string="..."),
                lifetime=ServiceLifetime.SINGLETON
            )

            # Register an instance
            container.register(
                ConfigService,
                instance=ConfigService(config_dict),
                lifetime=ServiceLifetime.SINGLETON
            )
        """
        if instance is not None:
            # Register pre-created instance
            self._services[service_type] = ServiceDescriptor(
                service_type=service_type,
                instance=instance,
                lifetime=ServiceLifetime.SINGLETON,
            )
            self._singletons[service_type] = instance
            self.logger.debug(f"Registered instance: {service_type.__name__}")
        elif factory is not None:
            # Register factory function
            self._services[service_type] = ServiceDescriptor(
                service_type=service_type,
                factory=factory,
                lifetime=lifetime,
            )
            self.logger.debug(f"Registered factory: {service_type.__name__}")
        else:
            # Register type
            impl = implementation or service_type
            dependencies = self._extract_dependencies(impl)
            self._services[service_type] = ServiceDescriptor(
                service_type=service_type,
                implementation=impl,
                lifetime=lifetime,
                dependencies=dependencies,
            )
            self.logger.debug(
                f"Registered type: {service_type.__name__} -> {impl.__name__} "
                f"(lifetime: {lifetime.value})"
            )

        return self

    def register_singleton(
        self,
        service_type: Type[T],
        implementation: Optional[Union[Type[T], Callable[[], T]]] = None,
        factory: Optional[Callable[[], T]] = None,
        instance: Optional[T] = None,
    ) -> "Container":
        """Convenience method to register a singleton"""
        return self.register(
            service_type=service_type,
            implementation=implementation,
            factory=factory,
            instance=instance,
            lifetime=ServiceLifetime.SINGLETON,
        )

    def register_transient(
        self,
        service_type: Type[T],
        implementation: Optional[Union[Type[T], Callable[[], T]]] = None,
        factory: Optional[Callable[[], T]] = None,
    ) -> "Container":
        """Convenience method to register a transient service"""
        return self.register(
            service_type=service_type,
            implementation=implementation,
            factory=factory,
            lifetime=ServiceLifetime.TRANSIENT,
        )

    def resolve(self, service_type: Type[T]) -> T:
        """
        Resolve a service instance

        Args:
            service_type: The type to resolve

        Returns:
            Instance of the requested type

        Raises:
            ValueError: If service is not registered

        Example:
            workflow_engine = container.resolve(WorkflowEngine)
        """
        if service_type not in self._services:
            raise ValueError(
                f"Service {service_type.__name__} is not registered. "
                f"Register it using container.register({service_type.__name__})"
            )

        descriptor = self._services[service_type]

        if descriptor.lifetime == ServiceLifetime.SINGLETON:
            if service_type in self._singletons:
                return self._singletons[service_type]
            with self._resolve_lock:
                if service_type in self._singletons:
                    return self._singletons[service_type]
                instance = self._create_instance(descriptor)
                self._singletons[service_type] = instance
                return instance

        return self._create_instance(descriptor)

    def try_resolve(self, service_type: Type[T]) -> Optional[T]:
        """
        Try to resolve a service, returning None if not registered

        Args:
            service_type: The type to resolve

        Returns:
            Instance of the requested type, or None if not registered
        """
        try:
            return self.resolve(service_type)
        except ValueError:
            return None

    def is_registered(self, service_type: Type) -> bool:
        """Check if a service is registered"""
        return service_type in self._services

    def _extract_dependencies(self, implementation: Type) -> Dict[str, Type]:
        """Extract constructor dependencies from type hints"""
        dependencies = {}
        try:
            if hasattr(implementation, "__init__"):
                sig = inspect.signature(implementation.__init__)
                hints = get_type_hints(implementation.__init__)
                for param_name, param in sig.parameters.items():
                    if param_name == "self":
                        continue
                    if param_name in hints:
                        dependencies[param_name] = hints[param_name]
        except (TypeError, AttributeError, ValueError) as e:
            self.logger.debug(f"Could not extract dependencies for {implementation.__name__}: {e}")
        return dependencies

    def _create_instance(self, descriptor: ServiceDescriptor) -> Any:
        """Create an instance of the service"""
        # Use pre-created instance if available
        if descriptor.instance is not None:
            return descriptor.instance

        # Use factory if available
        if descriptor.factory is not None:
            return descriptor.factory()

        # Create from implementation class
        implementation = descriptor.implementation
        if implementation is None:
            raise ValueError(f"No implementation specified for {descriptor.service_type.__name__}")

        # Resolve constructor dependencies
        constructor_args = {}
        if descriptor.dependencies:
            for param_name, param_type in descriptor.dependencies.items():
                if self.is_registered(param_type):
                    constructor_args[param_name] = self.resolve(param_type)
                else:
                    self.logger.debug(
                        f"Dependency {param_type.__name__} not registered, "
                        f"will use default value for {param_name}"
                    )

        # Create instance
        try:
            if constructor_args:
                return implementation(**constructor_args)
            else:
                return implementation()
        except TypeError as e:
            # If constructor injection fails, try without args
            self.logger.debug(
                f"Constructor injection failed for {implementation.__name__}, "
                f"trying without args: {e}"
            )
            return implementation()

    def create_scope(self) -> "ServiceScope":
        """Create a new service scope for scoped lifetime services"""
        return ServiceScope(self)

    def clear(self):
        """Clear all registered services (useful for testing)"""
        self._services.clear()
        self._singletons.clear()
        self._scoped_instances.clear()


class ServiceScope:
    """Represents a service scope for scoped lifetime services"""

    def __init__(self, container: Container):
        self.container = container
        self._scoped_instances: Dict[Type, Any] = {}

    def resolve(self, service_type: Type[T]) -> T:
        """Resolve a service within this scope"""
        descriptor = self.container._services.get(service_type)
        if descriptor is None:
            raise ValueError(f"Service {service_type.__name__} is not registered")

        if descriptor.lifetime == ServiceLifetime.SCOPED:
            if service_type not in self._scoped_instances:
                self._scoped_instances[service_type] = self.container._create_instance(descriptor)
            return self._scoped_instances[service_type]
        else:
            return self.container.resolve(service_type)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._scoped_instances.clear()


_global_container: Optional[Container] = None
_global_container_lock = threading.Lock()


def get_container() -> Container:
    """Get or create the global container instance. Thread-safe."""
    global _global_container
    if _global_container is None:
        with _global_container_lock:
            if _global_container is None:
                _global_container = Container()
    return _global_container


def reset_container():
    """Reset the global container (useful for testing)"""
    global _global_container
    _global_container = None
