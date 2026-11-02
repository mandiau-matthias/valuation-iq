"""
FX Converter utility

Uses Frankfurter (ECB) rates to convert amounts to EUR.
Lightweight in-memory cache with graceful fallback to last good rates.
"""

import time
from decimal import Decimal, InvalidOperation
from typing import Dict, Optional, Tuple

import requests

from src.utils.logging import get_logger

logger = get_logger(__name__)


class FxConverter:
    """
    Minimal FX converter to EUR using Frankfurter (ECB).
    """

    def __init__(self, base_url: str = "https://api.frankfurter.app", ttl_seconds: int = 3600):
        self.base_url = base_url.rstrip("/")
        self.ttl_seconds = ttl_seconds
        self._cache_rate: Dict[str, Tuple[float, float]] = {}  # currency -> (rate, timestamp)
        self._last_good_rate: Dict[str, float] = {}

    def _is_cached(self, currency: str) -> bool:
        if currency not in self._cache_rate:
            return False
        rate, ts = self._cache_rate[currency]
        return (time.time() - ts) < self.ttl_seconds

    def _fetch_rate(self, currency: str) -> Optional[float]:
        try:
            resp = requests.get(
                f"{self.base_url}/latest", params={"from": currency.upper(), "to": "EUR"}, timeout=3
            )
            if resp.status_code != 200:
                logger.warning(
                    "FX fetch failed", extra={"currency": currency, "status": resp.status_code}
                )
                return None
            data = resp.json()
            rate = data.get("rates", {}).get("EUR")
            if rate is None:
                logger.warning(
                    "FX fetch missing EUR rate",
                    extra={"currency": currency, "data_keys": list(data.keys())},
                )
                return None
            self._cache_rate[currency] = (float(rate), time.time())
            self._last_good_rate[currency] = float(rate)
            return float(rate)
        except Exception as e:
            logger.error("FX fetch exception", extra={"currency": currency, "error": str(e)})
            return None

    def get_rate(self, currency: str) -> Optional[float]:
        curr = currency.upper()
        if curr == "EUR":
            return 1.0
        if self._is_cached(curr):
            return self._cache_rate[curr][0]
        rate = self._fetch_rate(curr)
        if rate is not None:
            return rate
        # fallback to last good rate if available
        return self._last_good_rate.get(curr)

    def convert_to_eur(self, amount: Decimal, currency: str) -> Optional[Decimal]:
        try:
            rate = self.get_rate(currency)
            if rate is None:
                return None
            return (amount * Decimal(str(rate))).quantize(Decimal("0.01"))
        except (InvalidOperation, Exception) as e:
            logger.error("FX conversion failed", extra={"currency": currency, "error": str(e)})
            return None
