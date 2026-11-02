"""Pure gates for Upswitch Adaptive report composition (Pass-8 / Pass-9).

`has_upswitch_adaptive_page` decides whether the flagship adaptive chapter
renders. `is_adaptive_only_path` decides whether standalone DCF / EBITDA
dossier / weighted-synthesis sections are suppressed so the report reads as one
unified Adaptive narrative.

Presentation copy (executive summary, cover, calibration intro) keys off
``is_adaptive_only_path`` — **not** the ``is_hybrid`` flag from
``extract_methodology_weights`` in ``valuation_contract``, because the latter
is ``False`` when either DCF or multiples weight is zero even though the user is
still on the Upswitch Adaptive product path.

Numeric hybrid breakdown lines (e.g. "% multiples + % DCF" in the value hero) still
require ``is_hybrid`` so lone-weight compositions do not show a misleading blend formula.

These functions are the single source of truth — the aggregator assigns
their results onto the Jinja context; ``refresh_adaptive_gates_on_context``
runs again after ``apply_omni_calc_overrides`` so flags match the rendered
headline method. Unit tests import the same helpers instead of duplicating logic.
"""

from __future__ import annotations

from collections.abc import Mapping

from src.domain.valuation_contract import is_sde_method_key


def _norm_method(raw: str | None) -> str:
    return (raw or "").strip()


def coalesce_user_weights_for_gates(user_weights: object) -> object | None:
    """Treat an empty weight mapping like ``None`` for gate predicates.

    Some API layers serialize “no custom weights” as ``{}``; Python’s
    ``not {}`` is falsy in the wrong sense for ``is_single_method_override``
    (``not user_weights`` would be False, incorrectly blocking single-method
    detection). Normalize before any ``not user_weights`` checks.
    """
    if user_weights is None:
        return None
    if isinstance(user_weights, dict) and len(user_weights) == 0:
        return None
    return user_weights


def is_single_method_override(
    selected_method: str | None,
    user_weights: object,
) -> bool:
    """True when the accountant forced one engine method (not adaptive default).

    ``fiscal_4x`` and ``upswitch_adaptive`` are treated as non-overrides for
    the adaptive-page gate so the fiscal track and explicit adaptive pick can
    still co-render the flagship chapter.
    """
    user_weights = coalesce_user_weights_for_gates(user_weights)
    sm = _norm_method(selected_method)
    return bool(sm) and sm not in ("upswitch_adaptive", "fiscal_4x") and not user_weights


def compute_has_upswitch_adaptive_page(
    selected_method: str | None,
    user_weights: object,
    upswitch_adaptive_value: object,
) -> bool:
    """Whether ``pages/upswitch_adaptive_valuation.html`` should be included."""
    user_weights = coalesce_user_weights_for_gates(user_weights)
    # Custom weighted synthesis owns the narrative on this path.
    # Rendering the Adaptive flagship page as well duplicates method
    # explanation and confuses advisors ("why both adaptive + synthesis?").
    if user_weights:
        return False
    if is_single_method_override(selected_method, user_weights):
        return False
    if upswitch_adaptive_value is None:
        return False
    try:
        return float(upswitch_adaptive_value or 0) > 0
    except (TypeError, ValueError):
        return False


def compute_is_adaptive_only_path(
    selected_method: str | None,
    user_weights: object,
    has_upswitch_adaptive_page: bool,
) -> bool:
    """Whether to suppress parallel DCF / EBITDA / synthesis sections (Pass-9)."""
    user_weights = coalesce_user_weights_for_gates(user_weights)
    sm = _norm_method(selected_method)
    ov = is_single_method_override(selected_method, user_weights)
    return bool(
        sm in ("", "upswitch_adaptive")
        and not ov
        and not user_weights
        and has_upswitch_adaptive_page
    )


def _coerce_adaptive_dcf_weight(adaptive_dcf_weight: object) -> float:
    try:
        return float(adaptive_dcf_weight) if adaptive_dcf_weight is not None else 0.0
    except (TypeError, ValueError):
        return 0.0


def _coerce_optional_weight(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def stamp_adaptive_presentation_weights(context: dict[str, object]) -> None:
    """Stamp effective blend weights for template numeric display.

    ``adaptive_dcf_weight`` may reflect the user's requested hybrid split even
    when DCF did not execute (Creatief bureau / VAL-2026-35A4). Templates
    should prefer ``adaptive_presentation_*`` for blend math; raw keys stay
    available for audit and defensibility traces.
    """
    if context.get("is_adaptive_multiples_only"):
        context["adaptive_presentation_dcf_weight"] = 0.0
        mults = _coerce_optional_weight(context.get("adaptive_multiples_weight"))
        context["adaptive_presentation_multiples_weight"] = mults if mults and mults > 0 else 1.0
        return

    context["adaptive_presentation_dcf_weight"] = _coerce_optional_weight(
        context.get("adaptive_dcf_weight")
    )
    context["adaptive_presentation_multiples_weight"] = _coerce_optional_weight(
        context.get("adaptive_multiples_weight")
    )


def compute_is_adaptive_multiples_only(
    *,
    is_adaptive_only_path: bool,
    adaptive_dcf_weight: object = None,
    has_dcf: object = None,
    dcf_method_available: object = None,
) -> bool:
    """True when Adaptive is the lens and the headline ran multiples-only.

    Priority order:
    1. DCF method explicitly unavailable — diagnostics may exist, but the
       publishable headline leg is multiples-only.
    2. True hybrid: DCF executed (``has_dcf``) with a non-zero blend weight.
    3. DCF excluded from execution (``has_dcf is False``) — multiples-only even
       when a stale persisted snapshot still carries a non-zero hybrid weight
       (Creatief bureau / VAL-2026-35A4).
    4. Weight explicitly zero while on the Adaptive path.
    5. DCF dossier present but weight unknown — stay on hybrid framing.
    """
    if not is_adaptive_only_path:
        return False

    dcf_w = _coerce_adaptive_dcf_weight(adaptive_dcf_weight)
    weight_was_provided = adaptive_dcf_weight is not None

    if dcf_method_available is False:
        return True

    if has_dcf is True and dcf_w > 0:
        return False

    if has_dcf is False:
        return True

    if weight_was_provided and dcf_w == 0.0:
        return True

    return False


def resolve_effective_selected_method_for_report_gates(context: Mapping[str, object]) -> str:
    """Single effective method slug for Pass-8/9 after report-layer composition.

    When the method-override row is active (``show_method_override``), the
    override slug wins. A non-null ``method_override_selected_method`` with
    ``show_method_override`` falsy is treated as stale metadata and ignored.

    When ``multiple_metric_type`` is ``SDE``, the SDE primary (or canonical
    ``sde_multiple``) wins. When ``primary_method_key`` is the SDE engine key,
    that wins over a sole ``upswitch_adaptive`` / ``fiscal_4x`` / empty
    ``selected_method`` and no user blend weights — the pre-channel window
    before ``multiple_metric_type`` is stamped. Otherwise ``selected_method``
    then ``primary_method_key``.

    When ``ensure_sde_channel_applied`` runs after ``apply_omni_calc_overrides``,
    it stamps ``multiple_metric_type='SDE'`` and ``primary_method_key='sde_multiple'``
    while ``selected_method`` can still read ``upswitch_adaptive``. The SDE
    presentation is then authoritative for gates — otherwise Adaptive would
    stay on alongside an SDE-only cascade.
    """
    override_method = _active_method_override(context)
    if override_method:
        return override_method
    sde_metric_method = _sde_metric_method(context)
    if sde_metric_method:
        return sde_metric_method
    pre_channel_sde_method = _pre_channel_sde_method(context)
    if pre_channel_sde_method:
        return pre_channel_sde_method
    return _first_context_method(context, "selected_method", "primary_method_key")


def _active_method_override(context: Mapping[str, object]) -> str:
    if bool(context.get("show_method_override")) and context.get("method_override_selected_method"):
        return _norm_method(str(context["method_override_selected_method"]))
    return ""


def _sde_metric_method(context: Mapping[str, object]) -> str:
    if str(context.get("multiple_metric_type") or "").upper() == "SDE":
        pk = context.get("primary_method_key")
        pk_norm = _norm_method(str(pk)) if pk is not None else ""
        return pk_norm if pk_norm else "sde_multiple"
    return ""


def _pre_channel_sde_method(context: Mapping[str, object]) -> str:
    # Engine / aggregator may stamp ``primary_method_key='sde_multiple'`` before
    # ``multiple_metric_type`` is rewritten to SDE (pre-channel). Do not let a
    # lingering ``selected_method='upswitch_adaptive'`` win in that window.
    # Skip when the user forced another single method (e.g. DCF) or a custom blend.
    _pk_pre = context.get("primary_method_key")
    _sel_pre = _norm_method(str(context.get("selected_method") or ""))
    if (
        is_sde_method_key(_pk_pre)
        and _sel_pre in ("", "upswitch_adaptive", "fiscal_4x")
        and not coalesce_user_weights_for_gates(context.get("user_weights"))
    ):
        return _norm_method(str(_pk_pre))
    return ""


def _first_context_method(context: Mapping[str, object], *keys: str) -> str:
    for key in keys:
        raw = context.get(key)
        if raw is not None and _norm_method(str(raw)):
            return _norm_method(str(raw))
    return ""


def refresh_adaptive_gates_on_context(context: dict[str, object]) -> None:
    """Recompute ``has_upswitch_adaptive_page`` and ``is_adaptive_only_path``.

    Call after ``apply_omni_calc_overrides``, ``ensure_sde_channel_applied``, and
    similar report transforms so Pass-8/9 flags match the **rendered** headline method, not only the
    pre-override aggregation snapshot. Safe to call multiple times (idempotent
    given the same context).
    """
    sm = resolve_effective_selected_method_for_report_gates(context)
    uw = coalesce_user_weights_for_gates(context.get("user_weights"))
    av = context.get("upswitch_adaptive_value")
    has_page = compute_has_upswitch_adaptive_page(sm, uw, av)
    context["has_upswitch_adaptive_page"] = has_page
    is_adaptive_only = compute_is_adaptive_only_path(sm, uw, has_page)
    context["is_adaptive_only_path"] = is_adaptive_only
    # 2026-05-27 (VAL-2026-35A4): single source of truth for "Adaptive is the
    # lens AND DCF was excluded so the headline is multiples-only" — used by
    # cover note, exec badge/prose, calibration intro, and page-header chip
    # to swap to *_multiples_only translations. Without it each surface
    # recomputed the predicate locally and drifted; e.g. the calibration page
    # kept asserting "Een verkorte DCF-crosscheck ondersteunt de bandbreedte"
    # on multiples-only runs.
    context["is_adaptive_multiples_only"] = compute_is_adaptive_multiples_only(
        is_adaptive_only_path=is_adaptive_only,
        adaptive_dcf_weight=context.get("adaptive_dcf_weight"),
        has_dcf=context.get("has_dcf"),
        dcf_method_available=context.get("dcf_method_available"),
    )
    stamp_adaptive_presentation_weights(context)
