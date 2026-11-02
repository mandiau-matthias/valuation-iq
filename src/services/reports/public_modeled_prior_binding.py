"""Bind public modeled bands and their unchanged benchmark source separately.

Widening a sensitivity band is an explicit model transformation. It must neither
rewrite empirical percentiles nor grant permission to change source evidence.
The normal benchmark gate still validates metric values, sample size and target.
"""

from collections.abc import Mapping
from datetime import datetime, timezone

from src.api.schemas.stateless_api import CalculateRequest
from src.services.reports.public_adaptive_profile import (
    PublicAdaptiveProfileError,
    _verify_modeled_prior_contract,
    _verify_producer_contract,
)


def public_source_calibration(
    request: CalculateRequest, calibration: dict[str, object]
) -> tuple[dict[str, object], list[str]]:
    metadata = request.metadata or {}
    is_v2 = metadata.get("public_adaptive_profile_v2") is True
    is_v1 = metadata.get("public_adaptive_profile_v1") is True
    if not (is_v2 or (is_v1 and request.selected_method == "ebitda_multiple")):
        return calibration, []
    source_calibration = dict(calibration)
    try:
        producer = metadata.get("public_adaptive_producer_contract")
        if not isinstance(producer, Mapping):
            raise PublicAdaptiveProfileError("public producer contract is missing")
        _verify_producer_contract(request, producer, now=datetime.now(timezone.utc))
        contracts = (
            metadata.get("public_modeled_prior_contracts")
            if is_v2
            else [metadata.get("public_modeled_prior_contract")]
        )
        if not isinstance(contracts, list) or not contracts:
            raise PublicAdaptiveProfileError("public modeled-prior contracts are missing")
        seen: set[str] = set()
        for contract in contracts:
            if not isinstance(contract, Mapping):
                raise PublicAdaptiveProfileError("public modeled-prior contract is invalid")
            _, low, median, high = _verify_modeled_prior_contract(request, contract)
            metric = str(contract["metric"])
            if metric in seen:
                raise PublicAdaptiveProfileError("public modeled-prior metric is duplicated")
            seen.add(metric)
            for quantile, expected in (("p25", low), ("median", median), ("p75", high)):
                attribute = f"{metric}_{quantile}"
                if calibration.get(attribute) != expected:
                    raise PublicAdaptiveProfileError(f"{attribute}.modeled_band_mismatch")
                source_calibration[attribute] = contract["distribution"][quantile]
    except PublicAdaptiveProfileError as exc:
        return calibration, [f"public_modeled_prior.{exc}"]
    return source_calibration, []
