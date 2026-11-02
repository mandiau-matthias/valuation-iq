"""Buyer-ready package rendering route (Epic F / F3).

Titan owns orchestration and persistence. ValuationIQ owns the typed render
contract and Jinja output for screen/PDF HTML.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from src.domain.buyer_ready_models import (
    BuyerReadyPackageRender,
    ProvenanceRef,
    TaxLatencyRender,
    WCPegMonthlyPointRender,
    WCPegRender,
)
from src.middleware.auth import require_service_auth
from src.services.buyer_ready.tax_latency import TaxLatencySignals, compute_tax_latency
from src.services.buyer_ready.wc_peg import AnnualNWCPoint, MonthlyNWCPoint, compute_wc_peg
from src.services.infrastructure.exceptions import TemplateRenderingError
from src.services.infrastructure.template_service import get_template_service
from src.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(
    prefix="/buyer-ready-package",
    tags=["buyer-ready-package"],
    dependencies=[Depends(require_service_auth)],
)


class BuyerReadyPackageRenderResponse(BaseModel):
    """Rendered screen + PDF HTML assets for Titan persistence/export."""

    package_id: str
    generated_at: str
    html_report: str
    pdf_html_report: str


class MonthlyNWCPointInput(BaseModel):
    """Month-end operating NWC components from Hermes/Titan."""

    month: str
    receivables: float = 0.0
    inventory: float = 0.0
    prepaid_expenses: float = 0.0
    payables: float = 0.0
    accrued_expenses: float = 0.0
    deferred_revenue: float = 0.0


class AnnualNWCPointInput(BaseModel):
    """Annual fallback NWC point assembled by Titan."""

    year: int
    nwc: float


class TaxLatencySignalsInput(BaseModel):
    """Signals consulted by the deterministic BE/NL tax-latency rule set."""

    country_code: str
    accumulated_reserves: Optional[float] = None
    revalued_asset_book_value: Optional[float] = None
    revalued_asset_historical_cost: Optional[float] = None
    vendor_loan_balance: Optional[float] = None
    consolidated_goodwill: Optional[float] = None
    carry_forward_losses: Optional[float] = None
    owner_age: Optional[int] = None
    owner_compensation_annual: Optional[float] = None
    intercompany_management_fees: Optional[float] = None
    deal_type: Optional[str] = "unknown"
    employees_with_30pct_ruling_expiring_24m: Optional[int] = None


class BuyerReadyWcTaxRequest(BaseModel):
    """Pure F5 computation request. Titan owns persistence/audit."""

    package_id: str
    generated_at: str
    monthly_series: List[MonthlyNWCPointInput] = []
    annual_series: List[AnnualNWCPointInput] = []
    tax_signals: TaxLatencySignalsInput
    advisor_override_value: Optional[int] = None
    advisor_override_reason: Optional[str] = None


class BuyerReadyWcTaxSourceSignals(BaseModel):
    monthlyPointCount: int
    annualPointCount: int
    taxSignalKeys: List[str]


class BuyerReadyWcTaxResponse(BaseModel):
    wc_peg: Optional[WCPegRender] = None
    tax_latency: TaxLatencyRender
    source_signals: BuyerReadyWcTaxSourceSignals


@router.post(
    "/render",
    status_code=status.HTTP_200_OK,
    response_model=BuyerReadyPackageRenderResponse,
    summary="Render buyer-ready package HTML assets",
    description=(
        "Render the Stage 5 buyer-ready package from Titan's locked "
        "BuyerReadyPackageRender payload. Returns screen HTML and PDF HTML; "
        "DOCX/PDF export orchestration stays in Titan."
    ),
)
async def render_buyer_ready_package(
    package: BuyerReadyPackageRender,
) -> BuyerReadyPackageRenderResponse:
    template_service = get_template_service()

    try:
        html_report = template_service.render_buyer_ready_package(package, variant="screen")
        pdf_html_report = template_service.render_buyer_ready_package(package, variant="pdf")
    except TemplateRenderingError as exc:
        logger.error(
            "buyer_ready_package_render_failed",
            extra={
                "package_id": package.package_id,
                "error_type": type(exc).__name__,
                "error_message": str(exc),
            },
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc

    return BuyerReadyPackageRenderResponse(
        package_id=package.package_id,
        generated_at=package.generated_at,
        html_report=html_report,
        pdf_html_report=pdf_html_report,
    )


@router.post(
    "/wc-tax",
    status_code=status.HTTP_200_OK,
    response_model=BuyerReadyWcTaxResponse,
    summary="Compute buyer-ready WC peg and tax-latency flags",
    description=(
        "Pure F5 math endpoint. Titan assembles the signals, calls this "
        "contract, then persists buyer_ready_wc_tax and audit events."
    ),
)
async def compute_buyer_ready_wc_tax(
    payload: BuyerReadyWcTaxRequest,
) -> BuyerReadyWcTaxResponse:
    provenance = ProvenanceRef(
        source="computed",
        source_id=payload.package_id,
        computed_at=payload.generated_at,
    )
    as_of = _parse_generated_at(payload.generated_at)
    wc_result = compute_wc_peg(
        [
            MonthlyNWCPoint(
                month=point.month,
                receivables=point.receivables,
                inventory=point.inventory,
                prepaid_expenses=point.prepaid_expenses,
                payables=point.payables,
                accrued_expenses=point.accrued_expenses,
                deferred_revenue=point.deferred_revenue,
            )
            for point in payload.monthly_series
        ],
        [AnnualNWCPoint(year=point.year, nwc=point.nwc) for point in payload.annual_series],
        as_of,
    )
    tax_result = compute_tax_latency(
        TaxLatencySignals(
            country_code="NL" if payload.tax_signals.country_code.upper() == "NL" else "BE",
            accumulated_reserves=payload.tax_signals.accumulated_reserves,
            revalued_asset_book_value=payload.tax_signals.revalued_asset_book_value,
            revalued_asset_historical_cost=payload.tax_signals.revalued_asset_historical_cost,
            vendor_loan_balance=payload.tax_signals.vendor_loan_balance,
            consolidated_goodwill=payload.tax_signals.consolidated_goodwill,
            carry_forward_losses=payload.tax_signals.carry_forward_losses,
            owner_age=payload.tax_signals.owner_age,
            owner_compensation_annual=payload.tax_signals.owner_compensation_annual,
            intercompany_management_fees=payload.tax_signals.intercompany_management_fees,
            deal_type=_normalise_deal_type(payload.tax_signals.deal_type),
            employees_with_30pct_ruling_expiring_24m=payload.tax_signals.employees_with_30pct_ruling_expiring_24m,
        )
    )

    wc_peg = None
    if wc_result is not None:
        wc_peg = WCPegRender(
            target_eur=wc_result.target_eur,
            band_low_eur=wc_result.band_low_eur,
            band_high_eur=wc_result.band_high_eur,
            one_liner=wc_result.one_liner,
            monthly_series=[
                WCPegMonthlyPointRender(month=point.month, nwc_eur=int(round(point.nwc)))
                for point in wc_result.monthly_series
            ],
            derived_from=wc_result.derived_from,
            confidence=wc_result.confidence,
            advisor_override_value=payload.advisor_override_value,
            advisor_override_reason=payload.advisor_override_reason,
            provenance=provenance,
        )

    return BuyerReadyWcTaxResponse(
        wc_peg=wc_peg,
        tax_latency=TaxLatencyRender(
            jurisdiction=tax_result.jurisdiction,
            flags=[
                {
                    "rule_id": flag.rule_id,
                    "jurisdiction": flag.jurisdiction,
                    "label": flag.label,
                    "rationale": flag.rationale,
                    "estimated_impact_eur": flag.estimated_impact_eur,
                    "severity": flag.severity,
                    "provenance": provenance,
                }
                for flag in tax_result.flags
            ],
            flag_count=tax_result.flag_count,
        ),
        source_signals=BuyerReadyWcTaxSourceSignals(
            monthlyPointCount=len(payload.monthly_series),
            annualPointCount=len(payload.annual_series),
            taxSignalKeys=[
                key
                for key, value in payload.tax_signals.model_dump().items()
                if key != "country_code" and value is not None and value != "unknown"
            ],
        ),
    )


def _parse_generated_at(value: str) -> datetime:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return datetime.utcnow()


def _normalise_deal_type(value: Optional[str]) -> str:
    if not value:
        return "unknown"
    normalised = value.strip().lower()
    if "asset" in normalised:
        return "asset"
    if "share" in normalised or "stock" in normalised:
        return "share"
    return "unknown"
