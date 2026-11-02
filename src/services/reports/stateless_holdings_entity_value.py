"""Entity-level valuation inputs for deterministic holding-company SOTP."""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal, InvalidOperation

from src.api.schemas.stateless_api import CalculateRequest
from src.api.schemas.valuation_contracts import ValuationRun, ValuationRunV2
from src.services.reports.stateless_holdings_governance import (
    assumption_governance,
    unpriced_assumption,
)
from src.utils.decimal_helpers import safe_decimal_or_zero


class CanonicalChildRunError(ValueError):
    """A nested run failed the trust boundary required for canonical SOTP."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _mapping(value: object) -> Mapping[str, object]:
    return value if isinstance(value, Mapping) else {}


def _entity_lines(entity: Mapping[str, object]) -> Mapping[str, object]:
    for key in ("lines", "financial_lines", "financials"):
        nested = entity.get(key)
        if isinstance(nested, Mapping):
            return nested
    return entity


def _first_decimal(*values: object) -> Decimal | None:
    for value in values:
        if value is not None and value != "":
            try:
                parsed = value if isinstance(value, Decimal) else Decimal(str(value))
            except (InvalidOperation, TypeError, ValueError):
                continue
            if parsed.is_finite():
                return parsed
    return None


def _first_decimal_field(
    row: Mapping[str, object],
    *field_names: str,
) -> tuple[str | None, Decimal | None]:
    for field_name in field_names:
        if field_name not in row:
            continue
        parsed = _first_decimal(row.get(field_name))
        if parsed is not None:
            return field_name, parsed
    return None, None


def _governed_entity_adjustment(
    request: CalculateRequest,
    row: Mapping[str, object],
    *,
    field_path: str,
    signed_amount: Decimal,
    row_kind: str,
    parent_currency: str | None,
) -> bool:
    """Require one exact Titan-signed composite decision for an entity bridge row."""

    if not parent_currency:
        return False
    row_id = str(row.get("id") or "").strip()
    evidence_id = str(row.get("evidence_id") or "").strip()
    row_currency = str(row.get("currency") or "").strip().upper()
    if not row_id or not evidence_id or row_currency != parent_currency:
        return False
    case = request.valuation_case
    if case is None:
        return False
    matches = 0
    for decision in case.authoritative_input_decisions:
        if decision.state not in {"accepted", "edited"}:
            continue
        if str(decision.category).strip().casefold() not in {
            "balance_sheet_adjustment",
            "enterprise_to_equity",
            "equity_bridge",
            "holding_entity_bridge",
            "holding_sotp",
            "tax_latency",
        }:
            continue
        if decision.field_key != f"{field_path}.bridge_row":
            continue
        if str(decision.evidence_id).strip() != evidence_id:
            continue
        if str(decision.currency or "").upper() != parent_currency:
            continue
        payload = decision.value_payload
        if not isinstance(payload, Mapping):
            continue
        nested = payload.get("bridge_row")
        terms = nested if isinstance(nested, Mapping) else payload
        required = {"signed_amount", "type", "effective_date"}
        if row_kind == "tax_latency":
            required.update({"temporary_difference", "tax_rate"})
        else:
            required.update({"amount", "category"})
        if not required.issubset(terms):
            continue
        if (
            str(terms.get("type") or "").strip().casefold()
            != str(row.get("type") or "").strip().casefold()
        ):
            continue
        if _first_decimal(terms.get("signed_amount")) != signed_amount:
            continue
        if (
            str(terms.get("effective_date") or "").strip()
            != str(row.get("effective_date") or "").strip()
        ):
            continue
        if row_kind == "tax_latency":
            if _first_decimal(terms.get("temporary_difference")) != _first_decimal(
                row.get("temporary_difference")
            ) or _first_decimal(terms.get("tax_rate")) != _first_decimal(row.get("tax_rate")):
                continue
        elif (
            _first_decimal(terms.get("amount")) != _first_decimal(row.get("amount"))
            or str(terms.get("category") or "").strip().casefold()
            != str(row.get("category") or "").strip().casefold()
        ):
            continue
        matches += 1
    # Conflicting accepted decisions are excluded rather than selected by order.
    return matches == 1


def _entity_tax_adjustment(
    entity: Mapping[str, object],
    *,
    request: CalculateRequest,
    entity_path: str,
    parent_currency: str | None,
) -> tuple[Decimal, list[dict[str, object]]]:
    explicit = entity.get("tax_adjustment")
    if explicit is not None:
        decision = _mapping(entity.get("tax_adjustment_decision"))
        signed = safe_decimal_or_zero(explicit)
        if _governed_entity_adjustment(
            request,
            decision,
            field_path=f"{entity_path}.tax_adjustment",
            signed_amount=signed,
            row_kind="tax_latency",
            parent_currency=parent_currency,
        ):
            return safe_decimal_or_zero(explicit), []
        return Decimal("0"), [{"field": "tax_adjustment", "reason": "unverified"}]
    total = Decimal("0")
    unpriced: list[dict[str, object]] = []
    raw_latencies = entity.get("tax_latencies")
    if isinstance(raw_latencies, list):
        for index, raw in enumerate(raw_latencies):
            latency = _mapping(raw)
            if latency.get("tax_rate") is None:
                unpriced.append({"field": f"tax_latencies[{index}]", "reason": "tax_rate_missing"})
                continue
            difference = safe_decimal_or_zero(latency.get("temporary_difference"))
            rate = safe_decimal_or_zero(latency.get("tax_rate")) / Decimal("100")
            amount = difference * rate
            signed = amount if latency.get("type") == "active" else -amount
            if not _governed_entity_adjustment(
                request,
                latency,
                field_path=f"{entity_path}.tax_latencies[{index}]",
                signed_amount=signed,
                row_kind="tax_latency",
                parent_currency=parent_currency,
            ):
                unpriced.append(
                    {
                        "field": f"tax_latencies[{index}]",
                        "reason": "authoritative_composite_decision_required",
                    }
                )
                continue
            total += signed
    return total, unpriced


def _entity_balance_adjustment(
    entity: Mapping[str, object],
    *,
    request: CalculateRequest,
    entity_path: str,
    parent_currency: str | None,
) -> tuple[Decimal, list[dict[str, object]]]:
    total = Decimal("0")
    unpriced: list[dict[str, object]] = []
    raw_adjustments = entity.get("balance_sheet_adjustments")
    if not isinstance(raw_adjustments, list):
        return total, unpriced
    for index, raw in enumerate(raw_adjustments):
        adjustment = _mapping(raw)
        amount = abs(safe_decimal_or_zero(adjustment.get("amount")))
        signed = amount if adjustment.get("type") == "add" else -amount
        if not _governed_entity_adjustment(
            request,
            adjustment,
            field_path=f"{entity_path}.balance_sheet_adjustments[{index}]",
            signed_amount=signed,
            row_kind="balance_sheet_adjustment",
            parent_currency=parent_currency,
        ):
            unpriced.append(
                {
                    "field": f"balance_sheet_adjustments[{index}]",
                    "reason": "authoritative_composite_decision_required",
                }
            )
            continue
        total += signed
    return total, unpriced


def entity_sotp_value(
    entity: Mapping[str, object],
    *,
    default_name: str,
    parent_currency: str | None,
    request: CalculateRequest,
    entity_path: str,
) -> tuple[dict[str, object] | None, list[dict[str, object]]]:
    """Resolve one entity value and exclude ungoverned raw assumptions."""

    lines = _entity_lines(entity)
    run = _mapping(entity.get("valuation_run"))
    run_equity_range = _mapping(run.get("valuation_range"))
    run_enterprise_range = _mapping(run.get("enterprise_value_range"))
    has_canonical_run_range = bool(run_equity_range or run_enterprise_range)
    if has_canonical_run_range:
        run = _validated_canonical_run(
            entity=entity,
            run=run,
            parent_currency=parent_currency,
        )
        run_equity_range = _mapping(run.get("valuation_range"))
        run_enterprise_range = _mapping(run.get("enterprise_value_range"))
    equity_value_field, entity_equity_value = _first_decimal_field(
        entity,
        "equity_value",
        "equity_value_mid",
    )
    run_equity_value = _first_decimal(run_equity_range.get("mid"))
    enterprise_value_field, entity_enterprise_value = _first_decimal_field(
        entity,
        "enterprise_value",
        "enterprise_value_mid",
    )
    canonical_equity_values = (
        _first_decimal(run_equity_range.get("low")),
        _first_decimal(run_equity_range.get("mid")),
        _first_decimal(run_equity_range.get("high")),
    )
    canonical_enterprise_values = (
        _first_decimal(run_enterprise_range.get("low")),
        _first_decimal(run_enterprise_range.get("mid")),
        _first_decimal(run_enterprise_range.get("high")),
    )
    if has_canonical_run_range and any(value is None for value in canonical_equity_values):
        return None, []
    if run_enterprise_range and any(value is None for value in canonical_enterprise_values):
        return None, []

    method = ""
    value_basis = ""
    enterprise_low: Decimal | None = None
    enterprise_mid: Decimal | None = None
    enterprise_high: Decimal | None = None
    equity_low: Decimal | None = None
    equity_mid: Decimal | None = None
    equity_high: Decimal | None = None
    assumption_governance_sources: dict[str, str] = {}
    unpriced_assumptions: list[dict[str, object]] = []

    def require_raw_assumption(
        field_name: str,
        value: Decimal,
        *,
        monetary: bool,
    ) -> None:
        field_path = f"{entity_path}.{field_name}"
        verdict = assumption_governance(
            request,
            field_name=field_name,
            field_path=field_path,
            value=value,
            monetary=monetary,
            parent_currency=parent_currency,
        )
        if verdict.priced:
            assumption_governance_sources[field_name] = str(verdict.source)
            return
        unpriced_assumptions.append(
            unpriced_assumption(
                field_path=field_path,
                value=value,
                verdict=verdict,
            )
        )

    canonical_run_used = has_canonical_run_range
    if canonical_run_used:
        equity_low, equity_mid, equity_high = canonical_equity_values
        enterprise_low, enterprise_mid, enterprise_high = canonical_enterprise_values
        value_basis = "canonical_run"
        method = str(run.get("methodology_used") or "canonical_run")
        assumption_governance_sources["valuation_basis"] = "persisted_canonical_run"
    elif entity_equity_value is not None and equity_value_field is not None:
        require_raw_assumption(
            equity_value_field,
            entity_equity_value,
            monetary=True,
        )
        value_basis = "equity"
        method = str(entity.get("valuation_method") or "explicit")
        equity_mid = entity_equity_value
        equity_low_field, equity_low = _first_decimal_field(
            entity,
            "equity_value_low",
        )
        equity_high_field, equity_high = _first_decimal_field(
            entity,
            "equity_value_high",
        )
        if equity_low_field is not None and equity_low is not None:
            require_raw_assumption(equity_low_field, equity_low, monetary=True)
        if equity_high_field is not None and equity_high is not None:
            require_raw_assumption(equity_high_field, equity_high, monetary=True)
    elif entity_enterprise_value is not None and enterprise_value_field is not None:
        require_raw_assumption(
            enterprise_value_field,
            entity_enterprise_value,
            monetary=True,
        )
        value_basis = "enterprise"
        method = str(entity.get("valuation_method") or "explicit")
        enterprise_mid = entity_enterprise_value
        enterprise_low_field, enterprise_low = _first_decimal_field(
            entity,
            "enterprise_value_low",
        )
        enterprise_high_field, enterprise_high = _first_decimal_field(
            entity,
            "enterprise_value_high",
        )
        if enterprise_low_field is not None and enterprise_low is not None:
            require_raw_assumption(
                enterprise_low_field,
                enterprise_low,
                monetary=True,
            )
        if enterprise_high_field is not None and enterprise_high is not None:
            require_raw_assumption(
                enterprise_high_field,
                enterprise_high,
                monetary=True,
            )
    else:
        ebitda = _first_decimal(entity.get("ebitda"), lines.get("ebitda"))
        multiple_field, multiple = _first_decimal_field(
            entity,
            "ev_ebitda_multiple",
            "selected_multiple",
            "multiple",
        )
        if (
            ebitda is not None
            and ebitda > 0
            and multiple is not None
            and multiple > 0
            and multiple_field is not None
        ):
            require_raw_assumption(multiple_field, multiple, monetary=False)
            value_basis = "enterprise"
            method = "ev_ebitda"
            enterprise_mid = ebitda * multiple
            low_multiple_field, low_multiple = _first_decimal_field(
                entity,
                "multiple_low",
                "multiple_p25",
            )
            high_multiple_field, high_multiple = _first_decimal_field(
                entity,
                "multiple_high",
                "multiple_p75",
            )
            if low_multiple is not None and low_multiple_field is not None:
                require_raw_assumption(
                    low_multiple_field,
                    low_multiple,
                    monetary=False,
                )
                enterprise_low = ebitda * low_multiple
            if high_multiple is not None and high_multiple_field is not None:
                require_raw_assumption(
                    high_multiple_field,
                    high_multiple,
                    monetary=False,
                )
                enterprise_high = ebitda * high_multiple
        else:
            total_assets = _first_decimal(entity.get("total_assets"), lines.get("total_assets"))
            total_liabilities = _first_decimal(
                entity.get("total_liabilities"), lines.get("total_liabilities")
            )
            if total_assets is None or total_liabilities is None:
                return None, []
            value_basis = "equity"
            method = "adjusted_nav"
            equity_mid = total_assets - total_liabilities
            assumption_governance_sources["valuation_basis"] = (
                "reported_financial_facts_adjusted_nav_policy.v1"
            )

    if unpriced_assumptions:
        return None, unpriced_assumptions

    source_tax_adjustment, unpriced_tax_adjustments = _entity_tax_adjustment(
        entity,
        request=request,
        entity_path=entity_path,
        parent_currency=parent_currency,
    )
    source_other_adjustment, unpriced_balance_adjustments = _entity_balance_adjustment(
        entity,
        request=request,
        entity_path=entity_path,
        parent_currency=parent_currency,
    )
    # Canonical ranges are post-bridge and remain authoritative independently.
    # Pure-equity methods explicitly commit ``enterprise_value_range=None``; do
    # not manufacture EV from stale entity net debt in that case.
    canonical_run_equity_used = canonical_run_used and run_equity_value is not None
    run_response_snapshot = _mapping(run.get("response_snapshot"))
    embedded_owner_dependency_adjustment = safe_decimal_or_zero(
        run_response_snapshot.get("owner_dependency_adjustment")
    )
    value_basis_stage = str(entity.get("value_basis_stage") or "").strip().lower()
    if canonical_run_used:
        value_basis_stage = "post_bridge"
    elif not value_basis_stage:
        value_basis_stage = "pre_bridge"
    apply_entity_bridge = value_basis_stage == "pre_bridge"
    tax_adjustment = source_tax_adjustment if apply_entity_bridge else Decimal("0")
    other_adjustment = source_other_adjustment if apply_entity_bridge else Decimal("0")
    total_debt = _first_decimal(entity.get("total_debt"), lines.get("total_debt"))
    cash = _first_decimal(entity.get("cash"), lines.get("cash"))
    net_debt = _first_decimal(entity.get("net_debt"), lines.get("net_debt"))
    if net_debt is None:
        net_debt = safe_decimal_or_zero(total_debt) - safe_decimal_or_zero(cash)

    if canonical_run_used:
        if equity_mid is None:
            return None, []
    elif value_basis == "enterprise":
        if enterprise_mid is None:
            return None, []
        enterprise_low = enterprise_mid if enterprise_low is None else enterprise_low
        enterprise_high = enterprise_mid if enterprise_high is None else enterprise_high
        equity_mid = enterprise_mid - net_debt + tax_adjustment + other_adjustment
        equity_low = enterprise_low - net_debt + tax_adjustment + other_adjustment
        equity_high = enterprise_high - net_debt + tax_adjustment + other_adjustment
    else:
        if equity_mid is None:
            return None, []
        equity_low = equity_mid if equity_low is None else equity_low
        equity_high = equity_mid if equity_high is None else equity_high
        # Preserve the pre-bridge enterprise basis before applying entity-level
        # tax and balance-sheet adjustments to final equity.
        enterprise_mid = equity_mid + net_debt
        enterprise_low = equity_low + net_debt
        enterprise_high = equity_high + net_debt
        equity_mid = equity_mid + tax_adjustment + other_adjustment
        equity_low = equity_low + tax_adjustment + other_adjustment
        equity_high = equity_high + tax_adjustment + other_adjustment

    equity_low = equity_mid if equity_low is None else equity_low
    equity_high = equity_mid if equity_high is None else equity_high
    equity_low, equity_high = min(equity_low, equity_high), max(equity_low, equity_high)
    if enterprise_mid is not None:
        enterprise_low = enterprise_mid if enterprise_low is None else enterprise_low
        enterprise_high = enterprise_mid if enterprise_high is None else enterprise_high
        enterprise_low, enterprise_high = (
            min(enterprise_low, enterprise_high),
            max(enterprise_low, enterprise_high),
        )
    return {
        "entity_id": entity.get("id") or entity.get("source_id"),
        "entity_name": entity.get("name") or entity.get("title") or default_name,
        "valuation_run_id": entity.get("valuation_run_id") or run.get("run_id"),
        "currency": run.get("currency") if canonical_run_used else parent_currency,
        "method": method,
        "value_basis": value_basis,
        "value_basis_stage": value_basis_stage,
        "assumption_governance": assumption_governance_sources,
        "enterprise_value_low": enterprise_low,
        "enterprise_value_mid": enterprise_mid,
        "enterprise_value": enterprise_mid,
        "enterprise_value_high": enterprise_high,
        "equity_value_low": equity_low,
        "equity_value_mid": equity_mid,
        "equity_value_high": equity_high,
        "net_debt": net_debt,
        "tax_adjustment": tax_adjustment,
        "other_balance_sheet_adjustment": other_adjustment,
        "source_tax_adjustment": source_tax_adjustment,
        "source_other_balance_sheet_adjustment": source_other_adjustment,
        "unpriced_entity_adjustments": [
            *unpriced_tax_adjustments,
            *unpriced_balance_adjustments,
        ],
        "adjustments_embedded_in_source_value": canonical_run_equity_used
        or not apply_entity_bridge,
        "embedded_owner_dependency_adjustment": embedded_owner_dependency_adjustment,
        "range_is_point_only": equity_low == equity_mid == equity_high,
        "enterprise_range_is_point_only": (
            enterprise_mid is not None and enterprise_low == enterprise_mid == enterprise_high
        ),
        "enterprise_value_available": enterprise_mid is not None,
    }, []


def _validated_canonical_run(
    *,
    entity: Mapping[str, object],
    run: Mapping[str, object],
    parent_currency: str | None,
) -> Mapping[str, object]:
    """Validate integrity, identity and currency before pricing a child run."""

    try:
        model = ValuationRunV2 if run.get("schema_version") == "valuation_run.v2" else ValuationRun
        validated = model.model_validate(dict(run))
    except (TypeError, ValueError) as exc:
        raise CanonicalChildRunError(
            "integrity_invalid",
            f"Nested canonical valuation_run is invalid: {exc}",
        ) from exc

    currencies = {validated.currency, validated.valuation_range.currency}
    if validated.enterprise_value_range is not None:
        currencies.add(validated.enterprise_value_range.currency)
    if parent_currency is None:
        raise CanonicalChildRunError(
            "parent_currency_unresolved",
            "Parent currency must be explicit before canonical child ranges can be aggregated.",
        )
    if None in currencies or currencies != {parent_currency}:
        raise CanonicalChildRunError(
            "currency_mismatch",
            (
                "Canonical child run currency must match the parent currency on every "
                "applicable range; implicit FX conversion is prohibited."
            ),
        )

    entity_run_id = str(entity.get("valuation_run_id") or "").strip()
    if entity_run_id and entity_run_id != validated.run_id:
        raise CanonicalChildRunError(
            "run_id_mismatch",
            "Entity valuation_run_id does not match the nested canonical run.",
        )

    entity_id = str(entity.get("id") or entity.get("source_id") or "").strip()
    run_company_id = str(validated.company_id or "").strip()
    if entity_id and run_company_id and entity_id != run_company_id:
        raise CanonicalChildRunError(
            "company_id_mismatch",
            "Entity identity does not match valuation_run.company_id.",
        )

    entity_name = _normalized_identity_name(entity.get("name") or entity.get("title"))
    run_company_name = _normalized_identity_name(validated.company_name)
    if entity_name and run_company_name and entity_name != run_company_name:
        raise CanonicalChildRunError(
            "company_name_mismatch",
            "Entity name does not match valuation_run.company_name.",
        )

    return validated.model_dump(mode="python")


def _normalized_identity_name(value: object) -> str:
    return " ".join(str(value or "").split()).casefold()
