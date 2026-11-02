"""Render the verified company cash-flow schedule without historical placeholders."""

from decimal import Decimal, localcontext

from src.api.schemas.forecast_evidence import ForecastEvidence


def apply_verified_forecast_projection(
    calculated: dict[str, object],
    forecast: ForecastEvidence,
) -> dict[str, object]:
    result = dict(calculated)
    with localcontext() as context:
        context.prec = 60
        result["fcf_projection_detail"] = [
            {
                "year": period.end_date.year,
                "revenue": period.revenue,
                "ebitda": period.ebitda,
                "ebit": format(
                    Decimal(period.ebitda)
                    - Decimal(period.depreciation)
                    - Decimal(period.amortization),
                    "f",
                ),
                "depreciation": period.depreciation,
                "amortization": period.amortization,
                "taxes": period.cash_taxes,
                "tax_basis": "cash_taxes",
                "capex": period.capex,
                "nwc_change": period.change_in_operating_nwc,
                "free_cash_flow": period.free_cash_flow,
                "confidence_score": None,
                "source_document_hash": period.source_document_hash,
            }
            for period in forecast.periods
        ]
    result["forecast_evidence_content_hash"] = forecast.content_hash
    return result
