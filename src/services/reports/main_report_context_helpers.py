"""Shared helper methods required by main report aggregation mixins."""

from __future__ import annotations

from typing import Optional

from src.services.infrastructure.translations import ReportTranslations
from src.services.interfaces.request_response_protocol import ValuationRequestProtocol
from src.services.reports.report_locale_context import (
    country_code_from_request,
    translations_or_fallback,
)
from src.services.reports.report_methodology_helpers import (
    is_asset_anchored_methodology,
    is_asset_methodology,
    is_dcf_only_methodology,
    is_hybrid_methodology,
    is_yield_methodology,
    normalised_methodology,
)
from src.utils.fiscal_year import resolve_display_current_year

ValuationRequest = ValuationRequestProtocol


class MainReportContextHelpersMixin:
    """Locale, methodology, and filing-year helpers used across report mixins."""

    @staticmethod
    def _country_code_from_request(request: Optional[ValuationRequest]) -> str:
        return country_code_from_request(request)

    def _translations_or_fallback(
        self,
        locale: str,
        request: Optional[ValuationRequest],
        t: Optional[ReportTranslations],
    ) -> ReportTranslations:
        return translations_or_fallback(locale, request, t)

    @staticmethod
    def _is_hybrid_methodology(response: object) -> bool:
        return is_hybrid_methodology(response)

    @staticmethod
    def _normalised_methodology(response: object) -> str:
        return normalised_methodology(response)

    @classmethod
    def _is_asset_methodology(cls, response: object) -> bool:
        return is_asset_methodology(response)

    @classmethod
    def _is_yield_methodology(cls, response: object) -> bool:
        return is_yield_methodology(response)

    @classmethod
    def _is_asset_anchored_methodology(cls, response: object) -> bool:
        return is_asset_anchored_methodology(response)

    def _is_dcf_only_methodology(self, response: object) -> bool:
        return is_dcf_only_methodology(response)

    def _resolve_display_current_year(
        self,
        request: object | None = None,
        response: object | None = None,
    ) -> int:
        return resolve_display_current_year(request=request, response=response)
