"""
Netherlands Registry Client (KVK - Kamer van Koophandel)

Optional integration with a commercial registry API (default: Overheid.io OpenKvK V3).
**Product stance:** NL can ship without any third-party KVK/Overheid API — users enter
company data manually or via accounting imports; when `KVK_API_KEY` is unset, search
returns empty results (not an error).

When enabled, see: https://overheid.io/documentatie/v3/openkvk
Other providers (Company.info, etc.): point `KVK_API_BASE_URL` at a compatible REST shape
or extend this client.

SBI-to-NACE Hack:
  Dutch SBI codes are 5-digit extensions of the 4-digit EU NACE standard.
  We slice off the 5th digit so the existing NaceService works without
  any rewrites (e.g. 62011 -> 6201).
"""

import logging
import os
import re
from collections.abc import Mapping
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

import httpx

from .base import RegistryClient, RegistryFinancialData, RegistrySearchResult

logger = logging.getLogger(__name__)

KVK_NUMBER_PATTERN = re.compile(r"^\d{8}$")

# Overheid.io OpenKvK V3 (current public API)
DEFAULT_OPENKVK_V3_BASE = "https://api.overheid.io/v3/openkvk"


class NetherlandsRegistryClient(RegistryClient):
    """
    Optional commercial registry client for NL search.

    Environment variables (only when you enable a third-party API):
      KVK_API_KEY       – API key (e.g. Overheid.io: ovio-api-key)
      KVK_API_BASE_URL  – Base URL (default: OpenKvK V3)
    """

    BASE_URL = "https://www.kvk.nl"
    DEFAULT_BASE_URL = DEFAULT_OPENKVK_V3_BASE

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: float = 30.0,
    ):
        super().__init__(api_key=api_key, timeout=Decimal(str(timeout)))

        self.api_key = api_key or os.getenv("KVK_API_KEY", "")
        self.base_url = (base_url or os.getenv("KVK_API_BASE_URL") or self.DEFAULT_BASE_URL).rstrip(
            "/"
        )

        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=timeout,
            headers=self._build_headers(),
        )

        if not self.api_key:
            logger.info(
                "NetherlandsRegistryClient: no KVK_API_KEY — NL registry API search disabled "
                "(expected for manual-only / deferred API; manual entry still works)"
            )
        else:
            logger.debug(
                "NetherlandsRegistryClient initialized | base_url: %s",
                self.base_url,
            )

    # ------------------------------------------------------------------
    # RegistryClient interface
    # ------------------------------------------------------------------

    def get_registry_name(self) -> str:
        return "KVK (Kamer van Koophandel)"

    def get_country_code(self) -> str:
        return "NL"

    async def search_companies(
        self,
        company_name: str,
        limit: int = 10,
    ) -> List[RegistrySearchResult]:
        if not self.api_key:
            logger.debug(
                "NL registry search skipped (no KVK_API_KEY); empty results — use manual entry or imports"
            )
            return []

        query = company_name.strip()
        if len(query) < 2:
            return []

        is_kvk_number = KVK_NUMBER_PATTERN.match(query)

        try:
            size = min(limit, 100)
            # OpenKvK V3: filters[kvknummer] for 8-digit KVK; query + queryfields for name search.
            # httpx needs list-of-tuples for repeated queryfields[] keys.
            if is_kvk_number:
                params: List[Tuple[str, str]] = [
                    ("size", str(size)),
                    ("page", "1"),
                    ("filters[kvknummer]", query),
                ]
            else:
                params = [
                    ("size", str(size)),
                    ("page", "1"),
                    ("query", query),
                    ("queryfields[]", "naam"),
                    ("queryfields[]", "huidigeHandelsNamen"),
                ]

            response = await self._client.get("/", params=params)
            response.raise_for_status()
            data = response.json()

            results: List[RegistrySearchResult] = []
            items = self._extract_result_items(data)

            if isinstance(items, list):
                for item in items[:limit]:
                    result = self._map_to_search_result(item, query)
                    if result:
                        results.append(result)

            logger.info(
                "KVK search completed | query: %s | results: %d",
                query,
                len(results),
            )
            return results

        except httpx.HTTPStatusError as exc:
            logger.error(
                "KVK API HTTP error | status: %s | query: %s",
                exc.response.status_code,
                query,
            )
            return []
        except httpx.RequestError as exc:
            logger.error("KVK API request error | error: %s | query: %s", exc, query)
            return []
        except Exception as exc:
            logger.error(
                "KVK search unexpected error | error: %s | type: %s | query: %s",
                exc,
                type(exc).__name__,
                query,
                exc_info=True,
            )
            return []

    async def get_company_financials(
        self,
        company_id: str,
        years: Optional[int] = None,
    ) -> Optional[RegistryFinancialData]:
        # NL company financials are not publicly available via KVK
        return None

    async def get_company_details(
        self,
        company_id: str,
    ) -> Optional[Dict[str, Any]]:
        if not self.api_key:
            return None

        try:
            data: Optional[Dict[str, Any]] = None
            slug_or_kvk = company_id.strip()

            if KVK_NUMBER_PATTERN.match(slug_or_kvk):
                list_params: List[Tuple[str, str]] = [
                    ("filters[kvknummer]", slug_or_kvk),
                    ("size", "1"),
                    ("page", "1"),
                ]
                r = await self._client.get("/", params=list_params)
                r.raise_for_status()
                listing = r.json()
                items = self._extract_result_items(listing)
                if not items:
                    return None
                first = items[0]
                slug = self._openkvk_slug_from_item(first)
                if slug:
                    dr = await self._client.get(f"/{slug}")
                    dr.raise_for_status()
                    data = dr.json()
                else:
                    data = first
            else:
                response = await self._client.get(f"/{slug_or_kvk.lstrip('/')}")
                response.raise_for_status()
                data = response.json()

            if not data:
                return None

            return {
                "kvk_number": self._extract_kvk_digits(data, slug_or_kvk),
                "company_name": self._extract_company_name(data),
                "legal_form": self._extract_legal_form(data),
                "address": self._format_address(data),
                "sbi_code": self._extract_sbi(data),
                "nace_code": self._sbi_to_nace(self._extract_sbi(data)),
                "status": "active" if data.get("actief", True) else "inactive",
                "country_code": "NL",
            }
        except Exception as exc:
            logger.error(
                "KVK details error | company_id: %s | error: %s",
                company_id,
                exc,
            )
            return None

    # ------------------------------------------------------------------
    # OpenKvK V3 parsing
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_result_items(data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """HAL list: _embedded.bedrijf; legacy: results / resultaten."""
        embedded = data.get("_embedded") or {}
        bedrijf = embedded.get("bedrijf")
        if isinstance(bedrijf, list):
            return bedrijf
        for key in ("results", "resultaten"):
            v = data.get(key)
            if isinstance(v, list):
                return v
        return []

    @staticmethod
    def _openkvk_slug_from_item(item: Dict[str, Any]) -> Optional[str]:
        """Resolve detail path segment from HAL _links.self.href."""
        links = item.get("_links") or {}
        self_link = links.get("self") or {}
        href = self_link.get("href") if isinstance(self_link, dict) else None
        if not href or not isinstance(href, str):
            return None
        # "/v3/openkvk/hoofdvestiging-58488340-downsized" -> last segment
        part = href.rstrip("/").split("/")[-1]
        return part or None

    @staticmethod
    def _extract_kvk_digits(data: Dict[str, Any], fallback: str) -> str:
        for key in ("kvkNummer", "kvknummer"):
            v = data.get(key)
            if v is not None and str(v).strip():
                return str(v).strip()
        return fallback if KVK_NUMBER_PATTERN.match(fallback) else fallback

    @staticmethod
    def _extract_company_name(data: Dict[str, Any]) -> str:
        name = data.get("handelsnaam") or data.get("naam") or ""
        if isinstance(name, str) and name.strip():
            return name.strip()
        hhn = data.get("huidigeHandelsNamen")
        if isinstance(hhn, list) and hhn:
            first = hhn[0]
            if isinstance(first, str) and first.strip():
                return first.strip()
        return ""

    @staticmethod
    def _extract_legal_form(data: Dict[str, Any]) -> str:
        return str(data.get("rechtsvormOmschrijving") or data.get("rechtsvorm") or "").strip()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _build_headers(self) -> Dict[str, str]:
        headers: Dict[str, str] = {
            "Accept": "application/json",
        }
        if self.api_key:
            headers["ovio-api-key"] = self.api_key
        return headers

    def _map_to_search_result(
        self,
        item: Dict[str, Any],
        query: str,
    ) -> Optional[RegistrySearchResult]:
        kvk_number = self._kvk_from_item(item)
        company_name = self._name_from_item(item)

        if not kvk_number or not company_name:
            return None

        sbi_code = self._extract_sbi(item)
        nace_code = self._sbi_to_nace(sbi_code)

        address = self._format_address(item)
        legal_form = self._extract_legal_form(item) or None
        postal_code, city = self._postal_and_city(item)

        is_active = item.get("actief", True)
        status = "active" if is_active else "inactive"

        confidence = self._calculate_confidence(company_name, kvk_number, query)

        return RegistrySearchResult(
            result_type="COMPANY",
            company_id=kvk_number,
            company_name=company_name,
            registration_number=kvk_number,
            country_code="NL",
            legal_form=legal_form,
            address=address,
            status=status,
            confidence_score=confidence,
            registry_name=self.get_registry_name(),
            registry_url=f"https://www.kvk.nl/bestellen/#/kvk-nummer-{kvk_number}",
            nace_code=nace_code or None,
            nace_description=self._extract_sbi_description(item),
            activity_code=sbi_code or None,
            activity_label=self._extract_sbi_description(item),
            taxonomy="SBI_2008" if sbi_code else "UNKNOWN",
            canonical_nace_code=nace_code or None,
            postal_code=postal_code,
            city=city,
        )

    @staticmethod
    def _kvk_from_item(item: Dict[str, Any]) -> str:
        v = item.get("kvkNummer") or item.get("kvknummer")
        if v is not None:
            return str(v).strip()
        return ""

    @staticmethod
    def _name_from_item(item: Dict[str, Any]) -> str:
        if item.get("handelsnaam"):
            return str(item["handelsnaam"]).strip()
        if item.get("naam"):
            return str(item["naam"]).strip()
        # OpenKvK v3 list endpoint returns "huidigeNamen"; detail endpoint returns "huidigeHandelsNamen"
        for key in ("huidigeHandelsNamen", "huidigeNamen"):
            hhn = item.get(key)
            if isinstance(hhn, list) and hhn:
                n0 = hhn[0]
                if isinstance(n0, str) and n0.strip():
                    return n0.strip()
        stat = item.get("statutaireNaam")
        if stat:
            return str(stat).strip()
        return ""

    @staticmethod
    def _postal_and_city(item: Dict[str, Any]) -> tuple[Optional[str], Optional[str]]:
        bl = item.get("bezoeklocatie")
        if isinstance(bl, dict):
            pc = str(bl.get("postcode") or "").strip() or None
            city = str(bl.get("plaats") or "").strip() or None
            return pc, city
        postal_code = str(item.get("postcode") or "").strip() or None
        city = str(item.get("plaats") or item.get("plaatsnaam") or "").strip() or None
        return postal_code, city

    @staticmethod
    def _extract_sbi(data: Dict[str, Any]) -> str:
        """Extract the primary SBI / activity code from OpenKvK V3 or legacy JSON."""
        primary_activity = NetherlandsRegistryClient._primary_activity(data)
        if primary_activity:
            code = NetherlandsRegistryClient._first_present(primary_activity, ("code", "sbiCode"))
            if code is not None:
                return NetherlandsRegistryClient._as_stripped_text(code)

        sbi_arr = data.get("sbi")
        if isinstance(sbi_arr, list) and sbi_arr:
            first = sbi_arr[0]
            if first is not None:
                return NetherlandsRegistryClient._as_stripped_text(first)

        direct_sbi = NetherlandsRegistryClient._normalize_sbi_value(
            NetherlandsRegistryClient._first_present(data, ("spiCode", "sbiCode", "sbiActiviteit"))
        )
        if direct_sbi:
            return direct_sbi

        return NetherlandsRegistryClient._normalize_sbi_value(data.get("sbiActiviteiten"))

    @staticmethod
    def _sbi_to_nace(sbi_code: str) -> str:
        """
        Convert a 5-digit Dutch SBI code to a 4-digit EU NACE code.
        SBI codes are 5-digit extensions of NACE Rev. 2.
        Example: 62011 (SBI) -> 6201 (NACE)
        """
        digits = re.sub(r"\D", "", sbi_code)
        if len(digits) >= 4:
            return digits[:4]
        return digits

    @staticmethod
    def _extract_sbi_description(data: Dict[str, Any]) -> Optional[str]:
        """Extract the primary SBI activity description from the API response."""
        primary_activity = NetherlandsRegistryClient._primary_activity(data)
        activity_label = NetherlandsRegistryClient._first_stripped_text(
            primary_activity, ("omschrijving",)
        )
        if activity_label:
            return activity_label

        direct_label = NetherlandsRegistryClient._first_stripped_text(
            data,
            ("sbiOmschrijving", "omschrijving", "primaireActiviteit", "activiteitomschrijving"),
        )
        if direct_label:
            return direct_label

        return NetherlandsRegistryClient._first_sbi_activity_label(data.get("sbiActiviteiten"))

    @staticmethod
    def _primary_activity(data: Mapping[str, object]) -> Optional[Mapping[str, object]]:
        activiteiten = data.get("activiteiten")
        if not isinstance(activiteiten, list) or not activiteiten:
            return None

        hoofd = next(
            (
                activity
                for activity in activiteiten
                if isinstance(activity, dict) and activity.get("hoofdactiviteit")
            ),
            None,
        )
        chosen = hoofd or activiteiten[0]
        return chosen if isinstance(chosen, dict) else None

    @staticmethod
    def _first_present(data: Mapping[str, object], keys: tuple[str, ...]) -> object | None:
        for key in keys:
            value = data.get(key)
            if value:
                return value
        return None

    @staticmethod
    def _first_stripped_text(
        data: Optional[Mapping[str, object]], keys: tuple[str, ...]
    ) -> Optional[str]:
        if not data:
            return None

        for key in keys:
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return None

    @staticmethod
    def _normalize_sbi_value(value: object) -> str:
        if isinstance(value, list) and value:
            value = value[0]

        if isinstance(value, dict):
            value = value.get("sbiCode") or value.get("code") or ""

        return NetherlandsRegistryClient._as_stripped_text(value)

    @staticmethod
    def _first_sbi_activity_label(value: object) -> Optional[str]:
        if not isinstance(value, list) or not value:
            return None

        first = value[0]
        if not isinstance(first, dict):
            return None

        return NetherlandsRegistryClient._first_stripped_text(
            first, ("omschrijving", "sbiOmschrijving", "description")
        )

    @staticmethod
    def _as_stripped_text(value: object) -> str:
        return str(value or "").strip()

    @staticmethod
    def _format_address(data: Dict[str, Any]) -> str:
        bl = data.get("bezoeklocatie")
        if isinstance(bl, dict):
            street = bl.get("straat") or bl.get("straatnaam") or ""
            house = bl.get("huisnummer") or ""
            line1 = f"{street} {house}".strip() if street else ""
            postal = bl.get("postcode") or ""
            city = bl.get("plaats") or ""
            line2 = f"{postal} {city}".strip() if postal or city else ""
            parts = [p for p in (line1, line2) if p]
            if parts:
                return ", ".join(parts)

        parts: List[str] = []

        street = data.get("straatnaam") or data.get("straat", "")
        house = data.get("huisnummer", "")
        if street:
            parts.append(f"{street} {house}".strip())

        postal = data.get("postcode", "")
        city = data.get("plaats") or data.get("plaatsnaam", "")
        if postal or city:
            parts.append(f"{postal} {city}".strip())

        return ", ".join(filter(None, parts)) or ""

    @staticmethod
    def _calculate_confidence(
        company_name: str,
        kvk_number: str,
        query: str,
    ) -> Decimal:
        q = query.lower().strip()
        name = company_name.lower().strip()

        if q == kvk_number:
            return Decimal("1.0")
        if q == name:
            return Decimal("1.0")
        if name.startswith(q):
            return Decimal("0.9")
        if q in name:
            return Decimal("0.8")
        return Decimal("0.7")

    def get_registry_url(self, company_id: str) -> Optional[str]:
        return f"https://www.kvk.nl/bestellen/#/kvk-nummer-{company_id}"

    async def close(self) -> None:
        await self._client.aclose()
