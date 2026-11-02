"""Official-financials compatibility facades for the main report aggregator."""

from collections.abc import Mapping

from src.services.interfaces.request_response_protocol import (
    ValuationRequestProtocol,
    ValuationResponseProtocol,
)
from src.services.reports.official_financials_context import build_official_financials_context
from src.services.reports.official_variance_context import (
    OfficialVarianceTranslations,
    build_official_variance_comparison_rows,
)


class MainReportOfficialFinancialsMixin:
    """Private compatibility methods backed by modular official-filing builders."""

    def _get_official_financials_data(
        self,
        response: ValuationResponseProtocol,
        request: ValuationRequestProtocol | None = None,
    ) -> dict[str, object]:
        return build_official_financials_context(response, request)

    def _build_official_variance_comparison_rows(
        self,
        official_financials: Mapping[str, object],
        user_revenue: float | None,
        user_ebitda: float | None,
        translations: OfficialVarianceTranslations,
    ) -> list[dict[str, object]]:
        return build_official_variance_comparison_rows(
            official_financials,
            user_revenue,
            user_ebitda,
            translations,
        )
