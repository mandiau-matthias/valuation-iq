"""
Repository Protocol

Protocol definition for repository interfaces.
This allows domain layer to use repositories without
depending on database layer implementations.
"""

from typing import Protocol, Optional, Dict, Any
from decimal import Decimal
from uuid import UUID


class BusinessTypesRepositoryProtocol(Protocol):
    """Protocol for business types repository."""
    
    async def get_business_type_by_id(
        self,
        business_type_id: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Get business type by ID.
        
        Args:
            business_type_id: Business type ID (UUID string)
            
        Returns:
            Business type data or None
        """
        ...
    
    async def get_hybrid_weights(
        self,
        business_type_id: str,
    ) -> Optional[Dict[str, Decimal]]:
        """
        Get hybrid weights for business type.

        Args:
            business_type_id: Business type ID

        Returns:
            Dictionary with 'dcf' and 'multiples' weights or None
        """
        ...

    async def get_method_weights(
        self,
        business_type_id: str,
    ) -> Optional[Dict[str, Decimal]]:
        """Full 4-axis method-weight blend, renormalised across non-NULL axes.

        Optional protocol method — added with the 20260502 migration
        that introduced ``asset_preference`` and ``re_yield_preference``
        on the business_types table. Implementations that haven't been
        upgraded may still return ``None`` for every business type and
        the caller will fall back to ``get_hybrid_weights`` as before.

        Returns:
            Dict with any subset of ``{"dcf", "multiples", "asset", "re_yield"}``
            summing to 1.0, or ``None`` when no preference is seeded.
        """
        ...

