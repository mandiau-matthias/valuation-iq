"""Governed real-estate transaction-perimeter economics for stateless valuations."""

from __future__ import annotations

from decimal import Decimal

from src.api.schemas.stateless_api import CalculateRequest, TriageFlag, YearDataStateless
from src.utils.decimal_helpers import safe_decimal_or_zero

_REAL_ESTATE_DECISION_FIELDS = {
    "real_estate_treatment",
    "real_estate_perimeter",
    "real_estate_carve_out",
}
_REAL_ESTATE_DECISION_CATEGORIES = {
    "transaction_perimeter",
    "real_estate",
    "structural_adjustment",
}


def apply_stateless_real_estate_perimeter(
    request: CalculateRequest,
) -> tuple[CalculateRequest, list[TriageFlag]]:
    treatment = request.real_estate_treatment
    canonical_treatment = {
        "included": "owned_included",
        "carve_out": "owned_excluded",
    }.get(treatment, treatment)
    if canonical_treatment in (None, "none", "leased"):
        # A leased operation already carries actual rent in reported earnings.
        # Any lease liability belongs in the completion-account bridge, where
        # it is deducted once and remains null when unresolved.
        return request, []

    if canonical_treatment == "unresolved":
        return request, [
            TriageFlag(
                field="real_estate_treatment",
                issue="real_estate_perimeter_unresolved_no_adjustment",
                severity="warning",
            )
        ]

    decision = _governed_real_estate_decision(request)
    market_rent = safe_decimal_or_zero(request.estimated_market_rent)
    if decision is None or market_rent <= 0:
        metadata = dict(request.metadata or {})
        metadata["unpriced_real_estate_scenario"] = {
            "treatment": canonical_treatment,
            "market_value": request.real_estate_market_value,
            "book_value": request.real_estate_book_value,
            "estimated_market_rent": request.estimated_market_rent,
            "currency": request.currency,
            "status": (
                "market_rent_unresolved"
                if decision is not None
                else "scenario_only_unverified"
            ),
        }
        return (
            request.model_copy(
                update={
                    "real_estate_treatment": "unresolved",
                    "real_estate_market_value": None,
                    "real_estate_book_value": None,
                    "estimated_market_rent": None,
                    "metadata": metadata,
                }
            ),
            [
                TriageFlag(
                    field="real_estate_treatment",
                    issue=(
                        "real_estate_market_rent_unresolved_no_adjustment"
                        if decision is not None
                        else "unverified_real_estate_perimeter_scenario_only"
                    ),
                    severity="warning",
                )
            ],
        )

    current_year = _apply_market_rent(
        request.current_year,
        rent=market_rent,
        request=request,
        decision=decision,
        direct=False,
    )
    historical_years = [
        _apply_market_rent(
            year,
            rent=market_rent,
            request=request,
            decision=decision,
            direct=True,
        )
        for year in request.historical_years
    ]

    # Historical code also subtracted property book value as a balance-sheet
    # adjustment. That double counted the perimeter change: the rent-adjusted
    # operating EV already excludes property. Owned/included adds the full
    # appraised market value once later; owned/excluded adds nothing.
    adjustments = [
        row
        for row in (request.balance_sheet_adjustments or [])
        if row.id != "real_estate_carve_out"
    ]
    metadata = dict(request.metadata or {})
    metadata["real_estate_economic_treatment"] = {
        "treatment": canonical_treatment,
        "operating_earnings_charge": market_rent,
        "property_bridge_value": (
            request.real_estate_market_value
            if canonical_treatment == "owned_included"
            else Decimal("0")
        ),
        "book_value_used_in_bridge": False,
        "lease_liability_bridge": canonical_treatment == "leased",
        "evidence_id": decision.evidence_id,
    }

    return (
        request.model_copy(
            update={
                "real_estate_treatment": canonical_treatment,
                "current_year": current_year,
                "historical_years": historical_years,
                "balance_sheet_adjustments": adjustments,
                "metadata": metadata,
            }
        ),
        [],
    )


def _governed_real_estate_decision(request: CalculateRequest) -> object | None:
    case = request.valuation_case
    if case is None or not case.evidence_revision_id or not request.currency:
        return None
    for decision in case.authoritative_input_decisions:
        if (
            decision.state in {"accepted", "edited"}
            and decision.field_key.strip().lower() in _REAL_ESTATE_DECISION_FIELDS
            and decision.category.strip().lower() in _REAL_ESTATE_DECISION_CATEGORIES
            and decision.evidence_id
            and decision.rule_version
            and decision.decided_by
            and decision.decided_at is not None
            and decision.currency == request.currency
        ):
            return decision
    return None


def _apply_market_rent(
    year: YearDataStateless,
    *,
    rent: Decimal,
    request: CalculateRequest,
    decision: object,
    direct: bool,
) -> YearDataStateless:
    if rent <= 0:
        return year
    metadata = dict(year.ebitda_normalization_metadata or {})
    adjustments = list(metadata.get("adjustments") or [])
    adjustment_id = f"real_estate_market_rent_{year.year}"
    if any(
        isinstance(row, dict) and row.get("id") == adjustment_id for row in adjustments
    ):
        return year

    original = safe_decimal_or_zero(
        year.reported_ebitda if year.reported_ebitda is not None else year.ebitda
    )
    adjustments.append(
        {
            "id": adjustment_id,
            "field": "real_estate_carve_out",
            "label": "Estimated market rent",
            "amount": rent,
            "signed_amount": -rent,
            "type": "subtract",
            "category": "real_estate_carve_out",
            "status": "accepted",
            "evidence_id": getattr(decision, "evidence_id"),
            "reviewed_at": getattr(decision, "decided_at").isoformat(),
            "rule_version": getattr(decision, "rule_version"),
            "currency": request.currency,
        }
    )
    metadata.update(
        {
            "reported_ebitda": original,
            "normalized_ebitda": original - rent,
            "adjustments": adjustments,
        }
    )
    updates: dict[str, object] = {
        "reported_ebitda": original,
        "normalized_ebitda": original - rent,
        "ebitda_normalized": True,
        "ebitda_normalization_metadata": metadata,
    }
    if direct:
        updates["ebitda"] = original - rent
    return year.model_copy(update=updates)
