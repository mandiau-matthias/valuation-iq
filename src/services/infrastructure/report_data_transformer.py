"""
Report Data Transformer Service

DEPRECATED: The ``ReportDataTransformer`` class in this module is unused —
no production code path instantiates it.  The active report pipeline uses
``MainReportDataAggregator`` + ``SimplifiedReportTransformer`` instead.

The module-level helpers ``transform_for_info_tab()``, ``_get_orchestrator()``,
and ``transform_valuation_response()`` are still imported by
``html_report_service.py`` and ``main.py`` (startup health-check), so the file
must NOT be deleted without first migrating those call-sites.
"""

import uuid
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional

import structlog

from src.api.schemas import (
    AccountantBranding,
    ComparableTransaction,
    EBITDAAdjustment,
    ValuationMetric,
    ValuationReportData,
    ValuationRequest,
    ValuationResponse,
    YearlyEBITDA,
)
from src.domain.report_contact.sanitize import sanitize_report_email
from src.services.infrastructure.report_confidence import (
    confidence_score_display,
    confidence_score_percent,
)
from src.services.infrastructure.report_data_transformer_multi_year import extract_multi_year_ebitda
from src.services.reports.ebitda_extraction_context import extract_ebitda_values
from src.utils.fiscal_year import primary_filing_year_for_report_data

logger = structlog.get_logger(__name__)


def _first_present(*values: object) -> object | None:
    """Return the first explicitly present value, preserving zero."""
    for value in values:
        if value is not None:
            return value
    return None


def _current_year_data(request: Optional[ValuationRequest]) -> object | None:
    if request is None:
        return None
    return getattr(request, "current_year_data", None)


def _current_year_metadata(request: Optional[ValuationRequest]) -> dict[str, object]:
    current_year_data = _current_year_data(request)
    metadata = getattr(current_year_data, "ebitda_normalization_metadata", None)
    return metadata if isinstance(metadata, dict) else {}


def _optional_decimal(value: object) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _decimal_or_zero(value: object) -> Decimal:
    return _optional_decimal(value) or Decimal("0")


def _reported_ebitda_for_adjustments(request: Optional[ValuationRequest]) -> Decimal | None:
    metadata = _current_year_metadata(request)
    reported_ebitda = _optional_decimal(metadata.get("reported_ebitda"))
    if reported_ebitda is not None:
        return reported_ebitda

    current_year_data = _current_year_data(request)
    return _optional_decimal(getattr(current_year_data, "ebitda", None))


def _normalized_ebitda_for_adjustments(normalization: Dict[str, Any]) -> Decimal | None:
    return _optional_decimal(
        _first_present(
            normalization.get("normalized_ebitda"),
            normalization.get("sustainable_ebitda"),
        )
    )


def _adjustment_value(row: Dict[str, Any]) -> Decimal:
    return _decimal_or_zero(row.get("amount", row.get("value", 0)))


def _adjustment_type(row: Dict[str, Any], value: Decimal) -> str:
    return row.get("type") or ("add" if value > 0 else "subtract")


def _adjustment_label(row: Dict[str, Any], index: int) -> str:
    return row.get("label") or row.get("name") or f"Adjustment {index + 1}"


def _adjustment_from_row(
    row: Dict[str, Any],
    index: int,
    *,
    include_source_ref: bool,
    include_approved_by: bool,
    honor_status: bool,
) -> EBITDAAdjustment:
    value = _adjustment_value(row)
    adjustment = {
        "id": row.get("id") or str(uuid.uuid4()),
        "label": _adjustment_label(row, index),
        "value": value,
        "type": _adjustment_type(row, value),
        "category": row.get("category", "normalization"),
        "description": row.get("description"),
        "source": row.get("source"),
        "status": row.get("status", "approved") if honor_status else "approved",
    }
    if include_source_ref:
        adjustment["source_ref"] = row.get("source_ref", row.get("sourceRef"))
    if include_approved_by:
        adjustment["approved_by"] = row.get("approved_by", row.get("approvedBy"))
    return EBITDAAdjustment(**adjustment)


def _adjustments_from_rows(
    rows: object,
    *,
    include_source_ref: bool,
    include_approved_by: bool,
    honor_status: bool,
) -> List[EBITDAAdjustment]:
    if not isinstance(rows, list):
        return []
    return [
        _adjustment_from_row(
            row,
            index,
            include_source_ref=include_source_ref,
            include_approved_by=include_approved_by,
            honor_status=honor_status,
        )
        for index, row in enumerate(rows)
        if isinstance(row, dict)
    ]


def _has_adjustment_type(adjustments: List[EBITDAAdjustment], adjustment_type: str) -> bool:
    return any(adjustment.type == adjustment_type for adjustment in adjustments)


def _with_base_and_result_rows(
    adjustments: List[EBITDAAdjustment],
    *,
    reported_ebitda: Decimal | None,
    normalized_ebitda: Decimal | None,
) -> List[EBITDAAdjustment]:
    if reported_ebitda is not None and not _has_adjustment_type(adjustments, "base"):
        adjustments.insert(
            0,
            EBITDAAdjustment(
                id="base",
                label="Reported EBITDA",
                value=reported_ebitda,
                type="base",
                category="base",
                status="approved",
            ),
        )

    if normalized_ebitda is not None and not _has_adjustment_type(adjustments, "result"):
        adjustments.append(
            EBITDAAdjustment(
                id="result",
                label="Normalized EBITDA",
                value=normalized_ebitda,
                type="result",
                category="result",
                status="approved",
            )
        )
    return adjustments


# Industry emoji mapping
INDUSTRY_EMOJIS: Dict[str, str] = {
    "bakery": "🥐",
    "restaurant": "🍽️",
    "cafe": "☕",
    "retail": "🛍️",
    "technology": "💻",
    "manufacturing": "🏭",
    "construction": "🏗️",
    "healthcare": "🏥",
    "finance": "💰",
    "real_estate": "🏠",
    "hospitality": "🏨",
    "food-production": "🍕",
    "food-services": "🍴",
    "professional-services": "💼",
    "services": "🔧",
    "ecommerce": "🛒",
    "logistics": "🚚",
    "education": "📚",
    "entertainment": "🎬",
    "agriculture": "🌾",
}


class ReportDataTransformer:
    """
    Transforms valuation results to React template format.

    This service converts the internal ValuationResponse to the
    ValuationReportData format expected by the frontend React template.
    """

    _NORMALIZATION_KEYS = ("normalization", "ebitda_normalization", "ebitda_normalization_results")

    def __init__(self):
        self.logger = logger.bind(service="ReportDataTransformer")

    @staticmethod
    def _get_normalization_dict(detailed_results) -> Dict[str, Any]:
        """Resolve the normalization sub-dict from detailed_results, trying multiple known keys."""
        if not detailed_results or not hasattr(detailed_results, "get"):
            return {}
        for key in ReportDataTransformer._NORMALIZATION_KEYS:
            candidate = detailed_results.get(key)
            if isinstance(candidate, dict) and candidate:
                return candidate
        return {}

    def transform(
        self,
        response: ValuationResponse,
        request: Optional[ValuationRequest] = None,
        accountant: Optional[Dict[str, Any]] = None,
    ) -> ValuationReportData:
        """
        Transform valuation response to report template data.

        Args:
            response: ValuationResponse from calculation
            request: Original ValuationRequest (for additional context)
            accountant: Optional accountant branding data

        Returns:
            ValuationReportData for React template
        """
        self.logger.info(
            "Transforming valuation to report data",
            valuation_id=response.valuation_id,
            company_name=response.company_name,
        )

        # Extract EBITDA data
        ebitda, reported_ebitda, normalized_ebitda = self._extract_ebitda(response, request)

        # Extract multiple data
        multiple, multiple_low, multiple_high = self._extract_multiple(response, request)

        # Build metrics grid
        metrics = self._build_metrics(response, request)

        # Build EBITDA adjustments (if available)
        adjustments = self._extract_adjustments(response, request)

        # Build multi-year EBITDA (if available)
        multi_year = self._extract_multi_year_ebitda(response, request)

        # Get industry emoji
        industry = self._get_industry(response, request)
        industry_emoji = INDUSTRY_EMOJIS.get(industry.lower(), "📊") if industry else "📊"

        # Build comparables
        comparables = self._extract_comparables(response)

        # Build accountant branding
        accountant_branding = self._build_accountant_branding(accountant)

        primary_filing_year = primary_filing_year_for_report_data(
            request=request,
            response=response,
            multi_year=multi_year,
        )

        report_data = ValuationReportData(
            id=response.valuation_id,
            company_name=response.company_name,
            generated_at=datetime.now().isoformat(),
            # Valuation results
            valuation=response.equity_value_mid,
            valuation_low=response.equity_value_low,
            valuation_high=response.equity_value_high,
            # EBITDA data
            ebitda=ebitda,
            reported_ebitda=reported_ebitda,
            latest_normalized_ebitda=normalized_ebitda,
            primary_filing_year=primary_filing_year,
            ebitda_adjustments=adjustments,
            multi_year_ebitda=multi_year,
            # Multiple data
            multiple=multiple,
            multiple_low=multiple_low,
            multiple_high=multiple_high,
            # Company context
            industry=industry,
            industry_emoji=industry_emoji,
            revenue=self._get_revenue(response, request),
            employee_count=self._get_employee_count(request),
            founded_year=self._get_founded_year(request),
            country_code=self._get_country_code(request),
            # Metrics grid
            metrics=metrics,
            # Methodology
            methodology=self._get_methodology(response),
            methodology_notes=response.methodology_notes,
            # Comparables
            comparables=comparables,
            # Co-branding
            accountant=accountant_branding,
            # Confidence and risk
            confidence_level=(
                response.overall_confidence.value if response.overall_confidence else None
            ),
            confidence_score=confidence_score_percent(response.confidence_score),
            risk_factors=response.risk_factors[:5] if response.risk_factors else None,
            value_drivers=response.key_value_drivers[:5] if response.key_value_drivers else None,
        )

        self.logger.info(
            "Report data transformation complete",
            valuation_id=response.valuation_id,
            metrics_count=len(metrics),
            adjustments_count=len(adjustments),
        )

        return report_data

    def _extract_ebitda(
        self,
        response: ValuationResponse,
        request: Optional[ValuationRequest],
    ) -> tuple[Decimal, Optional[Decimal], Optional[Decimal]]:
        """Extract EBITDA values using the shared report extraction cascade."""
        normalization = self._get_normalization_dict(response.detailed_results)

        sustainable_ebitda, reported_ebitda, normalized_ebitda = extract_ebitda_values(
            response=response,
            request=request,
            normalization=normalization,
            current_year_metadata=_current_year_metadata(request),
        )
        self.logger.debug(
            "EBITDA extraction result",
            sustainable_ebitda=float(sustainable_ebitda),
            reported_ebitda=float(reported_ebitda),
            normalized_ebitda=float(normalized_ebitda),
        )

        return sustainable_ebitda, reported_ebitda, normalized_ebitda

    def _extract_multiple(
        self,
        response: ValuationResponse,
        request: Optional[ValuationRequest] = None,
    ) -> tuple[Decimal, Optional[Decimal], Optional[Decimal]]:
        """Extract multiple values from response.

        Priority:
        1. response.multiples_valuation.ev_ebitda_multiple
        2. Calculate from valuation / EBITDA
        3. Return 0 when no defensible multiple is present
        """
        # Try from multiples_valuation
        if response.multiples_valuation:
            mv = response.multiples_valuation
            multiple = mv.ev_ebitda_multiple if mv.ev_ebitda_multiple is not None else Decimal("0")
            # Try to get range from percentiles
            multiple_low = getattr(mv, "ev_ebitda_p25", None)
            multiple_high = getattr(mv, "ev_ebitda_p75", None)
            return multiple, multiple_low, multiple_high

        # Calculate from valuation and EBITDA
        ebitda = self._get_ebitda_for_multiple(response, request)
        if ebitda and ebitda > 0 and response.equity_value_mid:
            multiple = response.equity_value_mid / ebitda
            multiple_low = response.equity_value_low / ebitda if response.equity_value_low else None
            multiple_high = (
                response.equity_value_high / ebitda if response.equity_value_high else None
            )
            return multiple, multiple_low, multiple_high

        return Decimal("0"), None, None

    def _get_ebitda_for_multiple(
        self,
        response: ValuationResponse,
        request: Optional[ValuationRequest],
    ) -> Optional[Decimal]:
        """Get EBITDA value for multiple calculation."""
        # From response current_year_data
        if response.current_year_data and hasattr(response.current_year_data, "ebitda"):
            if response.current_year_data.ebitda:
                return response.current_year_data.ebitda

        # From request current_year_data
        if request and request.current_year_data and hasattr(request.current_year_data, "ebitda"):
            if request.current_year_data.ebitda:
                return request.current_year_data.ebitda

        # From detailed_results
        norm = self._get_normalization_dict(response.detailed_results)
        if norm:
            ebitda = _first_present(norm.get("sustainable_ebitda"), norm.get("normalized_ebitda"))
            if ebitda is not None:
                return Decimal(str(ebitda))

        return None

    def _build_metrics(
        self,
        response: ValuationResponse,
        request: Optional[ValuationRequest],
    ) -> List[ValuationMetric]:
        """Build key metrics grid from available data sources."""
        metrics = []

        # Get EBITDA from correct sources
        ebitda = self._get_ebitda_for_multiple(response, request)
        if ebitda and ebitda > 0:
            metrics.append(
                ValuationMetric(
                    label="EBITDA",
                    value=f"€{int(ebitda):,}",
                    category="financial",
                )
            )

        # Get Revenue from correct sources
        revenue = self._get_revenue(response, request)
        if revenue and revenue > 0:
            metrics.append(
                ValuationMetric(
                    label="Revenue",
                    # nl-BE thousands separator (period, not the locale-independent
                    # comma): "€2,130,092" → "€2.130.092" so the prose figure matches
                    # the nl-formatted data tables (advisor panel — locale slip).
                    value=f"€{int(revenue):,}".replace(",", "."),
                    category="financial",
                )
            )

        # EBITDA Margin (calculate if both available)
        if ebitda and revenue and revenue > 0:
            margin = (ebitda / revenue) * 100
            metrics.append(
                ValuationMetric(
                    label="EBITDA Margin",
                    value=f"{margin:.1f}%",
                    category="financial",
                )
            )
        elif response.financial_metrics and response.financial_metrics.ebitda_margin:
            # Use pre-calculated margin from financial_metrics
            metrics.append(
                ValuationMetric(
                    label="EBITDA Margin",
                    value=f"{float(response.financial_metrics.ebitda_margin):.1f}%",
                    category="financial",
                )
            )

        # Revenue Growth
        if response.financial_metrics and response.financial_metrics.revenue_growth:
            growth = response.financial_metrics.revenue_growth * 100  # Convert from decimal
            sign = "+" if growth > 0 else ""
            metrics.append(
                ValuationMetric(
                    label="Revenue Growth (YoY)",
                    value=f"{sign}{growth:.1f}%",
                    change=float(growth),
                    category="growth",
                )
            )

        # Multiple
        multiple, _, _ = self._extract_multiple(response, request)
        metrics.append(
            ValuationMetric(
                label="EV/EBITDA Multiple",
                value=f"{float(multiple):.2f}x",
                category="financial",
            )
        )

        # Confidence
        confidence_score_pct = confidence_score_percent(response.confidence_score)
        if confidence_score_pct is not None:
            metrics.append(
                ValuationMetric(
                    label="Confidence",
                    value=f"{confidence_score_display(confidence_score_pct)}%",
                    category="operational",
                )
            )

        return metrics

    def _extract_adjustments(
        self,
        response: ValuationResponse,
        request: Optional[ValuationRequest],
    ) -> List[EBITDAAdjustment]:
        """Extract EBITDA normalization adjustments.

        Sources:
        1. response.detailed_results.normalization.adjustments
        2. request.current_year_data.ebitda_normalization_metadata
        3. Build base/result from EBITDA values
        """
        normalization = self._get_normalization_dict(response.detailed_results)
        adjustments = _adjustments_from_rows(
            normalization.get("adjustments"),
            include_source_ref=True,
            include_approved_by=True,
            honor_status=True,
        )
        if not adjustments:
            adjustments = _adjustments_from_rows(
                _current_year_metadata(request).get("adjustments"),
                include_source_ref=False,
                include_approved_by=False,
                honor_status=False,
            )

        return _with_base_and_result_rows(
            adjustments,
            reported_ebitda=_reported_ebitda_for_adjustments(request),
            normalized_ebitda=_normalized_ebitda_for_adjustments(normalization),
        )

    def _extract_multi_year_ebitda(
        self,
        response: ValuationResponse,
        request: Optional[ValuationRequest],
    ) -> Optional[List[YearlyEBITDA]]:
        return extract_multi_year_ebitda(response, request)

    def _get_industry(
        self,
        response: ValuationResponse,
        request: Optional[ValuationRequest],
    ) -> Optional[str]:
        """Get industry classification."""
        if request and hasattr(request, "industry") and request.industry:
            return request.industry

        # Try from business_type_intelligence
        if response.business_type_intelligence:
            return response.business_type_intelligence.get("industry")

        return None

    def _get_revenue(
        self,
        response: ValuationResponse,
        request: Optional[ValuationRequest],
    ) -> Optional[Decimal]:
        """Get revenue value from available data sources.

        Priority:
        1. response.current_year_data.revenue (Pydantic model)
        2. request.current_year_data.revenue (Pydantic model)
        3. None
        """
        # From response current_year_data (Pydantic model, not dict)
        if response.current_year_data and hasattr(response.current_year_data, "revenue"):
            if response.current_year_data.revenue:
                return response.current_year_data.revenue

        # From request current_year_data (Pydantic model, not dict)
        if request and request.current_year_data and hasattr(request.current_year_data, "revenue"):
            if request.current_year_data.revenue:
                return request.current_year_data.revenue

        return None

    def _get_employee_count(
        self,
        request: Optional[ValuationRequest],
    ) -> Optional[int]:
        """Get employee count from request."""
        if request and hasattr(request, "number_of_employees"):
            return request.number_of_employees
        return None

    def _get_founded_year(
        self,
        request: Optional[ValuationRequest],
    ) -> Optional[int]:
        """Get founding year from request."""
        if request and hasattr(request, "founding_year"):
            return request.founding_year
        return None

    def _get_country_code(
        self,
        request: Optional[ValuationRequest],
    ) -> Optional[str]:
        """Get country code from request."""
        if request and hasattr(request, "country_code"):
            return request.country_code
        return None

    def _get_methodology(
        self,
        response: ValuationResponse,
    ) -> Optional[str]:
        """Get methodology description."""
        # Determine primary methodology
        if response.dcf_weight > response.multiples_weight:
            return "Discounted Cash Flow (DCF)"
        elif response.multiples_weight > Decimal("0.8"):
            return "EBITDA Multiple"
        else:
            return "Hybrid (DCF + Multiples)"

    def _extract_comparables(
        self,
        response: ValuationResponse,
    ) -> Optional[List[ComparableTransaction]]:
        """Extract comparable transactions."""
        if not response.multiples_valuation:
            return None

        mv = response.multiples_valuation
        if not hasattr(mv, "comparable_companies") or not mv.comparable_companies:
            return None

        comparables = []
        for comp in mv.comparable_companies[:5]:  # Max 5
            if hasattr(comp, "name"):
                comp_multiple = getattr(comp, "ev_ebitda", None)
                if comp_multiple is None:
                    continue
                comparables.append(
                    ComparableTransaction(
                        company=comp.name,
                        multiple=comp_multiple,
                        revenue=getattr(comp, "revenue", None),
                    )
                )

        return comparables if comparables else None

    def _build_accountant_branding(
        self,
        accountant: Optional[Dict[str, Any]],
    ) -> Optional[AccountantBranding]:
        """Build accountant branding from dict."""
        if not accountant:
            return None

        raw_mail = accountant.get("email")
        safe_mail = sanitize_report_email(raw_mail) if raw_mail is not None else None

        return AccountantBranding(
            firm_name=accountant.get("firm_name", accountant.get("firmName", "")),
            logo_url=accountant.get("logo_url", accountant.get("logoUrl")),
            website=accountant.get("website"),
            email=safe_mail,
        )


import threading

_transformer: Optional[ReportDataTransformer] = None
_orchestrator = None
_transformer_lock = threading.Lock()
_orchestrator_lock = threading.Lock()


def _get_orchestrator():
    """Lazy-load ReportTransformerOrchestrator to avoid circular imports."""
    global _orchestrator
    if _orchestrator is None:
        with _orchestrator_lock:
            if _orchestrator is None:
                from src.services.infrastructure.report_transformer.orchestrators.report_transformer_orchestrator import (
                    ReportTransformerOrchestrator,
                )

                _orchestrator = ReportTransformerOrchestrator()
    return _orchestrator


def transform_valuation_response(
    response: ValuationResponse,
    request: ValuationRequest,
) -> Dict[str, Any]:
    """
    Transform ValuationResponse to template-friendly data structure for Accountant View report.

    This function delegates to ReportTransformerOrchestrator for the actual transformation logic.

    Args:
        response: ValuationResponse containing valuation results
        request: Original ValuationRequest for context

    Returns:
        Dictionary with all template data for Accountant View report
    """
    return _get_orchestrator().transform_valuation_response(response, request)


def transform_for_info_tab(
    response: ValuationResponse,
    request: ValuationRequest,
) -> Dict[str, Any]:
    """
    Transform ValuationResponse to template-friendly data for Info Tab HTML generation.

    Backward-compatibility wrapper. Info Tab uses similar data to Accountant View;
    delegates to transform_valuation_response.

    Args:
        response: ValuationResponse containing calculation results
        request: Original ValuationRequest for context

    Returns:
        Dictionary with template data for Info Tab report
    """
    return transform_valuation_response(response, request)


def get_report_data_transformer() -> ReportDataTransformer:
    """Get or create singleton transformer instance. Thread-safe."""
    global _transformer
    if _transformer is None:
        with _transformer_lock:
            if _transformer is None:
                _transformer = ReportDataTransformer()
    return _transformer
