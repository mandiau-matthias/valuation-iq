from src.utils.exceptions import APIError, DataValidationError

"""
Component Base Classes

Base classes for all template components with caching, configuration,
and rendering capabilities.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from dataclasses import dataclass
import hashlib
import logging
from src.utils.core import format_currency, format_percent, format_number
from decimal import Decimal
from src.utils.decimal_helpers import to_decimal, from_decimal

logger = logging.getLogger(__name__)


@dataclass
class ComponentConfig:
    """Configuration for component rendering"""

    cache_enabled: bool = True
    cache_ttl: int = 3600  # 1 hour
    minify: bool = True
    async_render: bool = True
    preserve_formatting: bool = False  # For debugging


class ComponentBase(ABC):
    """Base class for all template components"""

    def __init__(self, config: Optional[ComponentConfig] = None):
        self.config = config or ComponentConfig()
        self.cache_key_prefix = self.__class__.__name__
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    @abstractmethod
    async def render(self, data: Dict[str, Any]) -> str:
        """Render component to HTML"""
        pass

    def get_cache_key(self, data: Dict[str, Any]) -> str:
        """Generate cache key for component"""
        # Create deterministic hash of data
        data_str = str(sorted(data.items()))
        hash_str = hashlib.md5(data_str.encode(), usedforsecurity=False).hexdigest()
        return f"{self.cache_key_prefix}:{hash_str}"

    async def render_cached(self, data: Dict[str, Any], cache_service) -> str:
        """Render with caching"""
        if not self.config.cache_enabled:
            return await self.render(data)

        cache_key = self.get_cache_key(data)

        try:
            cached = await cache_service.get(cache_key)
            if cached:
                self.logger.debug(f"Cache hit for {self.cache_key_prefix}")
                return cached
        except APIError as e:
            self.logger.warning(f"Cache get failed: {e}")

        # Cache miss - render component
        try:
            html = await self.render(data)

            # Store in cache
            try:
                await cache_service.set(cache_key, html, ttl=self.config.cache_ttl)
                self.logger.debug(f"Cached {self.cache_key_prefix}")
            except DataValidationError as e:
                self.logger.warning(f"Cache set failed: {e}")

            return html

        except DataValidationError as e:
            self.logger.error(f"Component render failed: {e}")
            raise

    def validate_data(self, data: Dict[str, Any], required_fields: list[str]) -> bool:
        """Validate required fields in data"""
        missing_fields = [field for field in required_fields if field not in data]
        if missing_fields:
            raise ValueError(f"Missing required fields: {missing_fields}")
        return True

    def get_safe_value(self, data: Dict[str, Any], key: str, default: Any = "") -> Any:
        """Safely get value from data with default"""
        return data.get(key, default)

    def format_currency(self, value: Decimal, currency: str = "USD") -> str:
        """
        Format currency value using unified utility.

        Delegates to src.utils.core.format_currency for consistency.
        """
        return format_currency(value, currency=currency, precision=2)

    def format_percentage(self, value: Decimal, decimals: int = 1) -> str:
        """
        Format percentage value using unified utility.

        Delegates to src.utils.core.format_percent for consistency.
        """
        return format_percent(value, precision=decimals, include_sign=False)

    def format_number(self, value: Decimal, decimals: int = 0) -> str:
        """
        Format number with thousand separators using unified utility.

        Delegates to src.utils.core.format_number for consistency.
        """
        return format_number(value, precision=decimals, use_thousands_separator=True)

    def escape_html(self, text: str) -> str:
        """Escape HTML special characters"""
        if not isinstance(text, str):
            text = str(text)

        html_escape_table = {
            "&": "&amp;",
            '"': "&quot;",
            "'": "&#x27;",
            ">": "&gt;",
            "<": "&lt;",
        }

        return "".join(html_escape_table.get(c, c) for c in text)

    def get_trend_class(self, change: Decimal) -> str:
        """Get CSS class for trend direction"""
        if change > 0:
            return "text-green-600"
        elif change < 0:
            return "text-red-600"
        else:
            return "text-gray-600"

    def get_trend_icon(self, change: Decimal) -> str:
        """Get icon for trend direction"""
        if change > 0:
            return "↑"
        elif change < 0:
            return "↓"
        else:
            return "→"

    def get_trend_color(self, change: Decimal) -> str:
        """Get color for trend direction"""
        if change > 0:
            return "green"
        elif change < 0:
            return "red"
        else:
            return "gray"
