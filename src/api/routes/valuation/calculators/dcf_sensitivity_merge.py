"""
Shared DCF sensitivity rebuild + sanitization + engine fallback.

Used after manual overrides (or stateless post-processing) so orchestrated and
stateless APIs behave identically and stay validator-safe.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import cast

SensitivityMap = dict[object, object]
SensitivityMatrix = dict[str, object]
SensitivityTriple = tuple[SensitivityMap, SensitivityMap, SensitivityMatrix | None]


def _sensitivity_log_extra(
    *,
    extra_base: dict[str, object] | None,
    correlation_id: object,
    company: object,
) -> dict[str, object]:
    extra: dict[str, object] = dict(extra_base or {})
    if correlation_id is not None:
        extra["correlation_id"] = correlation_id
    if company is not None:
        extra["company"] = company
    return extra


def _map_or_empty(value: object) -> SensitivityMap:
    return cast(SensitivityMap, value) if isinstance(value, dict) else {}


def _safe_sanitize_matrix(
    raw: object,
    *,
    sanitize_matrix_2d: Callable[[object], SensitivityMatrix | None],
    logger: logging.Logger,
    extra: dict[str, object],
    matrix_sanitize_failed_message: str,
) -> SensitivityMatrix | None:
    try:
        return sanitize_matrix_2d(raw)
    except Exception as san_exc:
        logger.warning(
            matrix_sanitize_failed_message,
            extra={
                **extra,
                "error": str(san_exc),
                "error_type": type(san_exc).__name__,
                "reason": "matrix_sanitize_exception",
            },
            exc_info=True,
        )
        return None


def _validated_build_tuple(built: object) -> tuple[object, object, object]:
    if isinstance(built, tuple) and len(built) == 3:
        return built

    tup_len = len(built) if isinstance(built, tuple) else None
    raise TypeError(
        "DCF sensitivity build must return a 3-tuple (wacc_map, growth_map, matrix); "
        f"got {type(built).__name__}" + (f" with length={tup_len}" if tup_len is not None else "")
    )


def _finite_1d_maps(
    *,
    sensitivity_values_are_finite: Callable[[object], bool],
    sensitivity_wacc: object,
    sensitivity_growth: object,
) -> tuple[bool, Exception | None]:
    try:
        return (
            bool(
                sensitivity_values_are_finite(sensitivity_wacc)
                and sensitivity_values_are_finite(sensitivity_growth)
            ),
            None,
        )
    except Exception as fin_exc:
        return False, fin_exc


def _finite_failure_extra(
    extra: dict[str, object],
    *,
    finite_exc: Exception | None,
    reason_without_exception: str,
) -> dict[str, object]:
    log_extra: dict[str, object] = dict(extra)
    if finite_exc is not None:
        log_extra["error"] = str(finite_exc)
        log_extra["error_type"] = type(finite_exc).__name__
        log_extra["reason"] = "sensitivity_finite_check_exception"
    else:
        log_extra["reason"] = reason_without_exception
    return log_extra


def _engine_matrix_fallback(
    *,
    engine_matrix_2d: SensitivityMatrix | None,
    sanitize_matrix_2d: Callable[[object], SensitivityMatrix | None],
    logger: logging.Logger,
    extra: dict[str, object],
    matrix_sanitize_failed_message: str,
) -> SensitivityMatrix | None:
    return _safe_sanitize_matrix(
        engine_matrix_2d,
        sanitize_matrix_2d=sanitize_matrix_2d,
        logger=logger,
        extra=extra,
        matrix_sanitize_failed_message=matrix_sanitize_failed_message,
    )


def _restore_prior_for_empty_rebuild(
    *,
    sensitivity_wacc: SensitivityMap,
    sensitivity_growth: SensitivityMap,
    sensitivity_matrix_2d: SensitivityMatrix | None,
    prior_wacc: SensitivityMap,
    prior_growth: SensitivityMap,
) -> SensitivityTriple:
    if not sensitivity_wacc and not sensitivity_growth and sensitivity_matrix_2d is None:
        return prior_wacc, prior_growth, sensitivity_matrix_2d
    return sensitivity_wacc, sensitivity_growth, sensitivity_matrix_2d


def _merge_valid_build_output(
    *,
    built: object,
    sanitize_matrix_2d: Callable[[object], SensitivityMatrix | None],
    sensitivity_values_are_finite: Callable[[object], bool],
    prior_wacc: SensitivityMap,
    prior_growth: SensitivityMap,
    engine_matrix_2d: SensitivityMatrix | None,
    logger: logging.Logger,
    extra: dict[str, object],
    invalid_1d_maps_type_message: str,
    non_finite_rebuild_message: str,
    matrix_sanitize_failed_message: str,
) -> SensitivityTriple:
    sensitivity_wacc, sensitivity_growth, raw_matrix_2d = _validated_build_tuple(built)
    if not isinstance(sensitivity_wacc, dict) or not isinstance(sensitivity_growth, dict):
        logger.warning(
            invalid_1d_maps_type_message,
            extra={
                **extra,
                "reason": "sensitivity_1d_maps_not_dict",
                "wacc_type": type(sensitivity_wacc).__name__,
                "growth_type": type(sensitivity_growth).__name__,
            },
        )
        return (
            prior_wacc,
            prior_growth,
            _engine_matrix_fallback(
                engine_matrix_2d=engine_matrix_2d,
                sanitize_matrix_2d=sanitize_matrix_2d,
                logger=logger,
                extra=extra,
                matrix_sanitize_failed_message=matrix_sanitize_failed_message,
            ),
        )

    rebuilt_matrix = _safe_sanitize_matrix(
        raw_matrix_2d,
        sanitize_matrix_2d=sanitize_matrix_2d,
        logger=logger,
        extra=extra,
        matrix_sanitize_failed_message=matrix_sanitize_failed_message,
    )
    rebuilt_1d_ok, finite_exc = _finite_1d_maps(
        sensitivity_values_are_finite=sensitivity_values_are_finite,
        sensitivity_wacc=sensitivity_wacc,
        sensitivity_growth=sensitivity_growth,
    )
    if not rebuilt_1d_ok:
        logger.warning(
            non_finite_rebuild_message,
            extra=_finite_failure_extra(
                extra,
                finite_exc=finite_exc,
                reason_without_exception="sensitivity_rebuilt_1d_non_finite",
            ),
            exc_info=finite_exc is not None,
        )
        return (
            prior_wacc,
            prior_growth,
            _engine_matrix_fallback(
                engine_matrix_2d=engine_matrix_2d,
                sanitize_matrix_2d=sanitize_matrix_2d,
                logger=logger,
                extra=extra,
                matrix_sanitize_failed_message=matrix_sanitize_failed_message,
            ),
        )

    return _restore_prior_for_empty_rebuild(
        sensitivity_wacc=cast(SensitivityMap, sensitivity_wacc),
        sensitivity_growth=cast(SensitivityMap, sensitivity_growth),
        sensitivity_matrix_2d=rebuilt_matrix,
        prior_wacc=prior_wacc,
        prior_growth=prior_growth,
    )


def _build_failure_extra(extra: dict[str, object], exc: Exception) -> dict[str, object]:
    rebuild_extra: dict[str, object] = {
        **extra,
        "error": str(exc),
        "error_type": type(exc).__name__,
    }
    if isinstance(exc, TypeError) and "must return a 3-tuple" in str(exc):
        rebuild_extra["reason"] = "sensitivity_build_bad_return_shape"
    return rebuild_extra


def _finalize_sensitivity_payload(
    *,
    sensitivity_wacc: object,
    sensitivity_growth: object,
    sensitivity_matrix_2d: SensitivityMatrix | None,
    sensitivity_values_are_finite: Callable[[object], bool],
    logger: logging.Logger,
    extra: dict[str, object],
    final_clear_message: str,
) -> SensitivityTriple:
    final_maps_ok, final_exc = _finite_1d_maps(
        sensitivity_values_are_finite=sensitivity_values_are_finite,
        sensitivity_wacc=sensitivity_wacc,
        sensitivity_growth=sensitivity_growth,
    )
    if (
        final_maps_ok
        and isinstance(sensitivity_wacc, dict)
        and isinstance(sensitivity_growth, dict)
    ):
        return (
            cast(SensitivityMap, sensitivity_wacc),
            cast(SensitivityMap, sensitivity_growth),
            sensitivity_matrix_2d,
        )

    reason = (
        "sensitivity_merged_1d_not_dict"
        if not (isinstance(sensitivity_wacc, dict) and isinstance(sensitivity_growth, dict))
        else "sensitivity_merged_1d_non_finite"
    )
    logger.warning(
        final_clear_message,
        extra=_finite_failure_extra(
            extra,
            finite_exc=final_exc,
            reason_without_exception=reason,
        ),
        exc_info=final_exc is not None,
    )
    return {}, {}, None


def merge_rebuilt_dcf_sensitivity_payload(
    *,
    build: Callable[[], object],
    sanitize_matrix_2d: Callable[[object], SensitivityMatrix | None],
    sensitivity_values_are_finite: Callable[[object], bool],
    prior_wacc: object,
    prior_growth: object,
    engine_matrix_2d: SensitivityMatrix | None,
    logger: logging.Logger,
    correlation_id: object = None,
    company: object = None,
    rebuild_failure_message: str = "DCF API-layer sensitivity payload failed; using engine sensitivities",
    invalid_1d_maps_type_message: str = (
        "DCF API-layer sensitivity rebuild returned non-dict 1D maps; using engine sensitivities"
    ),
    non_finite_rebuild_message: str = (
        "DCF API-layer sensitivity maps contain non-finite or invalid numerics; "
        "using engine sensitivities"
    ),
    final_clear_message: str = (
        "DCF sensitivity maps failed finite check after merge; clearing 1D/2D sensitivity extras"
    ),
    matrix_sanitize_failed_message: str = (
        "DCF 2D sensitivity matrix sanitization failed; dropping matrix for this response"
    ),
    extra_base: dict[str, object] | None = None,
) -> SensitivityTriple:
    """
    Run ``build()`` (typically coordinator-backed), sanitize the 2D matrix, and fall back to
    engine priors when rebuild output is invalid or ``build`` raises.

    If either 1D map is not a dict, values are non-finite, or engine priors are still bad after
    fallback, returns empty 1D maps and no matrix (``{}, {}, None``).

    ``build()`` must return exactly ``(wacc_map, growth_map, matrix_2d_or_none)`` as a 3-item tuple.
    """
    extra = _sensitivity_log_extra(
        extra_base=extra_base,
        correlation_id=correlation_id,
        company=company,
    )
    prior_wacc = _map_or_empty(prior_wacc)
    prior_growth = _map_or_empty(prior_growth)

    try:
        sensitivity_wacc, sensitivity_growth, sensitivity_matrix_2d = _merge_valid_build_output(
            built=build(),
            sanitize_matrix_2d=sanitize_matrix_2d,
            sensitivity_values_are_finite=sensitivity_values_are_finite,
            prior_wacc=prior_wacc,
            prior_growth=prior_growth,
            engine_matrix_2d=engine_matrix_2d,
            logger=logger,
            extra=extra,
            invalid_1d_maps_type_message=invalid_1d_maps_type_message,
            non_finite_rebuild_message=non_finite_rebuild_message,
            matrix_sanitize_failed_message=matrix_sanitize_failed_message,
        )
    except Exception as exc:
        logger.warning(
            rebuild_failure_message,
            extra=_build_failure_extra(extra, exc),
            exc_info=True,
        )
        sensitivity_wacc = prior_wacc
        sensitivity_growth = prior_growth
        sensitivity_matrix_2d = _engine_matrix_fallback(
            engine_matrix_2d=engine_matrix_2d,
            sanitize_matrix_2d=sanitize_matrix_2d,
            logger=logger,
            extra=extra,
            matrix_sanitize_failed_message=matrix_sanitize_failed_message,
        )

    return _finalize_sensitivity_payload(
        sensitivity_wacc=sensitivity_wacc,
        sensitivity_growth=sensitivity_growth,
        sensitivity_matrix_2d=sensitivity_matrix_2d,
        sensitivity_values_are_finite=sensitivity_values_are_finite,
        logger=logger,
        extra=extra,
        final_clear_message=final_clear_message,
    )
