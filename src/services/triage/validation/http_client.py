"""
HTTP Client for Validation Framework

Proxies validation operations through Node.js backend to Supabase.
"""

import logging
import os
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

import aiohttp

logger = logging.getLogger(__name__)


class ValidationHTTPClient:
    """
    HTTP client for validation framework operations.

    All database operations go through Node.js proxy to Supabase.
    """

    def __init__(
        self, base_url: Optional[str] = None, api_key: Optional[str] = None, timeout: int = 30
    ):
        self.base_url = (base_url or os.getenv("NODE_BACKEND_URL", "http://localhost:3000")).rstrip(
            "/"
        )
        self.api_key = api_key or os.getenv("VALIDATION_API_KEY")
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self._session: Optional[aiohttp.ClientSession] = None

        logger.info(f"✅ ValidationHTTPClient initialized: {self.base_url}")

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session."""
        if self._session is None or self._session.closed:
            headers = {"Content-Type": "application/json"}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"

            self._session = aiohttp.ClientSession(headers=headers, timeout=self.timeout)
        return self._session

    async def get_truth_by_id(self, truth_id: str) -> Optional[Dict[str, Any]]:
        """Get truth entry by ID."""
        session = await self._get_session()
        url = f"{self.base_url}/api/validation/truth/{truth_id}"

        try:
            async with session.get(url) as response:
                if response.status == 200:
                    return await response.json()
                elif response.status == 404:
                    return None
                else:
                    response.raise_for_status()
        except Exception as e:
            logger.error(f"Error fetching truth {truth_id}: {str(e)}")
            raise

    async def search_truths(
        self, keywords: List[str], language: str = "en", category: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Search truths by keywords."""
        session = await self._get_session()
        url = f"{self.base_url}/api/validation/truth/search"

        payload = {"keywords": keywords, "language": language}
        if category:
            payload["category"] = category

        try:
            async with session.post(url, json=payload) as response:
                response.raise_for_status()
                data = await response.json()
                return data.get("results", [])
        except Exception as e:
            logger.error(f"Error searching truths: {str(e)}")
            raise

    async def match_truths(
        self, claim: str, domain: str, language: str = "en"
    ) -> List[Dict[str, Any]]:
        """Find matching truths for a claim."""
        session = await self._get_session()
        url = f"{self.base_url}/api/validation/truth/match"

        payload = {"claim": claim, "domain": domain, "language": language}

        try:
            async with session.post(url, json=payload) as response:
                response.raise_for_status()
                data = await response.json()
                return data.get("results", [])
        except Exception as e:
            logger.error(f"Error matching truths: {str(e)}")
            raise

    async def validate_answer(
        self,
        question: str,
        answer: str,
        source: str,
        analysis: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Validate an answer through 5-gate pipeline."""
        session = await self._get_session()
        url = f"{self.base_url}/api/validation/validate"

        payload = {"question": question, "answer": answer, "source": source, "analysis": analysis}
        if metadata:
            payload["metadata"] = metadata

        try:
            async with session.post(url, json=payload) as response:
                response.raise_for_status()
                return await response.json()
        except Exception as e:
            logger.error(f"Error validating answer: {str(e)}")
            raise

    async def add_to_review_queue(
        self, validation_report: Dict[str, Any], question: str, answer: str
    ) -> Dict[str, Any]:
        """Add validation report to review queue."""
        session = await self._get_session()
        url = f"{self.base_url}/api/validation/review-queue"

        payload = {"validation_report": validation_report, "question": question, "answer": answer}

        try:
            async with session.post(url, json=payload) as response:
                response.raise_for_status()
                return await response.json()
        except Exception as e:
            logger.error(f"Error adding to review queue: {str(e)}")
            raise

    async def get_metrics(self) -> Dict[str, Any]:
        """Get validation metrics."""
        session = await self._get_session()
        url = f"{self.base_url}/api/validation/metrics"

        try:
            async with session.get(url) as response:
                response.raise_for_status()
                return await response.json()
        except Exception as e:
            logger.error(f"Error fetching metrics: {str(e)}")
            raise

    async def close(self):
        """Close HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()
            logger.info("✅ ValidationHTTPClient session closed")
