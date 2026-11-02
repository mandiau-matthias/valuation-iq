"""Evidence labels for automatic DCF estimates; no valuation arithmetic."""

from src.api.schemas.forecast_evidence import ForecastEvidence
from src.services.reports.verified_forecast_projection import apply_verified_forecast_projection


def label_forecast_output(
    calculated: dict[str, object], forecast: ForecastEvidence | None
) -> dict[str, object]:
    if forecast is not None:
        result = apply_verified_forecast_projection(calculated, forecast)
        result["forecast_evidence_status"] = "source_verified"
        return result
    result = dict(calculated)
    result["forecast_evidence_status"] = "unverified_indicative"
    assumptions = result.get("market_assumptions")
    result["market_assumptions"] = {
        **(assumptions if isinstance(assumptions, dict) else {}),
        "forecast_evidence_status": "unverified_indicative",
        "forecast_source_verification": False,
    }
    warnings = result.get("data_quality_warnings")
    result["data_quality_warnings"] = [
        *(warnings if isinstance(warnings, list) else []),
        {
            "type": "indicative_dcf_forecast",
            "severity": "warning",
            "message": (
                "Indicative DCF based on supplied or modeled cash-flow assumptions. "
                "The company forecast has not been source-verified."
            ),
            "recommendation": (
                "Review cash flows, taxes, reinvestment and terminal assumptions "
                "against company evidence before relying on this estimate."
            ),
        },
    ]
    return result
