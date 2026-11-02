"""
Dependency Injection Decorators

Decorators for marking classes with their lifetime and auto-registration.
"""

from typing import Type, TypeVar

from .container import Container, ServiceLifetime, get_container

T = TypeVar("T")


def singleton(service_type: Type[T] = None) -> Type[T]:
    """
    Decorator to mark a class as a singleton service

    Usage:
        @singleton
        class WorkflowEngine:
            ...

        # Or with explicit type:
        @singleton(WorkflowEngine)
        class WorkflowEngine:
            ...
    """

    def decorator(cls: Type[T]) -> Type[T]:
        container = get_container()
        container.register_singleton(cls, cls)
        return cls

    if service_type is None:
        return decorator
    else:
        return decorator(service_type)


def transient(service_type: Type[T] = None) -> Type[T]:
    """
    Decorator to mark a class as a transient service

    Usage:
        @transient
        class RequestHandler:
            ...
    """

    def decorator(cls: Type[T]) -> Type[T]:
        container = get_container()
        container.register_transient(cls, cls)
        return cls

    if service_type is None:
        return decorator
    else:
        return decorator(service_type)


def inject(service_type: Type[T]):
    """
    Decorator to inject dependencies into a function or method

    Usage:
        @inject(WorkflowEngine)
        def my_function(workflow_engine: WorkflowEngine):
            ...
    """

    def decorator(func):
        # This is a placeholder - actual injection would happen at call time
        # For now, we'll use the container.resolve() pattern
        return func

    return decorator
