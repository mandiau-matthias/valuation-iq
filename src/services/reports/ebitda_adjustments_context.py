"""EBITDA adjustment-table context builders for reports."""

from collections.abc import Callable, Mapping
from decimal import Decimal
from logging import Logger

from src.services.infrastructure.translations import EbitdaAdjustmentLabels
from src.services.reports.ebitda_normalization import (
    current_year_is_ebitda_normalized,
    has_explicit_normalization_metadata,
    is_adjustment_applied,
)
from src.services.reports.protocol_adapter import DictWrapper, _attr, _unwrap
from src.utils.decimal_helpers import optional_decimal, safe_decimal_or_zero, safe_float
from src.utils.financial_terms import get_manual_input_label, get_trial_balance_label

JsonMap = dict[str, object]

ACCOUNTING_SOURCE_ALIASES: dict[str, str] = {
    "exact online": "exact",
    "exact_online": "exact",
    "exactonline": "exact",
    "manual_input": "manual",
    "manual input": "manual",
    "manueel": "manual",
}


def _as_json_map(value: object) -> JsonMap | None:
    if not isinstance(value, dict):
        return None
    return {str(key): item for key, item in value.items()}


def _normalize_accounting_source(source: object) -> str:
    raw = str(source or "").strip().lower()
    if not raw:
        return "manual"
    return ACCOUNTING_SOURCE_ALIASES.get(raw, raw)


def _base_source_context(
    *,
    accounting_provider: object,
    country_code: str,
    locale: str,
    current_year: int,
) -> tuple[str, str]:
    source = _normalize_accounting_source(accounting_provider)
    if source == "manual":
        return source, get_manual_input_label(locale, current_year)
    return source, get_trial_balance_label(
        country_code,
        locale,
        current_year,
        source=source,
    )


def _log_ebitda_divergence_if_needed(
    *,
    request: object | None,
    current_year_metadata: Mapping[str, object],
    current_year_is_normalized: bool,
    logger: Logger,
) -> None:
    try:
        current_year_data = _attr(request, "current_year_data", None) if request else None
        if not current_year_data:
            return

        bare_ebitda = optional_decimal(_attr(current_year_data, "ebitda", None))
        metadata_normalized = optional_decimal(current_year_metadata.get("normalized_ebitda"))
        if (
            bare_ebitda is not None
            and metadata_normalized is not None
            and abs(bare_ebitda - metadata_normalized) > Decimal("1")
        ):
            logger.error(
                "[REPORT-EBITDA-DIVERGENCE] current_year_data.ebitda disagrees with "
                "ebitda_normalization_metadata.normalized_ebitda; the EBITDA bridge may "
                "render an inconsistent picture vs the underlying calculation record.",
                extra={
                    "year": _attr(current_year_data, "year", None),
                    "bare_ebitda_field": float(bare_ebitda),
                    "metadata_normalized_ebitda": float(metadata_normalized),
                    "delta": float(metadata_normalized - bare_ebitda),
                    "ebitda_normalized_flag": current_year_is_normalized,
                    "remediation": (
                        "Frontend buildValuationRequest should write the post-adjustment "
                        "value into both current_year_data.ebitda and "
                        "ebitda_normalization_metadata.normalized_ebitda."
                    ),
                },
            )
    except Exception:
        return


def _preferred_adjustments(
    *,
    normalization: Mapping[str, object],
    current_year_metadata: Mapping[str, object],
    current_year_is_normalized: bool,
) -> tuple[object, str]:
    if has_explicit_normalization_metadata(
        current_year_metadata,
        current_year_is_normalized,
    ) and isinstance(current_year_metadata.get("adjustments"), list):
        return current_year_metadata.get("adjustments", []), "metadata"
    return normalization.get("adjustments", []), "response"


_REPORTED_BASIS_WORDS = (
    ("Genormaliseerde", "Gerapporteerde"),
    ("Normalized", "Reported"),
    ("Normalised", "Reported"),
    ("normalise", "declare"),
)


def _has_adjustment_rows(rows: list[JsonMap]) -> bool:
    return any(
        str(row.get("type") or "").strip().lower() not in {"base", "result"} for row in rows
    )


def _result_row_label(labels: EbitdaAdjustmentLabels, current_year: int, has_adjustments: bool) -> str:
    """Name the result row for what it is.

    The row used to be labelled "Genormaliseerde EBITDA ({year})" unconditionally —
    including on a run with no adjustment at all, where the figure IS the reported
    EBITDA. Same rule as the cover and the waterfall: "genormaliseerd" has to be
    earned by an applied adjustment.
    """
    label = labels.normalized_ebitda_year.format(year=current_year)
    if has_adjustments:
        return label
    for normalized_word, reported_word in _REPORTED_BASIS_WORDS:
        label = label.replace(normalized_word, reported_word)
    return label


def build_main_ebitda_adjustments(
    *,
    request: object | None,
    reported_ebitda: Decimal | None,
    normalized_ebitda: Decimal | None,
    locale: str,
    labels: EbitdaAdjustmentLabels,
    current_year: int,
    country_code: str,
    normalization: Mapping[str, object],
    current_year_metadata: Mapping[str, object],
    logger: Logger,
) -> list[JsonMap]:
    """Build the main-report EBITDA adjustments table rows."""
    adjustments: list[JsonMap] = []
    accounting_provider = (
        getattr(request, "accounting_provider", None) if request is not None else None
    )
    base_source, source_ref_label = _base_source_context(
        accounting_provider=accounting_provider,
        country_code=country_code,
        locale=locale,
        current_year=current_year,
    )

    if reported_ebitda is not None:
        adjustments.append(
            {
                "id": "base",
                "label": labels.reported_ebitda_year.format(year=current_year),
                "value": safe_float(reported_ebitda),
                "type": "base",
                "category": "base",
                "source": base_source,
                "source_ref": source_ref_label,
                "status": "approved",
                "approved_by": None,
                "description": None,
            }
        )

    current_year_is_normalized = current_year_is_ebitda_normalized(request)
    _log_ebitda_divergence_if_needed(
        request=request,
        current_year_metadata=current_year_metadata,
        current_year_is_normalized=current_year_is_normalized,
        logger=logger,
    )

    raw_adjustments, raw_adjustment_source = _preferred_adjustments(
        normalization=normalization,
        current_year_metadata=current_year_metadata,
        current_year_is_normalized=current_year_is_normalized,
    )

    if isinstance(raw_adjustments, list):
        for index, adjustment in enumerate(raw_adjustments):
            adjustment_data = (
                _unwrap(adjustment) if isinstance(adjustment, DictWrapper) else adjustment
            )
            adjustment_map = _as_json_map(adjustment_data)
            if adjustment_map is None:
                continue
            # Pending/candidate normalizations (e.g. Hermes-detected related-party
            # rent flagged for advisor review) must NOT render as applied add-back
            # rows in the bridge/waterfall — that produced the "+€X total but
            # normalized == reported" contradiction. They are surfaced separately
            # via the normalization-candidates note + the audit-trail page.
            if not is_adjustment_applied(adjustment_map):
                continue
            amount = safe_decimal_or_zero(adjustment_map.get("amount", 0))
            adjustment_type = adjustment_map.get("type")
            if adjustment_type is None:
                adjustment_type = "subtract" if amount < 0 else "add"
            adjustments.append(
                {
                    "id": f"adj-{index}",
                    "label": adjustment_map.get("label", labels.adj_fallback),
                    "value": abs(safe_float(amount)),
                    "type": adjustment_type,
                    "category": adjustment_map.get("category", "owner"),
                    "description": adjustment_map.get("description"),
                    "source": (
                        "metadata"
                        if raw_adjustment_source == "metadata"
                        else adjustment_map.get("source", "manual")
                    ),
                    "source_ref": (
                        labels.submitted_metadata
                        if raw_adjustment_source == "metadata"
                        else adjustment_map.get("source_ref")
                    ),
                    "status": adjustment_map.get("status", "approved"),
                    "approved_by": adjustment_map.get("approved_by"),
                }
            )

    if (
        len(adjustments) == 1
        and reported_ebitda is not None
        and normalized_ebitda is not None
        and has_explicit_normalization_metadata(
            current_year_metadata,
            current_year_is_normalized,
        )
    ):
        metadata_total_adjustments = safe_decimal_or_zero(
            current_year_metadata.get("total_adjustments", 0)
        )
        diff = (
            metadata_total_adjustments
            if metadata_total_adjustments != Decimal("0")
            else normalized_ebitda - reported_ebitda
        )
        if diff != 0:
            adjustment_count = current_year_metadata.get("adjustment_count")
            auto_description = (
                labels.auto_desc_count_template.format(count=adjustment_count)
                if adjustment_count
                else labels.auto_desc_aggregate
            )
            adjustments.append(
                {
                    "id": "adj-auto",
                    "label": labels.total_normalization_label,
                    "value": abs(safe_float(diff)),
                    "type": "add" if diff > 0 else "subtract",
                    "category": "owner",
                    "description": auto_description,
                    "source": "metadata",
                    "source_ref": labels.submitted_metadata,
                    "status": "approved",
                    "approved_by": None,
                }
            )

    if normalized_ebitda is not None:
        adjustments.append(
            {
                "id": "result",
                "label": _result_row_label(
                    labels, current_year, has_adjustments=_has_adjustment_rows(adjustments)
                ),
                "value": safe_float(normalized_ebitda),
                "type": "result",
                "category": "result",
                "source": None,
                "source_ref": None,
                "status": None,
                "approved_by": None,
                "description": None,
            }
        )

    return adjustments


def _simplified_base_adjustment_row(
    *,
    reported_ebitda: Decimal | None,
    labels: EbitdaAdjustmentLabels,
    current_year: int,
    base_source: str,
    source_ref_label: str,
    format_currency: Callable[[Decimal | None], str],
) -> JsonMap | None:
    if reported_ebitda is None:
        return None
    return {
        "label": labels.reported_ebitda_year.format(year=current_year),
        "amount": reported_ebitda,
        "amount_formatted": format_currency(reported_ebitda),
        "type": "base",
        "category": "base",
        "source": base_source,
        "source_ref": source_ref_label,
        "status": "approved",
    }


def _iter_applied_adjustment_maps(raw_adjustments: object) -> list[JsonMap]:
    if not isinstance(raw_adjustments, list):
        return []

    adjustment_maps: list[JsonMap] = []
    for adjustment in raw_adjustments:
        adjustment_data = _unwrap(adjustment) if isinstance(adjustment, DictWrapper) else adjustment
        adjustment_map = _as_json_map(adjustment_data)
        if adjustment_map is not None and is_adjustment_applied(adjustment_map):
            adjustment_maps.append(adjustment_map)
    return adjustment_maps


def _simplified_source_value(
    adjustment_map: JsonMap,
    *,
    raw_adjustment_source: str,
) -> object:
    if raw_adjustment_source == "metadata":
        return "metadata"
    return adjustment_map.get("source", "manual")


def _simplified_source_ref_value(
    adjustment_map: JsonMap,
    *,
    raw_adjustment_source: str,
    labels: EbitdaAdjustmentLabels,
) -> object:
    if raw_adjustment_source == "metadata":
        return labels.submitted_metadata
    return adjustment_map.get("source_ref")


def _simplified_adjustment_row(
    adjustment_map: JsonMap,
    *,
    raw_adjustment_source: str,
    labels: EbitdaAdjustmentLabels,
    format_currency: Callable[[Decimal | None], str],
) -> JsonMap:
    amount = safe_decimal_or_zero(adjustment_map.get("amount", 0))
    adjustment_type = adjustment_map.get("type")
    if adjustment_type is None:
        adjustment_type = "add" if amount >= 0 else "subtract"

    return {
        "label": adjustment_map.get("label") or adjustment_map.get("note") or labels.adj_fallback,
        "amount": abs(amount),
        "amount_formatted": format_currency(abs(amount)),
        "type": adjustment_type,
        "category": adjustment_map.get("category", "owner"),
        "description": adjustment_map.get("description") or adjustment_map.get("note"),
        "source": _simplified_source_value(
            adjustment_map,
            raw_adjustment_source=raw_adjustment_source,
        ),
        "source_ref": _simplified_source_ref_value(
            adjustment_map,
            raw_adjustment_source=raw_adjustment_source,
            labels=labels,
        ),
        "status": adjustment_map.get("status", "approved"),
        "approved_by": adjustment_map.get("approved_by"),
    }


def _simplified_adjustment_rows(
    raw_adjustments: object,
    *,
    raw_adjustment_source: str,
    labels: EbitdaAdjustmentLabels,
    format_currency: Callable[[Decimal | None], str],
) -> list[JsonMap]:
    return [
        _simplified_adjustment_row(
            adjustment_map,
            raw_adjustment_source=raw_adjustment_source,
            labels=labels,
            format_currency=format_currency,
        )
        for adjustment_map in _iter_applied_adjustment_maps(raw_adjustments)
    ]


def _simplified_auto_adjustment_row(
    *,
    reported_ebitda: Decimal | None,
    normalized_ebitda: Decimal | None,
    current_year_metadata: Mapping[str, object],
    current_year_is_normalized: bool,
    labels: EbitdaAdjustmentLabels,
    format_currency: Callable[[Decimal | None], str],
) -> JsonMap | None:
    if reported_ebitda is None or normalized_ebitda is None:
        return None
    if not has_explicit_normalization_metadata(current_year_metadata, current_year_is_normalized):
        return None

    diff = normalized_ebitda - reported_ebitda
    if diff == 0:
        return None

    adjustment_count = current_year_metadata.get("adjustment_count")
    description = (
        labels.auto_desc_count_template.format(count=adjustment_count)
        if adjustment_count
        else labels.auto_desc_aggregate
    )
    return {
        "label": labels.total_normalization_label,
        "amount": abs(diff),
        "amount_formatted": format_currency(abs(diff)),
        "type": "add" if diff > 0 else "subtract",
        "category": "owner",
        "description": description,
        "source": "metadata",
        "source_ref": labels.submitted_metadata,
        "status": "approved",
    }


def _simplified_result_adjustment_row(
    *,
    normalized_ebitda: Decimal | None,
    labels: EbitdaAdjustmentLabels,
    current_year: int,
    format_currency: Callable[[Decimal | None], str],
    has_adjustments: bool = True,
) -> JsonMap | None:
    if normalized_ebitda is None:
        return None
    return {
        "label": _result_row_label(labels, current_year, has_adjustments=has_adjustments),
        "amount": normalized_ebitda,
        "amount_formatted": format_currency(normalized_ebitda),
        "type": "result",
        "category": "result",
    }


def build_simplified_ebitda_adjustments(
    *,
    request: object | None,
    reported_ebitda: Decimal | None,
    normalized_ebitda: Decimal | None,
    locale: str,
    labels: EbitdaAdjustmentLabels,
    current_year: int,
    country_code: str,
    normalization: Mapping[str, object],
    current_year_metadata: Mapping[str, object],
    format_currency: Callable[[Decimal | None], str],
) -> list[JsonMap]:
    """Build simplified-report EBITDA adjustments rows."""
    adjustments: list[JsonMap] = []
    accounting_provider = (
        getattr(request, "accounting_provider", None) if request is not None else None
    )
    base_source, source_ref_label = _base_source_context(
        accounting_provider=accounting_provider,
        country_code=country_code,
        locale=locale,
        current_year=current_year,
    )

    base_row = _simplified_base_adjustment_row(
        reported_ebitda=reported_ebitda,
        labels=labels,
        current_year=current_year,
        base_source=base_source,
        source_ref_label=source_ref_label,
        format_currency=format_currency,
    )
    if base_row:
        adjustments.append(base_row)

    current_year_is_normalized = current_year_is_ebitda_normalized(request)
    raw_adjustments, raw_adjustment_source = _preferred_adjustments(
        normalization=normalization,
        current_year_metadata=current_year_metadata,
        current_year_is_normalized=current_year_is_normalized,
    )
    adjustments.extend(
        _simplified_adjustment_rows(
            raw_adjustments,
            raw_adjustment_source=raw_adjustment_source,
            labels=labels,
            format_currency=format_currency,
        )
    )

    auto_row = (
        _simplified_auto_adjustment_row(
            reported_ebitda=reported_ebitda,
            normalized_ebitda=normalized_ebitda,
            current_year_metadata=current_year_metadata,
            current_year_is_normalized=current_year_is_normalized,
            labels=labels,
            format_currency=format_currency,
        )
        if len(adjustments) == 1
        else None
    )
    if auto_row:
        adjustments.append(auto_row)

    result_row = _simplified_result_adjustment_row(
        normalized_ebitda=normalized_ebitda,
        labels=labels,
        current_year=current_year,
        format_currency=format_currency,
        has_adjustments=_has_adjustment_rows(adjustments),
    )
    if result_row:
        adjustments.append(result_row)

    return adjustments
