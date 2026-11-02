"""Evidence-aware annual EBITDA normalization and weighting for stateless valuations."""

from __future__ import annotations

from decimal import Decimal
from typing import Mapping

from src.api.schemas.stateless_api import CalculateRequest, TriageFlag, YearDataStateless
from src.config.valuation_constants import recency_weights
from src.domain.multiples.advisor_controls import NON_APPLIED_EBITDA_ADJUSTMENT_STATUSES
from src.domain.multiples.owner_compensation_delta import owner_compensation_delta
from src.services.reports.stateless_calculation_helpers import filter_usable_actual_years
from src.services.reports.stateless_earnings_basis_models import StatelessEarningsBasis
from src.utils.decimal_helpers import safe_decimal_or_zero

_APPLIED_NORMALIZATION_STATUSES = {
    "accepted",
    "approved",
    "applied",
    "confirmed",
    "verified",
}
_NORMALIZATION_DECISION_CATEGORIES = {
    "ebitda_normalization",
    "normalization",
    "operating_normalization",
    "one_time",
    "one_time_expenses",
    "non_recurring",
    "non_recurring_revenue",
    "owner_compensation",
    "owner_compensation_adjustment",
    "private_expense",
    "related_party_transactions",
    "rent_normalization",
    "other_adjustments",
}


def _governed_legacy_adjustment(
    raw: Mapping[str, object],
    *,
    valuation_currency: str | None,
) -> bool:
    """Legacy client rows are scenarios, never authoritative monetary decisions.

    IDs, timestamps and reviewer-looking strings are caller-controlled fields;
    their presence cannot authenticate an accepted adjustment. Canonical
    economics enter through Titan's signed ``ValuationInputDecision v2`` list.
    A future engine-owned policy lane must use a separate typed contract and an
    explicit allow-listed policy registry rather than re-enable this envelope.
    """

    del raw, valuation_currency
    return False


def _governed_canonical_decision(
    decision: object,
    *,
    valuation_currency: str | None,
) -> bool:
    currency = str(getattr(decision, "currency", None) or "").strip().upper()
    return bool(
        str(getattr(decision, "decision_id", None) or "").strip()
        and str(getattr(decision, "evidence_id", None) or "").strip()
        and str(getattr(decision, "rule_version", None) or "").strip()
        and str(getattr(decision, "decided_by", None) or "").strip()
        and getattr(decision, "decided_at", None) is not None
        and currency
        and valuation_currency
        and currency == valuation_currency
    )


def _governed_typed_adjustment(
    adjustment: object,
    *,
    valuation_currency: str | None,
) -> bool:
    # This top-level Venus/Titan transport is retained for audit/scenario
    # parity only. It is not signed authority and must never price by itself.
    del adjustment, valuation_currency
    return False


def _canonical_decision_signed_amount(decision: object) -> Decimal | None:
    """Return an exact monetary delta committed by a signed v2 decision.

    Most normalization decisions use the scalar ``signed_amount``. Owner
    compensation is a composite economic identity, so Titan commits the actual
    pay, replacement pay, owner role and delta together in ``value_payload``.
    The composite is priced only when all terms reconcile exactly.
    """

    category = _status(getattr(decision, "category", None))
    if category not in {"owner_compensation", "owner_compensation_adjustment"}:
        direct = getattr(decision, "signed_amount", None)
        return safe_decimal_or_zero(direct) if direct is not None else None
    return owner_compensation_delta(getattr(decision, "value_payload", None))


def resolve_stateless_earnings_basis(request: CalculateRequest) -> StatelessEarningsBasis:
    """Normalize each actual year first, then apply the disclosed year weights."""
    annual_rows = _annual_rows(request)
    selected, weights, mode, flags = _select_rows_and_weights(request, annual_rows)
    current_result = _normalize_year(
        request.current_year,
        decisions=_decisions_for_year(request, request.current_year.year),
        contract_adjustments=_contract_adjustments_for_year(
            request,
            request.current_year.year,
        ),
        valuation_currency=request.currency,
    )
    rows: list[dict[str, object]] = []
    weighted_reported = Decimal("0")
    weighted_normalized = Decimal("0")
    for year_data, weight in zip(selected, weights):
        year_result = _normalize_year(
            year_data,
            decisions=_decisions_for_year(request, year_data.year),
            contract_adjustments=_contract_adjustments_for_year(
                request,
                year_data.year,
            ),
            valuation_currency=request.currency,
        )
        reported = safe_decimal_or_zero(year_result["reported_ebitda"])
        normalized = safe_decimal_or_zero(year_result["normalized_ebitda"])
        weighted_reported += reported * weight
        weighted_normalized += normalized * weight
        rows.append(
            {
                **year_result,
                "weight": weight,
                "weighted_reported_ebitda": reported * weight,
                "weighted_normalized_ebitda": normalized * weight,
            }
        )
        if year_result.get("reported_basis_missing_for_adjustments"):
            flags.append(
                TriageFlag(
                    field=f"financials.{year_data.year}.reported_ebitda",
                    issue="normalization_unpriced_reported_basis_missing",
                    severity="warning",
                )
            )
        pending_rows = year_result.get("pending_adjustments")
        if isinstance(pending_rows, list) and pending_rows:
            flags.append(
                TriageFlag(
                    field=f"financials.{year_data.year}.normalizations",
                    issue="unaccepted_normalizations_excluded_from_priced_basis",
                    severity="warning",
                    value={
                        "count": len(pending_rows),
                        "ids": [
                            row.get("id")
                            for row in pending_rows
                            if isinstance(row, Mapping) and row.get("id")
                        ],
                    },
                )
            )
            for issue, status_value in (
                ("normalization_currency_mismatch_unpriced", "unpriced_currency_mismatch"),
                ("ambiguous_duplicate_normalization_unpriced", "duplicate_transport_ambiguous"),
                ("normalization_governance_missing_unpriced", "scenario_only_unverified"),
                ("normalization_currency_unresolved_unpriced", "unpriced_currency_unresolved"),
            ):
                affected = [
                    row
                    for row in pending_rows
                    if isinstance(row, Mapping) and row.get("status") == status_value
                ]
                if affected:
                    flags.append(
                        TriageFlag(
                            field=f"financials.{year_data.year}.normalizations",
                            issue=issue,
                            severity="warning",
                            value={"count": len(affected)},
                        )
                    )

    return StatelessEarningsBasis(
        normalized_ebitda=weighted_normalized,
        reported_ebitda=weighted_reported,
        current_normalized_ebitda=safe_decimal_or_zero(current_result["normalized_ebitda"]),
        current_reported_ebitda=safe_decimal_or_zero(current_result["reported_ebitda"]),
        mode=mode,
        rows=rows,
        triage_flags=flags,
    )


def with_normalized_actual_earnings(request: CalculateRequest) -> CalculateRequest:
    """Return an internal method-input copy with accepted annual EBITDA applied.

    Reported fields stay untouched. Only the method driver ``ebitda`` on actual
    years is replaced, ensuring DCF forecasts and market methods start from the
    same evidence-linked normalized annual facts.
    """

    def normalized(row: YearDataStateless) -> YearDataStateless:
        result = _normalize_year(
            row,
            decisions=_decisions_for_year(request, row.year),
            contract_adjustments=_contract_adjustments_for_year(request, row.year),
            valuation_currency=request.currency,
        )
        normalized_ebitda = safe_decimal_or_zero(result["normalized_ebitda"])
        return row.model_copy(
            update={
                "ebitda": normalized_ebitda,
                "normalized_ebitda": normalized_ebitda,
                "ebitda_normalized": True,
            }
        )

    current_year = normalized(request.current_year)
    historical_years = [
        row if row.is_forecast else normalized(row) for row in request.historical_years
    ]
    return request.model_copy(
        update={
            "current_year": current_year,
            "historical_years": historical_years,
        }
    )


def _annual_rows(request: CalculateRequest) -> list[YearDataStateless]:
    by_year: dict[int, YearDataStateless] = {}
    for row in filter_usable_actual_years(request.historical_years):
        existing = by_year.get(row.year)
        if existing is not None and existing.model_dump() != row.model_dump():
            raise ValueError(
                f"conflicting actual financial observations for fiscal year {row.year}"
            )
        by_year[row.year] = row
    existing = by_year.get(request.current_year.year)
    if existing is not None and existing.model_dump() != request.current_year.model_dump():
        raise ValueError(
            f"conflicting actual financial observations for fiscal year {request.current_year.year}"
        )
    by_year[request.current_year.year] = request.current_year
    return [by_year[year] for year in sorted(by_year)]


def _select_rows_and_weights(
    request: CalculateRequest,
    rows: list[YearDataStateless],
) -> tuple[list[YearDataStateless], list[Decimal], str, list[TriageFlag]]:
    if request.historical_ebitda_weighting_mode == "current_year":
        return [request.current_year], [Decimal("1")], "current_year", []

    custom = request.historical_ebitda_weights or {}
    if request.historical_ebitda_weighting_mode == "weighted" and custom:
        by_year = {row.year: row for row in rows}
        missing = sorted(set(custom) - set(by_year))
        if not missing:
            selected = [by_year[year] for year in sorted(custom)]
            total = sum(custom.values(), Decimal("0"))
            divisor = Decimal("100") if total > Decimal("1.5") else Decimal("1")
            normalized = [safe_decimal_or_zero(custom[row.year]) / divisor for row in selected]
            normalized_total = sum(normalized, Decimal("0"))
            if normalized_total > 0:
                normalized = [weight / normalized_total for weight in normalized]
                return selected, normalized, "advisor_weighted", []
        else:
            return _standard_selection(
                rows,
                flags=[
                    TriageFlag(
                        field="historical_ebitda_weights",
                        issue="weighted_years_missing_standard_fallback",
                        severity="warning",
                        value=missing,
                    )
                ],
            )
    return _standard_selection(rows)


def _standard_selection(
    rows: list[YearDataStateless],
    *,
    flags: list[TriageFlag] | None = None,
) -> tuple[list[YearDataStateless], list[Decimal], str, list[TriageFlag]]:
    selected = rows[-5:]
    weights = list(recency_weights(len(selected))) if selected else []
    return selected, weights, "recency_weighted", list(flags or [])


def _normalization_metadata(year_data: YearDataStateless) -> Mapping[str, object]:
    metadata = year_data.ebitda_normalization_metadata
    return metadata if isinstance(metadata, Mapping) else {}


def _status(value: object) -> str:
    return str(value or "").strip().lower().replace("-", " ").replace(" ", "_")


def _signed_adjustment(raw: Mapping[str, object]) -> tuple[Decimal, bool]:
    signed_input = raw.get("signed_amount")
    amount = safe_decimal_or_zero(signed_input if signed_input is not None else raw.get("amount"))
    adjustment_type = str(raw.get("type") or "add").strip().lower()
    if signed_input is None:
        amount = abs(amount)
        amount = (
            -amount if adjustment_type in {"subtract", "deduct", "minus", "negative"} else amount
        )
    status = _status(raw.get("status"))
    # A missing/unknown status is not an accepted decision. Legacy rows remain
    # visible as proposed scenarios but cannot change the priced EBITDA basis.
    applied = status in _APPLIED_NORMALIZATION_STATUSES
    if status in NON_APPLIED_EBITDA_ADJUSTMENT_STATUSES:
        applied = False
    return amount, applied


def _decisions_for_year(request: CalculateRequest, fiscal_year: int) -> list[object]:
    valuation_case = request.valuation_case
    if valuation_case is None:
        return []
    return [
        decision
        for decision in valuation_case.authoritative_input_decisions
        if decision.fiscal_year == fiscal_year
        and decision.category.strip().lower() in _NORMALIZATION_DECISION_CATEGORIES
    ]


def _contract_adjustments_for_year(
    request: CalculateRequest,
    fiscal_year: int,
) -> list[object]:
    return [
        adjustment
        for adjustment in request.normalizations
        if adjustment.fiscal_year == fiscal_year
        or (adjustment.fiscal_year is None and fiscal_year == request.current_year.year)
    ]


def _adjustment_content_key(
    *,
    label: object,
    evidence_id: object,
    signed_amount: object,
    currency: object,
) -> tuple[str, str, str, str]:
    return (
        str(label or "").strip().casefold(),
        str(evidence_id or "").strip(),
        format(safe_decimal_or_zero(signed_amount), "f"),
        str(currency or "").strip().upper(),
    )


def _adjustment_transport_key(
    *,
    evidence_id: object,
    signed_amount: object,
    currency: object,
    valuation_currency: str | None,
) -> tuple[str, str, str] | None:
    """Identify one economic row across canonical/legacy transport envelopes.

    Decision IDs and normalization IDs are intentionally separate namespaces.
    During dual-write, the stable cross-contract identity is therefore the
    evidence fact plus signed amount and currency.  Without evidence we refuse
    to infer identity from coincidentally equal labels/amounts.
    """
    evidence = str(evidence_id or "").strip()
    if not evidence:
        return None
    return (
        evidence,
        format(safe_decimal_or_zero(signed_amount), "f"),
        str(currency or valuation_currency or "").strip().upper(),
    )


def _normalize_year(
    year_data: YearDataStateless,
    *,
    decisions: list[object] | None = None,
    contract_adjustments: list[object] | None = None,
    valuation_currency: str | None = None,
) -> dict[str, object]:
    metadata = _normalization_metadata(year_data)
    explicit_reported = (
        year_data.reported_ebitda
        if year_data.reported_ebitda is not None
        else metadata.get("reported_ebitda")
    )
    reported = explicit_reported
    if reported is None:
        reported = year_data.ebitda
    reported_dec = safe_decimal_or_zero(reported)
    reported_basis_available = explicit_reported is not None or not year_data.ebitda_normalized

    raw_adjustments = metadata.get("adjustments")
    adjustments = raw_adjustments if isinstance(raw_adjustments, list) else []
    applied_rows: list[dict[str, object]] = []
    pending_rows: list[dict[str, object]] = []
    applied_total = Decimal("0")
    seen_adjustment_ids: set[str] = set()
    seen_unidentified_content: set[tuple[str, str, str, str]] = set()
    contract_adjustment_ids = {
        str(getattr(adjustment, "id", "") or "").strip()
        for adjustment in (contract_adjustments or [])
        if str(getattr(adjustment, "id", "") or "").strip()
    }
    authoritative_content_keys = {
        _adjustment_content_key(
            label=getattr(adjustment, "label", None),
            evidence_id=getattr(adjustment, "evidence_id", None),
            signed_amount=getattr(adjustment, "adjustment_amount", None),
            currency=getattr(adjustment, "currency", None),
        )
        for adjustment in (contract_adjustments or [])
    }
    authoritative_content_keys.update(
        _adjustment_content_key(
            label=getattr(decision, "field_key", None),
            evidence_id=getattr(decision, "evidence_id", None),
            signed_amount=_canonical_decision_signed_amount(decision),
            currency=getattr(decision, "currency", None),
        )
        for decision in (decisions or [])
    )
    decision_transport_keys = {
        key
        for decision in (decisions or [])
        if (
            key := _adjustment_transport_key(
                evidence_id=getattr(decision, "evidence_id", None),
                signed_amount=_canonical_decision_signed_amount(decision),
                currency=getattr(decision, "currency", None),
                valuation_currency=valuation_currency,
            )
        )
        is not None
    }
    for raw in adjustments:
        if not isinstance(raw, Mapping):
            continue
        raw_adjustment_id = str(raw.get("id") or "").strip()
        # The top-level typed contract is authoritative. Venus still embeds the
        # same row in year metadata for legacy consumers; pricing both would
        # duplicate the adjustment and keeping the legacy copy would discard
        # typed currency/reviewer/original-value provenance.
        signed, applied = _signed_adjustment(raw)
        raw_content_key = _adjustment_content_key(
            label=raw.get("label") or raw.get("name"),
            evidence_id=raw.get("evidence_id") or raw.get("evidenceId"),
            signed_amount=signed,
            currency=raw.get("currency"),
        )
        if (raw_adjustment_id and raw_adjustment_id in contract_adjustment_ids) or (
            not raw_adjustment_id and raw_content_key in authoritative_content_keys
        ):
            continue
        duplicate_unidentified = (
            not raw_adjustment_id and raw_content_key in seen_unidentified_content
        )
        raw_currency = str(raw.get("currency") or "").strip().upper() or None
        currency_mismatch = bool(
            applied and raw_currency and valuation_currency and raw_currency != valuation_currency
        )
        if duplicate_unidentified or currency_mismatch:
            applied = False
        governed = _governed_legacy_adjustment(
            raw,
            valuation_currency=valuation_currency,
        )
        currency_unresolved = bool(
            applied
            and not currency_mismatch
            and (not str(raw.get("currency") or "").strip() or not valuation_currency)
        )
        if applied and not governed:
            applied = False
        if applied and explicit_reported is None and year_data.ebitda_normalized:
            applied = False
        row = {
            "id": raw.get("id"),
            "label": raw.get("label") or raw.get("name") or "EBITDA adjustment",
            "field": raw.get("field") or raw.get("category") or raw.get("adjustment_type"),
            "category": raw.get("category"),
            "owner_role": raw.get("owner_role"),
            "actual_owner_compensation": (
                raw.get("actual_owner_compensation")
                if "actual_owner_compensation" in raw
                else raw.get("actualOwnerCompensation")
            ),
            "replacement_owner_compensation": (
                raw.get("replacement_owner_compensation")
                if "replacement_owner_compensation" in raw
                else raw.get("replacementOwnerCompensation")
            ),
            "signed_amount": signed,
            "status": (
                "duplicate_transport_ambiguous"
                if duplicate_unidentified
                else (
                    "unpriced_currency_mismatch"
                    if currency_mismatch
                    else (
                        "unpriced_currency_unresolved"
                        if currency_unresolved
                        else (
                            "scenario_only_unverified"
                            if _status(raw.get("status")) in _APPLIED_NORMALIZATION_STATUSES
                            and not governed
                            else (
                                "unpriced_reported_basis_missing"
                                if not applied
                                and explicit_reported is None
                                and year_data.ebitda_normalized
                                else _status(raw.get("status")) or "proposed"
                            )
                        )
                    )
                )
            ),
            "source": raw.get("source"),
            "evidence_id": raw.get("evidence_id") or raw.get("evidenceId"),
            "reviewed_at": raw.get("reviewed_at") or raw.get("reviewedAt"),
            "rule_version": raw.get("rule_version") or raw.get("ruleVersion"),
            "currency": raw.get("currency"),
            "applied": applied,
        }
        adjustment_id = str(row.get("id") or "").strip()
        if adjustment_id:
            seen_adjustment_ids.add(adjustment_id)
        else:
            seen_unidentified_content.add(raw_content_key)
        if applied:
            applied_total += signed
            applied_rows.append(row)
        else:
            pending_rows.append(row)

    seen_decision_economics: set[tuple[str, str, str]] = set()
    for decision in decisions or []:
        evidence_id = str(getattr(decision, "evidence_id", "") or "").strip()
        decision_id = str(getattr(decision, "decision_id", "") or "").strip()
        if decision_id and decision_id in seen_adjustment_ids:
            continue
        state = _status(getattr(decision, "state", None))
        signed_amount = _canonical_decision_signed_amount(decision)
        decision_currency = getattr(decision, "currency", None)
        economics_key = _adjustment_transport_key(
            evidence_id=evidence_id,
            signed_amount=signed_amount,
            currency=decision_currency,
            valuation_currency=valuation_currency,
        )
        duplicate_economics = economics_key is not None and economics_key in seen_decision_economics
        currency_mismatch = bool(
            decision_currency and valuation_currency and decision_currency != valuation_currency
        )
        governed = _governed_canonical_decision(
            decision,
            valuation_currency=valuation_currency,
        )
        currency_unresolved = bool(
            state in {"accepted", "edited"}
            and (not str(decision_currency or "").strip() or not valuation_currency)
        )
        applied = (
            state in {"accepted", "edited"}
            and signed_amount is not None
            and not duplicate_economics
            and reported_basis_available
            and not currency_mismatch
            and governed
        )
        decision_payload = getattr(decision, "value_payload", None)
        if not isinstance(decision_payload, Mapping):
            decision_payload = {}
        owner_payload = (
            decision_payload
            if _status(getattr(decision, "category", None))
            in {"owner_compensation", "owner_compensation_adjustment"}
            else {}
        )
        decision_row = {
            "id": getattr(decision, "decision_id", None),
            "label": getattr(decision, "field_key", None) or "EBITDA adjustment",
            "field": getattr(decision, "field_key", None),
            "category": getattr(decision, "category", None),
            "owner_role": owner_payload.get("owner_role"),
            "actual_owner_compensation": owner_payload.get("actual_owner_compensation"),
            "replacement_owner_compensation": owner_payload.get("replacement_owner_compensation"),
            "signed_amount": safe_decimal_or_zero(signed_amount),
            "status": (
                "duplicate_transport_ambiguous"
                if duplicate_economics
                else (
                    "unpriced_currency_mismatch"
                    if currency_mismatch
                    else (
                        "unpriced_currency_unresolved"
                        if currency_unresolved
                        else (
                            "scenario_only_unverified"
                            if state in {"accepted", "edited"} and not governed
                            else (
                                state
                                if reported_basis_available
                                else "unpriced_reported_basis_missing"
                            )
                        )
                    )
                )
            )
            or "proposed",
            "source": getattr(decision, "schema_version", "valuation_input_decision.v2"),
            "evidence_id": evidence_id or None,
            "rule_version": getattr(decision, "rule_version", None),
            "currency": decision_currency,
            "decision_reason": getattr(decision, "reason", None),
            "decided_by": getattr(decision, "decided_by", None),
            "decided_at": getattr(decision, "decided_at", None),
            "applied": applied,
        }
        if applied:
            applied_total += safe_decimal_or_zero(signed_amount)
            applied_rows.append(decision_row)
            if economics_key is not None:
                seen_decision_economics.add(economics_key)
        else:
            pending_rows.append(decision_row)
        if decision_id:
            seen_adjustment_ids.add(decision_id)

    for adjustment in contract_adjustments or []:
        evidence_id = str(getattr(adjustment, "evidence_id", "") or "").strip()
        adjustment_id = str(getattr(adjustment, "id", "") or "").strip()
        if adjustment_id and adjustment_id in seen_adjustment_ids:
            continue
        status = _status(getattr(adjustment, "status", None))
        content_key = _adjustment_content_key(
            label=getattr(adjustment, "label", None),
            evidence_id=evidence_id,
            signed_amount=getattr(adjustment, "adjustment_amount", None),
            currency=getattr(adjustment, "currency", None),
        )
        transport_key = _adjustment_transport_key(
            evidence_id=evidence_id,
            signed_amount=getattr(adjustment, "adjustment_amount", None),
            currency=getattr(adjustment, "currency", None),
            valuation_currency=valuation_currency,
        )
        duplicate_unidentified = not adjustment_id and content_key in seen_unidentified_content
        duplicate_canonical_decision = (
            transport_key is not None and transport_key in decision_transport_keys
        )
        adjustment_currency = getattr(adjustment, "currency", None)
        currency_mismatch = bool(
            adjustment_currency and valuation_currency and adjustment_currency != valuation_currency
        )
        governed = _governed_typed_adjustment(
            adjustment,
            valuation_currency=valuation_currency,
        )
        currency_unresolved = bool(
            status in _APPLIED_NORMALIZATION_STATUSES
            and (not str(adjustment_currency or "").strip() or not valuation_currency)
        )
        applied = (
            status in _APPLIED_NORMALIZATION_STATUSES
            and reported_basis_available
            and not duplicate_unidentified
            and not duplicate_canonical_decision
            and not currency_mismatch
            and governed
        )
        signed_amount = safe_decimal_or_zero(getattr(adjustment, "adjustment_amount", None))
        adjustment_row = {
            "id": getattr(adjustment, "id", None),
            "label": getattr(adjustment, "label", None) or "EBITDA adjustment",
            "field": getattr(adjustment, "field", None),
            "category": getattr(adjustment, "category", None),
            "owner_role": getattr(adjustment, "owner_role", None),
            "actual_owner_compensation": getattr(adjustment, "actual_owner_compensation", None),
            "replacement_owner_compensation": getattr(
                adjustment, "replacement_owner_compensation", None
            ),
            "signed_amount": signed_amount,
            "status": (
                "duplicate_transport_ambiguous"
                if duplicate_unidentified or duplicate_canonical_decision
                else (
                    "unpriced_currency_mismatch"
                    if currency_mismatch
                    else (
                        "unpriced_currency_unresolved"
                        if currency_unresolved
                        else (
                            "scenario_only_unverified"
                            if status in _APPLIED_NORMALIZATION_STATUSES and not governed
                            else (
                                status
                                if reported_basis_available
                                else "unpriced_reported_basis_missing"
                            )
                        )
                    )
                )
            )
            or "proposed",
            "source": getattr(adjustment, "source", None),
            "evidence_id": evidence_id or None,
            "rule_version": getattr(adjustment, "rule_version", None),
            "decision_reason": getattr(adjustment, "reason", None),
            "approved_by": getattr(adjustment, "approved_by", None),
            "reviewed_at": getattr(adjustment, "reviewed_at", None),
            "currency": getattr(adjustment, "currency", None),
            "original_value": getattr(adjustment, "original_value", None),
            "adjusted_value": getattr(adjustment, "adjusted_value", None),
            "applied": applied,
        }
        if applied:
            applied_total += signed_amount
            applied_rows.append(adjustment_row)
        else:
            pending_rows.append(adjustment_row)
        if not adjustment_id:
            seen_unidentified_content.add(content_key)

    reported_basis_missing_for_adjustments = bool(
        not reported_basis_available
        and (contract_adjustments or decisions or (adjustments and year_data.ebitda_normalized))
    )
    if reported_basis_missing_for_adjustments:
        normalized = (
            year_data.normalized_ebitda
            if year_data.normalized_ebitda is not None
            else year_data.ebitda
        )
        source = "legacy_preapplied_unreconciled"
    elif adjustments or decisions or contract_adjustments:
        normalized = reported_dec + applied_total
        source = "accepted_adjustment_rows"
    elif year_data.normalized_ebitda is not None:
        normalized = reported_dec
        source = "unpriced_precomputed_normalized_ebitda"
        candidate = safe_decimal_or_zero(year_data.normalized_ebitda)
        if candidate != reported_dec:
            pending_rows.append(
                {
                    "id": None,
                    "label": "Precomputed normalized EBITDA",
                    "field": "normalized_ebitda",
                    "signed_amount": candidate - reported_dec,
                    "status": "scenario_only_unverified",
                    "source": "request.normalized_ebitda",
                    "applied": False,
                }
            )
    elif year_data.ebitda_normalized and metadata.get("normalized_ebitda") is not None:
        normalized = reported_dec
        source = "unpriced_precomputed_normalization_metadata"
        candidate = safe_decimal_or_zero(metadata.get("normalized_ebitda"))
        if candidate != reported_dec:
            pending_rows.append(
                {
                    "id": None,
                    "label": "Precomputed normalized EBITDA",
                    "field": "normalized_ebitda",
                    "signed_amount": candidate - reported_dec,
                    "status": "scenario_only_unverified",
                    "source": "ebitda_normalization_metadata.normalized_ebitda",
                    "applied": False,
                }
            )
    elif year_data.ebitda_normalized:
        normalized = reported_dec
        source = "reported_ebitda_normalized_flag_unpriced"
    else:
        normalized = reported_dec
        source = "reported_ebitda"

    return {
        "fiscal_year": year_data.year,
        "reported_ebitda": reported_dec,
        "normalized_ebitda": safe_decimal_or_zero(normalized),
        "applied_adjustments": applied_rows,
        "pending_adjustments": pending_rows,
        "normalization_source": source,
        "reported_basis_missing_for_adjustments": reported_basis_missing_for_adjustments,
    }
