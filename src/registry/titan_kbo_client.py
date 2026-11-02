"""Titan-owned Belgian KBO registry client.

ValuationIQ is intentionally a calculation engine: Belgian registry identity
is owned by Titan, which owns the KBO database, refreshes, and indexes.
"""

from decimal import Decimal
from typing import Any, Dict, List, Optional

import httpx

from .base import RegistryClient, RegistryFinancialData, RegistrySearchResult


class TitanRegistryUnavailable(RuntimeError):
    """Titan could not provide a valid registry response."""


class TitanRegistryNotFound(RuntimeError):
    """Titan completed a registry lookup but found no matching company."""


class TitanKBOClient(RegistryClient):
    """Adapter from Titan's KBO contract to ValuationIQ registry models."""

    def __init__(self, base_url: str, timeout: float = 10.0):
        normalized_url = base_url.strip()
        if not normalized_url:
            raise ValueError("TITAN_API_URL is required for Belgian registry access")
        self.base_url = normalized_url.rstrip("/")
        self.timeout_seconds = timeout
        super().__init__(timeout=Decimal(str(timeout)))

    def get_registry_name(self) -> str:
        return "Titan KBO"

    def get_country_code(self) -> str:
        return "BE"

    async def _request(self, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.post(f"{self.base_url}{path}", json=payload)
        except httpx.HTTPError as exc:
            raise TitanRegistryUnavailable("Titan registry request failed") from exc

        if response.status_code == 404:
            raise TitanRegistryNotFound("Company not found in Titan KBO registry")
        if response.status_code >= 400:
            raise TitanRegistryUnavailable(
                f"Titan registry returned HTTP {response.status_code}"
            )
        try:
            body = response.json()
        except ValueError as exc:
            raise TitanRegistryUnavailable("Titan registry returned invalid JSON") from exc
        if not isinstance(body, dict):
            raise TitanRegistryUnavailable("Titan registry returned an invalid payload")
        return body

    @staticmethod
    def _as_company(payload: object) -> Dict[str, Any]:
        if not isinstance(payload, dict):
            raise TitanRegistryUnavailable("Titan registry returned an invalid company")
        kbo_number = payload.get("kbo_number")
        company_name = payload.get("company_name")
        if not isinstance(kbo_number, str) or not kbo_number or not isinstance(company_name, str) or not company_name:
            raise TitanRegistryUnavailable("Titan registry company is missing identity fields")
        return payload

    @staticmethod
    def _to_search_result(payload: Dict[str, Any]) -> RegistrySearchResult:
        company = TitanKBOClient._as_company(payload)
        return RegistrySearchResult(
            company_id=company["kbo_number"],
            company_name=company["company_name"],
            registration_number=company["kbo_number"],
            country_code=str(company.get("country_code") or "BE"),
            legal_form=company.get("legal_form"),
            address=company.get("address"),
            status=str(company.get("status") or "unknown"),
            confidence_score=Decimal("1"),
            registry_name="Titan KBO",
            registry_url=None,
            nace_code=company.get("nace_code"),
            nace_description=company.get("nace_description"),
            activity_code=company.get("activity_code"),
            activity_label=company.get("activity_label"),
            taxonomy=company.get("taxonomy"),
            canonical_nace_code=company.get("canonical_nace_code"),
            postal_code=company.get("postal_code"),
            city=company.get("city"),
        )

    async def search_payload(self, company_name: str, limit: int = 10) -> Dict[str, Any]:
        body = await self._request(
            "/api/v2/registry/search",
            {"company_name": company_name, "country_code": "BE", "limit": limit},
        )
        results = body.get("results")
        if not isinstance(results, list):
            raise TitanRegistryUnavailable("Titan registry search is missing results")
        normalized = [self._to_search_result(item).model_dump(mode="json") for item in results]
        return {
            "results": normalized,
            "total_results": int(body.get("total_results", len(normalized))),
            "search_time_ms": int(body.get("search_time_ms", 0)),
            "registry_name": str(body.get("registry_name") or "Titan KBO"),
            "registry_url": None,
        }

    async def search_companies(self, company_name: str, limit: int = 10) -> List[RegistrySearchResult]:
        payload = await self.search_payload(company_name, limit)
        return [RegistrySearchResult.model_validate(item) for item in payload["results"]]

    async def lookup_company(self, kbo_number: str) -> Dict[str, Any]:
        body = await self._request("/api/v2/registry/kbo/lookup", {"kbo_number": kbo_number})
        if body.get("success") is False or body.get("data") is None:
            raise TitanRegistryNotFound("Company not found in Titan KBO registry")
        return self._as_company(body["data"])

    async def get_company_details(self, company_id: str) -> Optional[Dict[str, Any]]:
        try:
            company = await self.lookup_company(company_id)
        except TitanRegistryNotFound:
            return None
        foundation_date = company.get("foundation_date")
        founding_year = int(str(foundation_date)[:4]) if str(foundation_date or "")[:4].isdigit() else None
        return {
            "company_id": company["kbo_number"],
            "company_name": company["company_name"],
            "registration_number": company["kbo_number"],
            "country_code": str(company.get("country_code") or "BE"),
            "legal_form": str(company.get("legal_form") or ""),
            "status": str(company.get("status") or "unknown"),
            "founding_year": founding_year,
            "industry_code": company.get("nace_code"),
            "industry_description": company.get("nace_description"),
            "employees": None,
            "website": None,
            "address": company.get("address"),
            "filing_history": [],
            "data_source": "Titan KBO",
            "source_url": None,
            "last_updated": str(company.get("last_updated") or ""),
            "completeness_score": Decimal("0.6"),
            "metadata": company.get("metadata") if isinstance(company.get("metadata"), dict) else {},
        }

    async def get_company_financials(
        self, company_id: str, years: Optional[int] = None
    ) -> Optional[RegistryFinancialData]:
        # KBO identity data is intentionally separate from Titan's official-filing
        # enrichment contract; this adapter must not invent financial history.
        return None
