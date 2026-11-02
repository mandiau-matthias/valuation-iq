"""Shared EBITDA normalization policy helpers for report builders."""

import re
from decimal import Decimal
from typing import Optional, Sequence, cast

from src.services.reports.protocol_adapter import DictWrapper, _attr, _unwrap
from src.utils.decimal_helpers import optional_decimal, safe_decimal_or_zero

NORMALIZATION_RESULT_KEYS = (
    "normalization",
    "ebitda_normalization",
    "ebitda_normalization_results",
    "normalization_result",
    "step_2_5_multiple_calibration",
    "step_2_5_ebitda_normalization",
)

JsonMap = dict[str, object]


def normalization_result_from_detailed_results(detailed_results: object) -> JsonMap:
    """Extract the first populated EBITDA normalization payload."""
    unwrapped = _unwrap(detailed_results)
    if not isinstance(unwrapped, dict):
        return {}

    for key in NORMALIZATION_RESULT_KEYS:
        candidate = _unwrap(unwrapped.get(key))
        if isinstance(candidate, dict) and candidate:
            return cast(JsonMap, candidate)
    return {}


def normalization_result_from_response(response: object) -> JsonMap:
    """Extract normalization payload from a valuation response."""
    return normalization_result_from_detailed_results(getattr(response, "detailed_results", None))


def current_year_normalization_metadata(request: object | None) -> JsonMap:
    """Return request-side normalization metadata for the current/base year."""
    if not request or not _attr(request, "current_year_data", None):
        return {}

    metadata = _unwrap(_attr(request.current_year_data, "ebitda_normalization_metadata", None))
    return cast(JsonMap, metadata) if isinstance(metadata, dict) else {}


def current_year_is_ebitda_normalized(request: object | None) -> bool:
    """Return True when current-year EBITDA is flagged as already normalized."""
    current_year_data = _attr(request, "current_year_data", None) if request else None
    return bool(_attr(current_year_data, "ebitda_normalized", False))


# Statuses that mark an EBITDA adjustment as a *proposal / candidate* that has
# NOT been accepted by an advisor — it must NOT be counted as an applied
# normalization (i.e. it must not move the normalized EBITDA, the "Totale
# aanpassingen" total, or the normalization waterfall). Anything outside this
# set — including a missing/empty status, "approved", "applied", "accepted" or
# "confirmed" — is treated as applied so advisor-confirmed flows are unchanged.
# This is the fix for the advisor page-4 contradiction where Hermes-detected
# candidates ("status": "pending") were summed into "Totale aanpassingen" while
# the normalized EBITDA (correctly) stayed equal to the reported EBITDA.
# Statuses that mark an adjustment as surfaced for advisor review but NOT yet
# decided. These drive the "candidates detected — advisor review required" note.
PENDING_REVIEW_STATUSES = frozenset(
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
    }
)
# Statuses that mark an adjustment as explicitly DECIDED against — rejected or
# excluded. Not applied, and not a pending candidate (the advisor already
# decided, so the report must not nag them to "review" it again).
DECIDED_NON_APPLIED_STATUSES = frozenset({"rejected", "declined", "excluded"})
# Union: anything here is excluded from the applied normalization (the normalized
# EBITDA, the "Totale aanpassingen" total, and the waterfall). Anything OUTSIDE
# this set — a missing/empty status, "approved", "applied", "accepted",
# "confirmed" — is treated as applied so advisor-confirmed flows are unchanged.
NON_APPLIED_ADJUSTMENT_STATUSES = PENDING_REVIEW_STATUSES | DECIDED_NON_APPLIED_STATUSES


def _adjustment_status(adjustment_data: object) -> str:
    """Return a canonical status token for an adjustment, or ''.

    Normalizes case, surrounding whitespace, and internal whitespace/hyphens to
    underscores so "Advisor Review Required", "advisor-review-required" and
    "advisor review required" all match the canonical "advisor_review_required".
    A non-string status (None/int/bool) resolves to '' — treated as applied, the
    backward-compatible default for advisor-confirmed flows that omit a status.
    """
    if isinstance(adjustment_data, DictWrapper):
        adjustment_data = _unwrap(adjustment_data)
    if not isinstance(adjustment_data, dict):
        return ""
    raw_status = adjustment_data.get("status")
    if not isinstance(raw_status, str):
        return ""
    return re.sub(r"[\s\-]+", "_", raw_status.strip().lower())


def is_adjustment_applied(adjustment_data: object) -> bool:
    """Return True when an EBITDA adjustment is applied (vs a pending/decided candidate).

    Backward-compatible: a missing/empty status counts as applied so existing
    advisor-confirmed flows (which often omit a status) keep working.
    """
    return _adjustment_status(adjustment_data) not in NON_APPLIED_ADJUSTMENT_STATUSES


def is_adjustment_pending_review(adjustment_data: object) -> bool:
    """Return True when an adjustment is a pending candidate awaiting advisor review.

    Distinct from rejected/excluded (already decided) — only pending items drive
    the "candidates detected, not applied" note so a decided item is never
    re-surfaced as needing review.
    """
    return _adjustment_status(adjustment_data) in PENDING_REVIEW_STATUSES


def sum_signed_adjustments(adjustments: object, *, applied_only: bool = False) -> Decimal:
    """Sum normalization adjustments while preserving add/subtract direction.

    When ``applied_only`` is True, pending/candidate adjustments (see
    ``NON_APPLIED_ADJUSTMENT_STATUSES``) are skipped so the total reflects only
    advisor-accepted normalizations.
    """
    if isinstance(adjustments, DictWrapper):
        adjustments = _unwrap(adjustments)
    if not isinstance(adjustments, list):
        return Decimal("0")

    total = Decimal("0")
    for adjustment in adjustments:
        adjustment_data = _unwrap(adjustment) if isinstance(adjustment, DictWrapper) else adjustment
        if not isinstance(adjustment_data, dict):
            continue
        if applied_only and not is_adjustment_applied(adjustment_data):
            continue
        raw_amount = safe_decimal_or_zero(adjustment_data.get("amount", 0))
        adjustment_type = adjustment_data.get("type")
        if adjustment_type is not None:
            amount = abs(raw_amount)
            if str(adjustment_type).lower() in {
                "subtract",
                "deduct",
                "minus",
                "negative",
            }:
                total -= amount
            else:
                total += amount
        else:
            total += raw_amount

    return total


def summarize_proposed_adjustments(adjustments: object) -> tuple[Decimal, int]:
    """Return ``(signed_total, count)`` of NON-applied (candidate) adjustments.

    Used to render an honest "candidates detected but not applied — advisor
    review required" note instead of silently dropping Hermes-detected
    normalization candidates from the report.
    """
    if isinstance(adjustments, DictWrapper):
        adjustments = _unwrap(adjustments)
    if not isinstance(adjustments, list):
        return Decimal("0"), 0

    total = Decimal("0")
    count = 0
    for adjustment in adjustments:
        adjustment_data = _unwrap(adjustment) if isinstance(adjustment, DictWrapper) else adjustment
        if not isinstance(adjustment_data, dict):
            continue
        # Only pending-review candidates count — a rejected/excluded item is
        # decided, so it must not be re-surfaced as "advisor review required".
        if not is_adjustment_pending_review(adjustment_data):
            continue
        raw_amount = safe_decimal_or_zero(adjustment_data.get("amount", 0))
        adjustment_type = adjustment_data.get("type")
        if adjustment_type is not None:
            amount = abs(raw_amount)
            if str(adjustment_type).lower() in {
                "subtract",
                "deduct",
                "minus",
                "negative",
            }:
                total -= amount
            else:
                total += amount
        else:
            total += raw_amount
        count += 1

    return total, count


def has_explicit_normalization_metadata(
    normalization_metadata: JsonMap | None,
    normalized_flag: bool = False,
) -> bool:
    """Return True when metadata reflects a real normalization action."""
    if not isinstance(normalization_metadata, dict):
        return False
    if normalized_flag:
        return True
    if normalization_metadata.get("normalized_ebitda") is not None:
        return True
    if normalization_metadata.get("sustainable_ebitda") is not None:
        return True
    adjustments = normalization_metadata.get("adjustments")
    if isinstance(adjustments, list) and len(adjustments) > 0:
        return True
    if normalization_metadata.get("has_custom_adjustments") is True:
        return True
    return False


def derive_normalized_ebitda(
    reported_ebitda: Decimal,
    normalization_metadata: JsonMap | None,
    normalized_flag: bool = False,
) -> Optional[Decimal]:
    """Resolve normalized EBITDA from explicit values, totals, or raw adjustments."""
    if not isinstance(normalization_metadata, dict):
        return reported_ebitda if normalized_flag else None

    if not has_explicit_normalization_metadata(
        normalization_metadata,
        normalized_flag,
    ):
        return None

    normalized_value = normalization_metadata.get("normalized_ebitda")
    if normalized_value is None:
        normalized_value = normalization_metadata.get("sustainable_ebitda")
    parsed_normalized_value = optional_decimal(normalized_value)
    if parsed_normalized_value is not None:
        return cast(Decimal, parsed_normalized_value)

    total_adjustments = normalization_metadata.get("total_adjustments")
    parsed_total_adjustments = optional_decimal(total_adjustments)
    if parsed_total_adjustments is not None:
        return reported_ebitda + cast(Decimal, parsed_total_adjustments)

    # applied_only: pending/rejected candidates must NOT move the normalized
    # EBITDA — otherwise the metadata path re-opens the advisor contradiction
    # (normalized ≠ reported on the stat card while "Totale aanpassingen" = €0).
    adjustment_total = sum_signed_adjustments(
        normalization_metadata.get("adjustments"), applied_only=True
    )
    if adjustment_total != Decimal("0"):
        return reported_ebitda + adjustment_total

    return reported_ebitda if normalization_metadata.get("adjustments") else None


def compute_explicit_total_adjustments(
    *,
    request: object | None,
    normalization: JsonMap,
    reported_ebitda: Decimal,
    latest_year_normalized: Decimal,
) -> Decimal:
    """Return user-entered EBITDA adjustments, excluding multi-year weighting effects."""
    if not request or not _attr(request, "current_year_data", None):
        return Decimal("0")

    normalization_metadata = current_year_normalization_metadata(request)
    normalized_flag = current_year_is_ebitda_normalized(request)
    has_custom = (
        bool(normalization_metadata.get("has_custom_adjustments"))
        if normalization_metadata
        else False
    )

    metadata_adjustments = (
        normalization_metadata.get("adjustments")
        if isinstance(normalization_metadata, dict)
        else None
    )
    if isinstance(metadata_adjustments, list) and len(metadata_adjustments) > 0:
        return sum_signed_adjustments(metadata_adjustments, applied_only=True)

    response_adjustments = (
        normalization.get("adjustments") if isinstance(normalization, dict) else None
    )
    if isinstance(response_adjustments, list) and len(response_adjustments) > 0:
        return sum_signed_adjustments(response_adjustments, applied_only=True)

    if not (normalized_flag or has_custom):
        return Decimal("0")

    if not has_explicit_normalization_metadata(normalization_metadata, normalized_flag):
        return Decimal("0")

    metadata_total_adjustments = optional_decimal(normalization_metadata.get("total_adjustments"))
    if metadata_total_adjustments is not None:
        return cast(Decimal, metadata_total_adjustments)

    return latest_year_normalized - reported_ebitda


def latest_year_normalized_for_display(
    *,
    request: object | None,
    reported_ebitda: Decimal,
    multi_year_data: Sequence[object] | None,
    normalized_key: str = "normalized_ebitda",
) -> Decimal:
    """Return latest-year normalized EBITDA, not the weighted valuation basis."""
    if multi_year_data:
        first_row = _unwrap(multi_year_data[0])
        if isinstance(first_row, dict):
            return cast(Decimal, safe_decimal_or_zero(first_row[normalized_key]))
        return cast(Decimal, safe_decimal_or_zero(_attr(first_row, normalized_key, None)))

    current_year_data = _attr(request, "current_year_data", None) if request else None
    if current_year_data is None:
        return reported_ebitda

    normalization_metadata = current_year_normalization_metadata(request)
    normalized_flag = current_year_is_ebitda_normalized(request)
    derived = derive_normalized_ebitda(
        reported_ebitda,
        normalization_metadata,
        normalized_flag,
    )
    if derived is not None:
        return derived

    raw_current_year_ebitda = _attr(current_year_data, "ebitda", None)
    if raw_current_year_ebitda is not None:
        return cast(Decimal, safe_decimal_or_zero(raw_current_year_ebitda))

    return reported_ebitda
