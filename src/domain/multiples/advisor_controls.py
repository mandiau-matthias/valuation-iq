"""Advisor-grade controls and transparency helpers for multiples valuation.

The functions in this module are intentionally pure. They normalize advisor
inputs, compose discount stacks, and build report/API-ready provenance without
depending on FastAPI or the step-pipeline classes.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from decimal import Decimal, InvalidOperation
from typing import Any

JsonMap = dict[str, object]

MULTIPLE_TYPE_ALIASES: dict[str, str] = {
    "ev_ebitda": "ev_ebitda",
    "ev/ebitda": "ev_ebitda",
    "ev_ebitda_multiple": "ev_ebitda",
    "ebitda": "ev_ebitda",
    "ebitda_multiple": "ev_ebitda",
    "ev/revenue": "ev_revenue",
    "ev_revenue": "ev_revenue",
    "ev_revenue_multiple": "ev_revenue",
    "revenue": "ev_revenue",
    "revenue_multiple": "ev_revenue",
    "omzet": "ev_revenue",
    "omzet_multiple": "ev_revenue",
    "p/e": "pe",
    "pe": "pe",
    "pe_ratio": "pe",
}

MULTIPLE_TYPE_LABELS: dict[str, str] = {
    "ev_ebitda": "EV/EBITDA",
    "ev_revenue": "EV/Revenue",
    "pe": "P/E",
}

DEFAULT_MULTIPLE_TYPE_WEIGHTS: dict[str, Decimal] = {
    "ev_ebitda": Decimal("0.60"),
    "ev_revenue": Decimal("0.30"),
    "pe": Decimal("0.10"),
}

DISCOUNT_LABELS: dict[str, str] = {
    "size_discount": "Size discount",
    "liquidity_discount": "Liquidity discount",
    "country_adjustment": "Country adjustment",
    "growth_premium": "Growth premium",
    "owner_concentration": "Owner concentration",
    "revenue_trend": "Revenue trend",
}

DEFAULT_DISCOUNT_FLOOR_FACTOR = Decimal("0.45")


def _decimal(value: object, default: Decimal = Decimal("0")) -> Decimal:
    if value is None or value == "":
        return default
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return default


def _optional_decimal(value: object) -> Decimal | None:
    if value is None or value == "":
        return None
    parsed = _decimal(value)
    return parsed


def _canonical_multiple_key(raw: object) -> str | None:
    token = str(raw or "").strip().lower().replace("-", "_").replace(" ", "_")
    return MULTIPLE_TYPE_ALIASES.get(token)


def _percent_or_ratio(value: Decimal) -> Decimal:
    """Accept either 0..1 ratios or whole percentages."""
    if abs(value) > Decimal("1.5"):
        return value / Decimal("100")
    return value


def normalize_multiple_type_weights(
    raw_weights: Mapping[str, object] | None,
    available_types: Sequence[str],
    default_weights: Mapping[str, object] | None = None,
    default_source: str = "sector_aware_default",
) -> tuple[dict[str, Decimal], str]:
    """Normalize advisor multiple-type weights against available methods.

    Values may be ratios or whole percentages. Missing weights fall back to
    the supplied sector/model default, then the conservative 60/30/10 policy,
    but only over methods with an available valuation.
    """
    available = [key for key in available_types if key in MULTIPLE_TYPE_LABELS]
    if not available:
        return {}, "none"

    normalized_input: dict[str, Decimal] = {}
    if raw_weights:
        for raw_key, raw_value in raw_weights.items():
            key = _canonical_multiple_key(raw_key)
            if key not in available:
                continue
            weight = _percent_or_ratio(_decimal(raw_value))
            if weight > 0:
                normalized_input[key] = weight

    normalized_default: dict[str, Decimal] = {}
    if default_weights:
        for raw_key, raw_value in default_weights.items():
            key = _canonical_multiple_key(raw_key)
            if key not in available:
                continue
            weight = _percent_or_ratio(_decimal(raw_value))
            if weight > 0:
                normalized_default[key] = weight

    source = (
        "advisor"
        if normalized_input
        else (default_source if normalized_default else "system_default")
    )
    weights = (
        {key: normalized_input.get(key, Decimal("0")) for key in available}
        if normalized_input
        else (
            {key: normalized_default.get(key, Decimal("0")) for key in available}
            if normalized_default
            else {key: DEFAULT_MULTIPLE_TYPE_WEIGHTS.get(key, Decimal("0")) for key in available}
        )
    )

    total = sum(weights.values(), Decimal("0"))
    if total <= 0:
        equal = Decimal("1") / Decimal(len(available))
        return {key: equal for key in available}, "equal_fallback"
    return {key: weight / total for key, weight in weights.items()}, source


def infer_sector_multiple_type_weights(
    *,
    revenue: object = None,
    ebitda: object = None,
    benchmark_contract: Mapping[str, object] | None = None,
) -> tuple[dict[str, Decimal], str]:
    """Infer model blend defaults from the available sector/financial signal.

    Upswitch Index benchmark contracts currently provide the multiple metrics but not a
    persisted "blend weights" field. Until that exists, the engine derives a
    sector-aware default from whether the resolved benchmark exposes each
    metric and from the company's EBITDA margin.
    """
    contract_weights = None
    if benchmark_contract:
        contract_weights = (
            benchmark_contract.get("multiple_type_weights")
            or benchmark_contract.get("multipleTypeWeights")
            or benchmark_contract.get("blend_weights")
            or benchmark_contract.get("blendWeights")
        )
    if isinstance(contract_weights, Mapping):
        weights: dict[str, Decimal] = {}
        for raw_key, raw_value in contract_weights.items():
            key = _canonical_multiple_key(raw_key)
            if key:
                weights[key] = _percent_or_ratio(_decimal(raw_value))
        if weights:
            return weights, "delphi_benchmark_contract"

    metrics = benchmark_contract.get("metrics") if isinstance(benchmark_contract, Mapping) else None
    metrics_map = metrics if isinstance(metrics, Mapping) else {}
    has_pe = "pe_ratio" in metrics_map or "pe" in metrics_map

    revenue_decimal = _decimal(revenue)
    ebitda_decimal = _decimal(ebitda)
    margin = ebitda_decimal / revenue_decimal if revenue_decimal > 0 else Decimal("0")

    if ebitda_decimal <= 0 or margin < Decimal("0.05"):
        weights = {
            "ev_ebitda": Decimal("0.15"),
            "ev_revenue": Decimal("0.75"),
            "pe": Decimal("0.10") if has_pe else Decimal("0"),
        }
    elif margin >= Decimal("0.20"):
        weights = {
            "ev_ebitda": Decimal("0.70"),
            "ev_revenue": Decimal("0.20"),
            "pe": Decimal("0.10") if has_pe else Decimal("0"),
        }
    else:
        weights = {
            "ev_ebitda": Decimal("0.60"),
            "ev_revenue": Decimal("0.30"),
            "pe": Decimal("0.10") if has_pe else Decimal("0"),
        }

    return weights, "sector_aware_default"


def build_multiple_type_blend(
    valuations: Mapping[str, object],
    raw_weights: Mapping[str, object] | None = None,
    default_weights: Mapping[str, object] | None = None,
    default_source: str = "sector_aware_default",
) -> JsonMap:
    """Build the advisor-visible multiple-type blend block."""
    canonical_values: dict[str, Decimal] = {}
    for raw_key, raw_value in valuations.items():
        key = _canonical_multiple_key(raw_key)
        value = _optional_decimal(raw_value)
        if key and value is not None and value > 0:
            canonical_values[key] = value

    weights, source = normalize_multiple_type_weights(
        raw_weights,
        list(canonical_values.keys()),
        default_weights=default_weights,
        default_source=default_source,
    )
    model_weights, model_source = normalize_multiple_type_weights(
        None,
        list(canonical_values.keys()),
        default_weights=default_weights,
        default_source=default_source,
    )
    weighted_ev = sum(
        canonical_values[key] * weights.get(key, Decimal("0")) for key in canonical_values
    )

    rows = [
        {
            "key": key,
            "label": MULTIPLE_TYPE_LABELS[key],
            "enterprise_value": canonical_values[key],
            "weight": weights.get(key, Decimal("0")),
            "model_weight": model_weights.get(key, Decimal("0")),
            "advisor_delta": weights.get(key, Decimal("0")) - model_weights.get(key, Decimal("0")),
            "contribution": canonical_values[key] * weights.get(key, Decimal("0")),
            "included": weights.get(key, Decimal("0")) > 0,
        }
        for key in canonical_values
    ]

    return {
        "source": source,
        "model_source": model_source,
        "weighted_enterprise_value": weighted_ev,
        "weights": weights,
        "model_weights": model_weights,
        "rows": rows,
    }


def normalize_discount_weights(
    raw_weights: Mapping[str, object] | None,
    discount_keys: Sequence[str],
) -> dict[str, Decimal]:
    """Normalize per-discount influence weights.

    These weights are multipliers, not a sum-to-one mix. A weight of 0 disables
    that discount. 1 keeps the model discount. Values are capped at 2x so an
    override cannot silently double an already aggressive risk penalty.
    """
    normalized: dict[str, Decimal] = {key: Decimal("1") for key in discount_keys}
    if not raw_weights:
        return normalized

    aliases = {
        "size": "size_discount",
        "liquidity": "liquidity_discount",
        "country": "country_adjustment",
        "growth": "growth_premium",
        "owner": "owner_concentration",
    }
    for raw_key, raw_value in raw_weights.items():
        token = str(raw_key).strip().lower().replace("-", "_").replace(" ", "_")
        key = aliases.get(token, token)
        if key not in normalized:
            continue
        value = _percent_or_ratio(_decimal(raw_value, Decimal("1")))
        normalized[key] = min(Decimal("2"), max(Decimal("0"), value))
    return normalized


def compose_discount_stack(
    adjustments: Mapping[str, object],
    *,
    raw_weights: Mapping[str, object] | None = None,
    enabled: bool = True,
    floor_factor: object = DEFAULT_DISCOUNT_FLOOR_FACTOR,
) -> JsonMap:
    """Compose discounts multiplicatively with a defended floor.

    Input adjustments use the existing convention: -0.22 means a 22% discount,
    +0.05 means a 5% premium. The returned ``total_adjustment_factor`` is the
    multiplier to apply to enterprise value.
    """
    discount_keys = [
        key for key, value in adjustments.items() if _optional_decimal(value) is not None
    ]
    weights = normalize_discount_weights(raw_weights, discount_keys)
    floor = min(
        Decimal("1"), max(Decimal("0"), _decimal(floor_factor, DEFAULT_DISCOUNT_FLOOR_FACTOR))
    )

    running = Decimal("1")
    rows: list[JsonMap] = []
    for key in discount_keys:
        model_adjustment = _decimal(adjustments.get(key))
        weight = weights.get(key, Decimal("1"))
        effective_adjustment = model_adjustment * weight if enabled else Decimal("0")
        factor = max(Decimal("0"), Decimal("1") + effective_adjustment)
        before = running
        running *= factor
        rows.append(
            {
                "key": key,
                "label": DISCOUNT_LABELS.get(key, key.replace("_", " ").title()),
                "model_adjustment": model_adjustment,
                "advisor_weight": weight,
                "effective_adjustment": effective_adjustment,
                "factor_before": before,
                "factor_after": running,
                "enabled": enabled and weight > 0,
            }
        )

    pre_floor_factor = running
    floored = enabled and running < floor
    if floored:
        running = floor

    return {
        "enabled": enabled,
        "floor_factor": floor,
        "pre_floor_factor": pre_floor_factor,
        "floor_applied": floored,
        "total_adjustment_factor": running,
        "total_adjustment": running - Decimal("1"),
        "rows": rows,
        "composition": "multiplicative",
    }


def normalize_earnings_basis(metric_type: object) -> str:
    token = str(metric_type or "").strip().upper().replace("_", " ")
    if "SDE" in token:
        return "SDE"
    if "EBIT" in token and "EBITDA" not in token:
        return "EBIT"
    if "REVENUE" in token or "OMZET" in token:
        return "Revenue"
    if "EBITDA" in token:
        return "EBITDA"
    return token.title() if token else "Unknown"


NON_APPLIED_EBITDA_ADJUSTMENT_STATUSES = frozenset(
    {
        "pending",
        "proposed",
        "proposal",
        "candidate",
        "suggested",
        "suggestion",
        "review",
        "needs_review",
        "advisor_review_required",
        "draft",
        "unconfirmed",
        "rejected",
        "declined",
        "excluded",
    }
)


def _normalization_decimal(value: object) -> Decimal | None:
    if value is None or isinstance(value, bool) or value == "":
        return None
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    return parsed if parsed.is_finite() else None


def _first_normalization_decimal(*values: object) -> Decimal | None:
    for value in values:
        parsed = _normalization_decimal(value)
        if parsed is not None:
            return parsed
    return None


def build_adjusted_ebitda_build_up(year_data: object | None) -> JsonMap:
    """Build a domain-level reported EBITDA -> adjusted EBITDA ledger."""
    if year_data is None:
        return {}

    metadata_raw = _attr(year_data, "ebitda_normalization_metadata")
    metadata = dict(metadata_raw) if isinstance(metadata_raw, Mapping) else {}
    normalized_flag = bool(_attr(year_data, "ebitda_normalized"))
    reported = _first_normalization_decimal(
        metadata.get("reported_ebitda"),
        _attr(year_data, "reported_ebitda"),
        None if normalized_flag else _attr(year_data, "ebitda"),
    )
    adjustment_rows = _build_ebitda_adjustment_rows(metadata.get("adjustments"))
    applied_total = sum(
        (row["signed_amount"] for row in adjustment_rows if row["applied"]),
        Decimal("0"),
    )

    adjusted = _first_normalization_decimal(
        metadata.get("normalized_ebitda"),
        metadata.get("sustainable_ebitda"),
        _attr(year_data, "adjusted_ebitda"),
    )
    if normalized_flag and reported is None:
        # `ebitda_normalized` identifies an already adjusted amount. Without
        # the original reported basis, neither rows nor a claimed total may be
        # added again, and their bridge cannot be represented as zero.
        adjusted = _normalization_decimal(_attr(year_data, "ebitda"))
        if adjusted is None:
            return {}
        adjustment_rows = [
            (
                {**row, "applied": False, "status": "unpriced_reported_basis_missing"}
                if row["applied"]
                else row
            )
            for row in adjustment_rows
        ]
    elif reported is None:
        return {}
    elif adjustment_rows:
        # Itemized accepted rows are the earnings bridge. A precomputed total
        # must not price an unapproved proposal or apply the same rows twice.
        adjusted = reported + applied_total
    elif adjusted is None:
        total_adjustments = _normalization_decimal(metadata.get("total_adjustments"))
        if total_adjustments is not None:
            adjusted = reported + total_adjustments
        elif normalized_flag:
            adjusted = _normalization_decimal(_attr(year_data, "ebitda"))
    if adjusted is None:
        adjusted = reported

    total_adjustments = adjusted - reported if reported is not None else None
    return {
        "version": (
            "adjusted_ebitda_build_up_v3"
            if reported is None
            or any(
                row["status"]
                in {
                    "unpriced_duplicate_adjustment_identity",
                    "unpriced_conflicting_adjustment_identity",
                }
                for row in adjustment_rows
            )
            else "adjusted_ebitda_build_up_v2"
        ),
        "basis": "EBITDA",
        "reported_ebitda": reported,
        "adjusted_ebitda": adjusted,
        "normalized_ebitda": adjusted,
        "total_adjustments": total_adjustments,
        "adjustments": adjustment_rows,
        "applied_adjustment_count": sum(1 for row in adjustment_rows if row["applied"]),
        "pending_adjustment_count": sum(1 for row in adjustment_rows if not row["applied"]),
        "is_adjusted": reported is None
        or bool(total_adjustments)
        or any(row["applied"] for row in adjustment_rows),
        "reported_basis_available": reported is not None,
        "normalized_flag": normalized_flag,
        "source": (
            "current_year.ebitda_normalization_metadata" if metadata else "current_year.ebitda"
        ),
    }


def _build_ebitda_adjustment_rows(adjustments: object) -> list[JsonMap]:
    if not isinstance(adjustments, list):
        return []

    rows: list[JsonMap] = []
    for raw in adjustments:
        if not isinstance(raw, Mapping):
            continue
        explicit_signed = raw.get("signed_amount") is not None
        parsed_amount = _normalization_decimal(
            raw.get("signed_amount") if explicit_signed else raw.get("amount")
        )
        amount = parsed_amount if parsed_amount is not None else Decimal("0")
        adjustment_type = str(raw.get("type") or "add").strip().lower()
        signed_amount = (
            amount
            if explicit_signed
            else (
                -abs(amount) if adjustment_type in {"subtract", "deduct", "minus"} else abs(amount)
            )
        )
        adjustment_type = "subtract" if signed_amount < 0 else "add"
        status = _normalization_status(raw.get("status"))
        applied = parsed_amount is not None and status in {
            "accepted",
            "approved",
            "applied",
            "confirmed",
            "verified",
        }
        rows.append(
            {
                "id": raw.get("decision_id") or raw.get("id"),
                "evidence_id": raw.get("evidence_id"),
                "fiscal_year": raw.get("fiscal_year"),
                "currency": raw.get("currency"),
                "label": raw.get("label")
                or raw.get("name")
                or raw.get("category")
                or "EBITDA adjustment",
                "category": raw.get("category") or raw.get("type") or "other",
                "amount": abs(amount),
                "type": adjustment_type,
                "signed_amount": signed_amount,
                "rationale": raw.get("rationale") or raw.get("description"),
                "source": raw.get("source"),
                "status": (
                    "unpriced_amount_missing_or_invalid"
                    if parsed_amount is None
                    else status or "proposed"
                ),
                "applied": applied,
            }
        )
    # One identity denotes one decision in this annual ledger. Preserve every
    # transport row for audit, but price an identical repeat only once. If the
    # same identity carries conflicting economics or approval states, none can
    # price until the caller resolves the revision; list order is not authority.
    identified: dict[str, list[JsonMap]] = {}
    for row in rows:
        identity = row.get("id")
        if isinstance(identity, str) and identity.strip():
            identified.setdefault(identity.strip(), []).append(row)
    for group in identified.values():
        if len(group) < 2:
            continue
        fingerprints = {
            (
                row["signed_amount"],
                *(
                    str(row.get(key))
                    for key in (
                        "status",
                        "category",
                        "currency",
                        "fiscal_year",
                        "evidence_id",
                    )
                ),
            )
            for row in group
        }
        conflicting = len(fingerprints) > 1
        for row in group if conflicting else group[1:]:
            row["applied"] = False
            row["status"] = (
                "unpriced_conflicting_adjustment_identity"
                if conflicting
                else "unpriced_duplicate_adjustment_identity"
            )
    return rows


def _normalization_status(value: object) -> str:
    if not isinstance(value, str):
        return ""
    return re.sub(r"[\s\-]+", "_", value.strip().lower())


def _attr(obj: object, attr: str) -> object:
    if isinstance(obj, Mapping):
        return obj.get(attr)
    return getattr(obj, attr, None)


def _first_provided_segment_decimal(
    segment: Mapping[str, object], fields: Sequence[str]
) -> Decimal | None:
    for field in fields:
        if segment.get(field) is not None:
            # An invalid selected amount is unavailable, not an invitation to
            # choose another metric or manufacture zero.
            return _normalization_decimal(segment[field])
    return None


def build_sotp_segments(raw_segments: Sequence[Mapping[str, object]] | None) -> JsonMap | None:
    """Build a true SOTP segment summary when segment earnings are supplied."""
    if not raw_segments:
        return None

    rows: list[JsonMap] = []
    missing_inputs = False
    total_ev = Decimal("0")
    for index, segment in enumerate(raw_segments):
        basis = normalize_earnings_basis(segment.get("basis") or segment.get("earnings_basis"))
        metric_fields = {
            "EBITDA": ("adjusted_ebitda", "ebitda"),
            "EBIT": ("ebit",),
            "SDE": ("sde",),
            "Revenue": ("revenue",),
        }.get(basis, ("adjusted_ebitda", "ebitda", "revenue"))
        # An explicit zero is a financial observation. Never substitute revenue
        # for a missing EBITDA basis, or switch metrics because zero is falsey.
        earnings = _first_provided_segment_decimal(
            segment, ("earnings", "adjusted_earnings", *metric_fields)
        )
        multiple = _first_provided_segment_decimal(segment, ("multiple", "applied_multiple"))
        value = earnings * multiple if earnings is not None and multiple is not None else None
        if value is None:
            missing_inputs = True
        else:
            total_ev += value
        rows.append(
            {
                "index": index,
                "business_type_id": segment.get("business_type_id"),
                "business_type_title": segment.get("business_type_title") or segment.get("title"),
                "nace_code": segment.get("nace_code"),
                "basis": basis,
                "earnings": earnings,
                "multiple": multiple,
                "enterprise_value": value,
                "input_weight": _optional_decimal(segment.get("weight")),
                "weight": None,
            }
        )

    if not missing_inputs and total_ev > Decimal("0"):
        for row in rows:
            row_value = _optional_decimal(row.get("enterprise_value")) or Decimal("0")
            row["weight"] = row_value / total_ev
    else:
        for row in rows:
            row["weight"] = row.get("input_weight")

    return {
        "mode": "weighted_blend_fallback" if missing_inputs else "true_sotp",
        "enterprise_value": None if missing_inputs else total_ev,
        "segments": rows,
        "requires_segment_earnings": missing_inputs,
        "weight_policy": "derived_from_segment_ev" if not missing_inputs else "input_fallback",
    }


def build_pipeline_multiple_build_up(
    multiple_pipeline: Mapping[str, object] | None,
    *,
    advisor_override: Mapping[str, object] | None = None,
    segment_valuation: Mapping[str, object] | None = None,
) -> JsonMap | None:
    """Build one canonical build-up object from the Step 11 pipeline."""
    if not multiple_pipeline:
        return None
    metric_type = multiple_pipeline.get("metric_type")
    initial_mid = _optional_decimal(
        multiple_pipeline.get("initial_multiple_mid") or multiple_pipeline.get("initial_multiple")
    )
    final_mid = _optional_decimal(
        multiple_pipeline.get("final_multiple_mid") or multiple_pipeline.get("final_multiple")
    )
    if initial_mid is None and final_mid is None:
        return None

    return {
        "version": "multiple_build_up_v1",
        "earnings_basis": normalize_earnings_basis(metric_type),
        "metric_type": metric_type,
        "metric_value": _optional_decimal(multiple_pipeline.get("metric_value")),
        "reported_ebitda": _optional_decimal(multiple_pipeline.get("reported_ebitda")),
        "adjusted_ebitda": _optional_decimal(multiple_pipeline.get("adjusted_ebitda")),
        "adjusted_ebitda_build_up": dict(multiple_pipeline.get("adjusted_ebitda_build_up") or {}),
        "initial_multiple": initial_mid,
        "final_multiple": final_mid,
        "total_reduction_percentage": _optional_decimal(
            multiple_pipeline.get("total_reduction_percentage")
        ),
        "discount_waterfall": list(multiple_pipeline.get("discount_waterfall") or []),
        "stages": list(multiple_pipeline.get("stages") or []),
        "advisor_override": dict(advisor_override or {}),
        "segment_valuation": dict(segment_valuation or {}),
        "source": "step_11_multiple_pipeline",
    }
