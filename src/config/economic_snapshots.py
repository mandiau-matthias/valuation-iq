"""Immutable, source-dated macro snapshots used by canonical DCF.

The economic context is a value-affecting input.  A hash-shaped identifier by
itself is not evidence, so the commitment binds every value, observation date,
source and issuer that can influence DCF.  Country-pack policy separately
decides whether the sealed snapshot is fresh enough for a valuation date.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Mapping, Sequence

ECONOMIC_SNAPSHOT_SCHEMA_VERSION = "economic_snapshot.v1"

_COMMITTED_FIELDS = (
    "schema_version",
    "snapshot_id",
    "snapshot_issuer",
    "country_code",
    "risk_free_rate",
    "risk_free_rate_source",
    "risk_free_rate_is_override",
    "risk_free_rate_observed_at",
    "gdp_growth_rate",
    "terminal_growth_rate",
    "growth_rates_observed_at",
    "inflation_rate",
    "equity_risk_premium",
    "market_risk_premium",
    "erp",
    "equity_risk_premium_observed_at",
    "source",
    "source_references",
)


def _canonical(value: object) -> object:
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise ValueError("economic snapshot values must be finite")
        return format(value, "f")
    if isinstance(value, Enum):
        return _canonical(value.value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Mapping):
        return {str(key): _canonical(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_canonical(item) for item in value]
    if isinstance(value, float) and (value != value or value in (float("inf"), float("-inf"))):
        raise ValueError("economic snapshot values must be finite")
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    raise TypeError(f"unsupported economic snapshot value: {type(value).__name__}")


def economic_snapshot_commitment(payload: Mapping[str, object]) -> dict[str, object]:
    """Return the complete calculation-affecting snapshot commitment."""
    commitment = {field: _canonical(payload.get(field)) for field in _COMMITTED_FIELDS}
    # These are transport aliases for one economic assumption, not three
    # independently priced inputs.  Derive absent aliases deterministically so
    # every producer seals the same economics to the same cross-language hash.
    equity_risk_premium = commitment["equity_risk_premium"]
    if commitment["market_risk_premium"] is None:
        commitment["market_risk_premium"] = equity_risk_premium
    if commitment["erp"] is None:
        commitment["erp"] = equity_risk_premium
    return commitment


def economic_snapshot_hash(payload: Mapping[str, object]) -> str:
    encoded = json.dumps(
        economic_snapshot_commitment(payload),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def seal_economic_snapshot_payload(payload: Mapping[str, object]) -> dict[str, object]:
    """Test/registry helper that seals, but does not authenticate, a snapshot."""
    sealed = dict(payload)
    sealed.setdefault("schema_version", ECONOMIC_SNAPSHOT_SCHEMA_VERSION)
    sealed["snapshot_hash"] = economic_snapshot_hash(sealed)
    return sealed


def verify_economic_snapshot_hash(payload: Mapping[str, object]) -> None:
    expected = economic_snapshot_hash(payload)
    supplied = str(payload.get("snapshot_hash") or "").strip().lower()
    if supplied != expected:
        raise ValueError("economic_context.snapshot_hash does not match its canonical commitment")
