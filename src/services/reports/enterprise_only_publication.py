"""Project an independently priced EV without an unsupported shareholder bridge."""

from dataclasses import dataclass
from decimal import Decimal
from typing import Mapping

from src.api.schemas.multiple_build_up import MultipleBuildUp
from src.api.schemas.negative_ebitda_recovery import NegativeEbitdaResolution
from src.api.schemas.stateless_response_schemas import MethodResult, TriageFlag
from src.api.schemas.weighted_valuation import WeightedValuationResult

from .stateless_completion_accounts import CompletionAccountBridge
from .value_basis_admission import (
    enterprise_only_build_up,
    enterprise_only_method_results,
    remove_equity_projections,
    uses_accounting_basis_policy,
)


@dataclass(frozen=True)
class EnterpriseOnlyPublication:
    financial_metrics: dict[str, object]
    method_results: dict[str, MethodResult]
    multiple_build_up: MultipleBuildUp | None
    driver_ledger: dict[str, object]
    dcf_results: dict[str, object] | None
    multiples_results: dict[str, object] | None
    public_audit: dict[str, object] | None
    negative_resolution: NegativeEbitdaResolution | None
    bridge_adjustments: dict[str, object]
    triage_flag: TriageFlag


def _without_equity(mapping: Mapping[str, object] | None) -> dict[str, object] | None:
    return remove_equity_projections(mapping) if mapping is not None else None


def enterprise_only_publication(
    *,
    request: object,
    completion_accounts: CompletionAccountBridge,
    enterprise_value_mid: Decimal | None,
    financial_metrics: Mapping[str, object],
    method_results: Mapping[str, MethodResult],
    multiple_build_up: MultipleBuildUp | None,
    weighted_valuation: WeightedValuationResult | None,
    driver_ledger: Mapping[str, object],
    dcf_results: Mapping[str, object] | None,
    multiples_results: Mapping[str, object] | None,
    public_audit: Mapping[str, object] | None,
    negative_resolution: NegativeEbitdaResolution | None,
) -> EnterpriseOnlyPublication | None:
    if not (
        uses_accounting_basis_policy(request)
        and completion_accounts.unresolved_fields
        and enterprise_value_mid is not None
    ):
        return None
    missing = list(completion_accounts.unresolved_fields)
    metrics = dict(financial_metrics)
    metrics.update(
        {
            "equity_status": "unavailable_incomplete_bridge",
            "cash": completion_accounts.available_cash,
            "total_debt": completion_accounts.total_debt_like,
            "net_debt": None,
            "resolved_method_weights": [
                {
                    "method_key": row.method_key,
                    "weight": str(row.weight),
                    "eligible": True,
                    "value_basis": "enterprise_value",
                }
                for row in (weighted_valuation.contributions if weighted_valuation else [])
            ],
        }
    )
    ledger = remove_equity_projections(driver_ledger)
    layers = ledger.get("layers")
    if isinstance(layers, dict):
        layers["enterprise_to_equity"] = {"status": "unavailable", "unresolved_fields": missing}
        layers["shareholder_transaction"] = {"status": "unavailable"}
    if negative_resolution is not None:
        from .negative_ebitda_recovery import _canonical_hash

        resolution = remove_equity_projections(
            negative_resolution.model_dump(mode="json", exclude={"resolution_snapshot_hash"})
        )
        resolution["equity_bridge"] = {
            "shareholder_equity_status": "unavailable_incomplete_bridge",
            "unresolved_fields": missing,
        }
        resolution["resolution_snapshot_hash"] = _canonical_hash(resolution)
        negative_resolution = NegativeEbitdaResolution.model_validate(resolution)
    return EnterpriseOnlyPublication(
        financial_metrics=metrics,
        method_results=enterprise_only_method_results(method_results),
        multiple_build_up=enterprise_only_build_up(
            multiple_build_up, completion_accounts.unresolved_fields
        ),
        driver_ledger=ledger,
        dcf_results=_without_equity(dcf_results),
        multiples_results=_without_equity(multiples_results),
        public_audit=_without_equity(public_audit),
        negative_resolution=negative_resolution,
        bridge_adjustments={"status": "unavailable", "unresolved_fields": missing},
        triage_flag=TriageFlag(
            field="equity_value",
            issue="EQUITY_BRIDGE_INCOMPLETE",
            severity="warning",
            value={"unresolved_fields": missing},
        ),
    )
