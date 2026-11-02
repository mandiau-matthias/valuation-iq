"""
Base adapter class for external data sources

Provides common functionality for all external API adapters including:
- Retry logic with exponential backoff
- Error handling and logging
- Response caching
- Rate limiting
- Request/response validation
"""

import asyncio
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Union
from datetime import datetime, timedelta
import hashlib
import json

import aiohttp
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)
from src.utils.logging import get_logger, log_calculation_step, log_validation_step
from src.utils.logging_context import get_current_context

from src.config import get_settings

logger = get_logger(__name__)
settings = get_settings()


class APIError(Exception):
    """Base exception for API errors"""
    pass


class RateLimitError(APIError):
    """Rate limit exceeded"""
    pass


class DataNotFoundError(APIError):
    """Requested data not found"""
    pass


class ValidationError(APIError):
    """Data validation failed"""
    pass


class BaseAdapter(ABC):
    """
    Base class for external API adapters

    Provides:
    - HTTP client with retry logic
    - Caching functionality
    - Rate limiting
    - Error handling
    - Logging
    """

    def __init__(
        self,
        base_url: str,
        api_key: Optional[str] = None,
        timeout: int = 30,
        max_retries: int = 3,
        cache_ttl: int = 3600,
    ):
        """
        Initialize base adapter

        Args:
            base_url: Base URL for the API
            api_key: API key for authentication (if required)
            timeout: Request timeout in seconds
            max_retries: Maximum number of retry attempts
            cache_ttl: Cache time-to-live in seconds
        """
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.timeout = timeout
        self.max_retries = max_retries
        self.cache_ttl = cache_ttl
        self._session: Optional[aiohttp.ClientSession] = None
        self._cache: Dict[str, Any] = {}  # TODO: Replace with Redis

        logger.debug(
            "Adapter initialized",
            adapter=self.__class__.__name__,
            base_url=self.base_url,
            has_api_key=bool(self.api_key)
        )

    async def __aenter__(self):
        """Async context manager entry"""
        await self._ensure_session()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.close()

    async def _ensure_session(self):
        """Ensure HTTP session is created"""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.timeout),
                headers=self._get_default_headers()
            )

    async def close(self) -> None:
        """Close HTTP session"""
        if self._session and not self._session.closed:
            await self._session.close()
            logger.debug("Session closed", adapter=self.__class__.__name__)

    def _get_default_headers(self) -> Dict[str, str]:
        """
        Get default HTTP headers

        Override in subclasses to add API-specific headers
        """
        headers = {
            "User-Agent": f"Upswitch-Valuation-Engine/{settings.app_version}",
            "Accept": "application/json",
        }

        if self.api_key:
            # Override this in subclass if API key header format differs
            headers["Authorization"] = f"Bearer {self.api_key}"

        return headers

    def _get_cache_key(self, endpoint: str, params: Optional[Dict] = None) -> str:
        """
        Generate cache key from endpoint and parameters

        Args:
            endpoint: API endpoint
            params: Query parameters

        Returns:
            Cache key hash
        """
        cache_data = {
            "adapter": self.__class__.__name__,
            "endpoint": endpoint,
            "params": params or {}
        }
        cache_string = json.dumps(cache_data, sort_keys=True)
        return hashlib.sha256(cache_string.encode()).hexdigest()

    def _get_from_cache(self, cache_key: str) -> Optional[Any]:
        """
        Get data from cache

        Args:
            cache_key: Cache key

        Returns:
            Cached data if available and not expired, None otherwise
        """
        if not settings.enable_cache:
            return None

        cached = self._cache.get(cache_key)
        if cached:
            if datetime.utcnow() < cached['expires_at']:
                logger.debug(
                    "Cache hit",
                    adapter=self.__class__.__name__,
                    cache_key=cache_key[:16]
                )
                return cached['data']
            else:
                # Remove expired entry
                del self._cache[cache_key]
                logger.debug("Cache expired", cache_key=cache_key[:16])

        return None

    def _set_cache(self, cache_key: str, data: Any, ttl: Optional[int] = None):
        """
        Set data in cache

        Args:
            cache_key: Cache key
            data: Data to cache
            ttl: Time-to-live in seconds (uses default if None)
        """
        if not settings.enable_cache:
            return

        ttl = ttl or self.cache_ttl
        self._cache[cache_key] = {
            'data': data,
            'expires_at': datetime.utcnow() + timedelta(seconds=ttl)
        }

        logger.debug(
            "Data cached",
            adapter=self.__class__.__name__,
            cache_key=cache_key[:16],
            ttl=ttl
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((aiohttp.ClientError, asyncio.TimeoutError)),
        reraise=True
    )
    async def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict] = None,
        data: Optional[Dict] = None,
        headers: Optional[Dict] = None,
        use_cache: bool = True,
    ) -> Dict[str, Any]:
        """
        Make HTTP request with retry logic

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint (relative to base_url)
            params: Query parameters
            data: Request body data
            headers: Additional headers
            use_cache: Whether to use caching for GET requests

        Returns:
            Response data as dictionary

        Raises:
            APIError: If request fails after retries
            RateLimitError: If rate limit is exceeded
            DataNotFoundError: If requested data is not found
        """
        await self._ensure_session()

        # Check cache for GET requests
        if method.upper() == 'GET' and use_cache:
            cache_key = self._get_cache_key(endpoint, params)
            cached_data = self._get_from_cache(cache_key)
            if cached_data is not None:
                return cached_data

        # Build URL
        url = f"{self.base_url}/{endpoint.lstrip('/')}"

        # Merge headers
        request_headers = self._get_default_headers()
        if headers:
            request_headers.update(headers)

        # Get current logging context
        logging_context = get_current_context()
        session_id = getattr(logging_context, 'current_session_id', None) if logging_context else None

        # Log external API request
        log_calculation_step(
            "external_api_request",
            inputs={
                "adapter": self.__class__.__name__,
                "method": method,
                "endpoint": endpoint,
                "url": url,
                "params": params,
                "use_cache": use_cache
            },
            outputs={},
            formula="External_API_Request = Build_URL + Prepare_Headers + Check_Cache + Make_Request"
        )

        logger.calculation(
            "External API request",
            session_id=session_id,
            adapter=self.__class__.__name__,
            method=method,
            url=url,
            params=params
        )

        try:
            async with self._session.request(
                method=method,
                url=url,
                params=params,
                json=data,
                headers=request_headers
            ) as response:
                # Handle different status codes
                if response.status == 200:
                    response_data = await response.json()

                    # Cache successful GET requests
                    if method.upper() == 'GET' and use_cache:
                        cache_key = self._get_cache_key(endpoint, params)
                        self._set_cache(cache_key, response_data)

                    # Log successful API response
                    log_calculation_step(
                        "external_api_response_success",
                        inputs={"response_status": response.status, "response_size": len(str(response_data))},
                        outputs={
                            "status_code": response.status,
                            "response_size": len(str(response_data)),
                            "cached": method.upper() == 'GET' and use_cache
                        },
                        formula="API_Response_Success = Parse_JSON + Cache_Response + Log_Success"
                    )

                    logger.calculation(
                        "API request successful",
                        session_id=session_id,
                        adapter=self.__class__.__name__,
                        status=response.status,
                        response_size=len(str(response_data))
                    )

                    return response_data

                elif response.status == 404:
                    raise DataNotFoundError(f"Data not found: {url}")

                elif response.status == 429:
                    raise RateLimitError(f"Rate limit exceeded for {url}")

                elif response.status >= 400:
                    error_text = await response.text()
                    raise APIError(
                        f"API error {response.status}: {error_text}"
                    )

                else:
                    raise APIError(f"Unexpected status code: {response.status}")

        except aiohttp.ClientError as e:
            logger.error(
                "HTTP client error",
                adapter=self.__class__.__name__,
                error=str(e),
                url=url
            )
            raise APIError(f"HTTP request failed: {str(e)}") from e

        except asyncio.TimeoutError as e:
            logger.error(
                "Request timeout",
                adapter=self.__class__.__name__,
                url=url,
                timeout=self.timeout
            )
            raise APIError(f"Request timed out after {self.timeout}s") from e

    @abstractmethod
    async def test_connection(self) -> bool:
        """
        Test connection to the API

        Returns:
            True if connection successful, False otherwise

        This should be implemented by each adapter subclass
        """
        pass

    @abstractmethod
    def validate_response(self, data: Any) -> bool:
        """
        Validate API response data

        Args:
            data: Response data to validate

        Returns:
            True if valid, False otherwise

        This should be implemented by each adapter subclass
        """
        pass

