"""
Domain models package for owner dependency.

This package contains specialized models that were extracted from the main models.py
to avoid circular dependencies and improve modularity.
"""

from .owner_dependency import DependencyLevel, OwnerDependencyFactors, OwnerDependencyResult

__all__ = [
    # Owner Dependency Models
    "DependencyLevel",
    "OwnerDependencyFactors",
    "OwnerDependencyResult",
]
