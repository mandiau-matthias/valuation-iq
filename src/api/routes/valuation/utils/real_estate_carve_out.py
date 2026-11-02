"""
Real-estate transaction perimeter normalization.

Keeps the going-concern carve-out policy isolated from general request-field
normalization so the request utility module stays a facade.
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Dict, List

from src.api.legacy_schemas import BalanceSheetAdjustmentInput
from src.api.schemas import ValuationRequest
from src.api.routes.valuation.utils.legacy_value_governance import (
    governed_real_estate_perimeter_decision,
)


@dataclass(frozen=True)
class RealEstatePerimeter:
    treatment: str
    property_value: Decimal
    market_rent: Decimal
    locale: Any


def _unpriced_real_estate_request(
    request: ValuationRequest,
    perimeter: RealEstatePerimeter,
) -> ValuationRequest:
    metadata = dict(getattr(request, "metadata", None) or {})
    metadata["unpriced_real_estate_scenario"] = {
        "treatment": perimeter.treatment,
        "book_value": perimeter.property_value,
        "market_value": getattr(request, "real_estate_market_value", None),
        "estimated_market_rent": perimeter.market_rent,
        "currency": getattr(request, "currency", None),
        "status": "scenario_only_unverified",
        "qualification": (
            "Real-estate perimeter economics were excluded from the priced v1 value. "
            "Legacy requests cannot create authoritative monetary decisions."
        ),
    }
    warnings = list(metadata.get("legacy_value_governance_warnings") or [])
    warnings.append(
        {
            "type": "unverified_real_estate_perimeter",
            "severity": "high",
            "message": (
                "The requested real-estate perimeter is disclosed as a scenario only "
                "and did not change EBITDA or equity value."
            ),
            "recommendation": (
                "Use the canonical v2 path with a Titan-signed, evidence-bound "
                "perimeter decision before pricing it."
            ),
            "details": {"treatment": perimeter.treatment, "step_number": 7},
        }
    )
    metadata["legacy_value_governance_warnings"] = warnings
    return request.model_copy(
        update={
            "real_estate_treatment": "none",
            "exclude_real_estate": False,
            "real_estate_book_value": None,
            "real_estate_market_value": None,
            "estimated_market_rent": None,
            "metadata": metadata,
        }
    )


def _build_real_estate_adjustment_label(locale: Any) -> str:
    return (
        "Vastgoed carve-out"
        if str(locale or "").lower().startswith("nl")
        else "Real estate carve-out"
    )


def _build_real_estate_inclusion_label(locale: Any, surplus: Decimal) -> str:
    if str(locale or "").lower().startswith("nl"):
        return (
            "Vastgoed inclusief - meerwaarde"
            if surplus >= 0
            else "Vastgoed inclusief - minderwaarde"
        )
    return (
        "Real estate included - surplus value"
        if surplus >= 0
        else "Real estate included - shortfall"
    )


def _normalize_real_estate_treatment(request: ValuationRequest) -> str:
    raw_treatment = getattr(request, "real_estate_treatment", None)
    if raw_treatment is not None and str(raw_treatment).strip() != "":
        normalized = str(raw_treatment).strip().lower().replace("-", "_").replace(" ", "_")
        if normalized in {"included", "include", "vastgoed_inclusief", "real_estate_included"}:
            return "included"
        if normalized in {"carve_out", "vastgoed_carve_out", "exclude", "excluded"}:
            return "carve_out"
        if normalized in {"none", "geen", "geen_vastgoed", "no_real_estate"}:
            return "none"

    return "carve_out" if getattr(request, "exclude_real_estate", False) else "none"


def _real_estate_perimeter(request: ValuationRequest) -> RealEstatePerimeter:
    return RealEstatePerimeter(
        treatment=_normalize_real_estate_treatment(request),
        property_value=Decimal(str(getattr(request, "real_estate_book_value", None) or 0)),
        market_rent=Decimal(str(getattr(request, "estimated_market_rent", None) or 0)),
        locale=getattr(request, "locale", None),
    )


def _has_adjustment(adjustments: list[Any], adjustment_id: str) -> bool:
    return any(getattr(adj, "id", None) == adjustment_id for adj in adjustments)


def _market_rent_already_applied(year_data: Any) -> bool:
    meta = getattr(year_data, "ebitda_normalization_metadata", None)
    if not isinstance(meta, dict):
        return False
    for entry in meta.get("adjustments") or []:
        if isinstance(entry, dict) and entry.get("category") == "real_estate_carve_out":
            return True
    return False


def _apply_real_estate_inclusion_adjustment(request: ValuationRequest) -> ValuationRequest:
    market_value = Decimal(str(getattr(request, "real_estate_market_value", None) or 0))
    book_value = Decimal(str(getattr(request, "real_estate_book_value", None) or 0))
    surplus = market_value - book_value
    if surplus == 0:
        return request

    existing_adjustments = list(getattr(request, "balance_sheet_adjustments", None) or [])
    if _has_adjustment(existing_adjustments, "real_estate_inclusion_surplus"):
        return request

    locale = getattr(request, "locale", None)
    existing_adjustments.append(
        BalanceSheetAdjustmentInput(
            id="real_estate_inclusion_surplus",
            label=_build_real_estate_inclusion_label(locale, surplus),
            amount=abs(surplus),
            type="add" if surplus > 0 else "subtract",
            category="non_operating",
            description=(
                "Real estate transfers with the operating company; equity value reflects market value less book value."
                if not str(locale or "").lower().startswith("nl")
                else "Vastgoed gaat mee over met de werkvennootschap; equity value weerspiegelt marktwaarde min boekwaarde."
            ),
        )
    )

    return request.model_copy(update={"balance_sheet_adjustments": existing_adjustments})


def _append_market_rent_adjustment_metadata(
    year_data: Any,
    market_rent: Decimal,
    locale: Any,
) -> Dict[str, Any]:
    existing_meta = getattr(year_data, "ebitda_normalization_metadata", None)
    metadata = dict(existing_meta) if isinstance(existing_meta, dict) else {}
    adjustments = (
        list(metadata.get("adjustments", []))
        if isinstance(metadata.get("adjustments"), list)
        else []
    )
    adjustments.append(
        {
            "label": (
                "Fictieve huur"
                if str(locale or "").lower().startswith("nl")
                else "Estimated market rent"
            ),
            "amount": market_rent,
            "type": "subtract",
            "category": "real_estate_carve_out",
        }
    )

    original_ebitda = getattr(year_data, "ebitda", Decimal("0")) or Decimal("0")
    reported_ebitda = metadata.get("reported_ebitda", original_ebitda)
    previous_total = metadata.get("total_adjustments", Decimal("0")) or Decimal("0")
    previous_count = metadata.get("adjustment_count", 0) or 0

    metadata.update(
        {
            "reported_ebitda": reported_ebitda,
            "total_adjustments": Decimal(str(previous_total)) - market_rent,
            "adjustment_count": int(previous_count) + 1,
            "has_custom_adjustments": True,
            "normalized_ebitda": Decimal(str(reported_ebitda))
            + (Decimal(str(previous_total)) - market_rent),
            "adjustments": adjustments,
        }
    )
    return metadata


def _real_estate_carve_out_bsa_row(
    perimeter: RealEstatePerimeter,
    decision: dict[str, object],
) -> BalanceSheetAdjustmentInput:
    return BalanceSheetAdjustmentInput(
        id="real_estate_carve_out",
        label=_build_real_estate_adjustment_label(perimeter.locale),
        amount=perimeter.property_value,
        type="subtract",
        category="non_operating",
        description=(
            "Seller-owned real estate excluded from the transaction."
            if not str(perimeter.locale or "").lower().startswith("nl")
            else "Verkopersvastgoed uitgesloten uit de transactie."
        ),
        status=str(decision.get("status") or decision.get("state") or "accepted"),
        evidence_id=str(decision.get("evidence_id") or ""),
        reviewed_at=str(decision.get("reviewed_at") or decision.get("decided_at") or ""),
        rule_version=str(decision.get("rule_version") or ""),
        approved_by=str(decision.get("approved_by") or decision.get("decided_by") or ""),
        currency=str(decision.get("currency") or ""),
    )


def _balance_sheet_adjustment_updates(
    request: ValuationRequest,
    perimeter: RealEstatePerimeter,
    decision: dict[str, object],
) -> Dict[str, Any]:
    if perimeter.property_value <= 0:
        return {}

    existing_adjustments = list(getattr(request, "balance_sheet_adjustments", None) or [])
    if _has_adjustment(existing_adjustments, "real_estate_carve_out"):
        return {}

    existing_adjustments.append(_real_estate_carve_out_bsa_row(perimeter, decision))
    return {"balance_sheet_adjustments": existing_adjustments}


def _year_ebitda_after_market_rent(year_data: Any, market_rent: Decimal) -> Decimal:
    return (getattr(year_data, "ebitda", Decimal("0")) or Decimal("0")) - market_rent


def _market_rent_year_updates(
    year_data: Any,
    perimeter: RealEstatePerimeter,
    *,
    ebitda_override: Decimal | None = None,
) -> Dict[str, Any]:
    return {
        "ebitda": (
            ebitda_override
            if ebitda_override is not None
            else _year_ebitda_after_market_rent(year_data, perimeter.market_rent)
        ),
        "ebitda_normalized": True,
        "ebitda_normalization_metadata": _append_market_rent_adjustment_metadata(
            year_data,
            perimeter.market_rent,
            perimeter.locale,
        ),
    }


def _adjust_forecast_years_for_market_rent(
    request: ValuationRequest,
    perimeter: RealEstatePerimeter,
) -> List[Any]:
    return [
        forecast_year.model_copy(update=_market_rent_year_updates(forecast_year, perimeter))
        for forecast_year in list(getattr(request, "forecast_years_data", None) or [])
    ]


def _same_fiscal_year(left: Any, right: Any) -> bool:
    if left is None or right is None:
        return False
    try:
        return int(left) == int(right)
    except (TypeError, ValueError):
        return False


def _adjust_historical_years_for_market_rent(
    request: ValuationRequest,
    perimeter: RealEstatePerimeter,
    *,
    adjusted_current_ebitda: Decimal,
) -> List[Any]:
    current_year = request.current_year_data
    current_fiscal_year = getattr(current_year, "year", None) if current_year is not None else None
    adjusted_historical = []

    for historical_year in list(getattr(request, "historical_years_data", None) or []):
        if getattr(historical_year, "is_forecast", False):
            adjusted_historical.append(historical_year)
            continue

        if _same_fiscal_year(getattr(historical_year, "year", None), current_fiscal_year):
            adjusted_historical.append(
                historical_year.model_copy(
                    update=_market_rent_year_updates(
                        historical_year,
                        perimeter,
                        ebitda_override=adjusted_current_ebitda,
                    )
                )
            )
            continue

        adjusted_historical.append(
            historical_year.model_copy(update=_market_rent_year_updates(historical_year, perimeter))
        )

    return adjusted_historical


def _market_rent_updates(
    request: ValuationRequest,
    perimeter: RealEstatePerimeter,
) -> Dict[str, Any]:
    current_year = request.current_year_data
    if perimeter.market_rent <= 0 or _market_rent_already_applied(current_year):
        return {}

    updates: Dict[str, Any] = {}
    adjusted_current_ebitda = _year_ebitda_after_market_rent(
        current_year,
        perimeter.market_rent,
    )
    if current_year is not None:
        updates["current_year_data"] = current_year.model_copy(
            update=_market_rent_year_updates(
                current_year,
                perimeter,
                ebitda_override=adjusted_current_ebitda,
            )
        )

    adjusted_forecasts = _adjust_forecast_years_for_market_rent(request, perimeter)
    if adjusted_forecasts:
        updates["forecast_years_data"] = adjusted_forecasts

    historical_years = list(getattr(request, "historical_years_data", None) or [])
    if historical_years:
        updates["historical_years_data"] = _adjust_historical_years_for_market_rent(
            request,
            perimeter,
            adjusted_current_ebitda=adjusted_current_ebitda,
        )

    return updates


def apply_real_estate_carve_out(request: ValuationRequest) -> ValuationRequest:
    """Apply real-estate transaction perimeter logic.

    For ``real_estate_treatment='included'`` the property transfers with the
    OpCo, so EBITDA is left untouched and only the market-vs-book surplus is
    added to the equity bridge.

    For ``real_estate_treatment='carve_out'`` (or legacy
    ``exclude_real_estate=True``), the carve-out is a *going-concern equity
    bridge* — it expresses that the building doesn't transfer with the
    operating company. It applies to income methods via two channels:

      1. **Equity bridge** — emit a ``balance_sheet_adjustment`` row.
      2. **EBITDA normalization** — strip fictive market rent from EBITDA.

    It deliberately does not mutate ``current_year_data.total_assets`` or
    ``total_equity`` because liquidation, WACC, and adjusted NAV own those
    balance-sheet lenses.
    """
    perimeter = _real_estate_perimeter(request)
    if perimeter.treatment == "none":
        return request
    decision = governed_real_estate_perimeter_decision(
        request,
        treatment=perimeter.treatment,
    )
    if decision is None:
        return _unpriced_real_estate_request(request, perimeter)
    if perimeter.treatment == "included":
        return _apply_real_estate_inclusion_adjustment(request)
    if perimeter.treatment != "carve_out":
        return request
    if perimeter.property_value <= 0 and perimeter.market_rent <= 0:
        return request

    updates = {
        **_balance_sheet_adjustment_updates(request, perimeter, dict(decision)),
        **_market_rent_updates(request, perimeter),
    }
    return request.model_copy(update=updates) if updates else request
