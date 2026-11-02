"""
Post-Deal Equity Swap (OWNER-PROFILING-2 / Business Card Post-M&A lens).

Computes a real, SDE-driven post-deal equity value alongside the engine's
"pre-deal" headline. Replaces the FE haircut heuristic in
`apps/titan-api/src/users/profile/util/key-man-score.util.ts:computePostDealEquity`
with a fully-attributed normalization swap:

    post_deal_equity = pre_deal_equity + owner_comp_adj * effective_multiple

where:
- `owner_comp_adj` is the existing Step 2.5 normalization delta
  (`actual_owner_compensation - market_replacement_cost`), positive when the
  owner is paid above market (typical SME pattern), negative when underpaid.
- `effective_multiple` is the Step 2.5 calibrated multiple
  (`base_multiple + quality_multiple_adjustment`). Capitalising the swap at
  the same multiple keeps Pre-Deal/Post-Deal directly comparable: the only
  thing that changed between the two views is the owner-comp swap, not the
  buyer's quality lens.

The swap intentionally does NOT also reverse the multiple-side
owner-compensation-risk discount. That discount captures the *risk premium*
a buyer demands when an owner is overpaid; it doesn't fully evaporate the
moment the owner exits (transition risk, customer retention, etc.).
Removing both effects together would double-count and produce a noisy
demo number.

9-METHOD COVERAGE (per Hermes `valuation_method_readiness`):

  Method                Step 2.5?   Swap?              Notes
  ─────────────────────────────────────────────────────────────────────
  upswitch_adaptive     yes         yes                blended SME path
  ebitda_multiple       yes         yes
  revenue_multiple      yes         yes                NL alias: omzet_multiple
  sde_multiple          yes         yes
  arr_multiple          yes         yes                SaaS — same Step 2.5
  dcf                   NO          yes (FALLBACK)     compute owner-comp
                                                       adj directly; multiple
                                                       implied from equity/EBITDA
  fiscal_4x             NO          yes (FALLBACK)     BE-only; multiple = 4
  adjusted_nav          n/a         not_applicable     balance-sheet, not earnings
  startup_valuation     n/a         not_applicable     pre-revenue methods

`applied=False` covers two distinct cases now, separated by `state`:
  - `state="not_applicable"`: methodology doesn't have an SDE owner-comp
    swap by construction (NAV, startup). FE renders the lens as
    "not applicable to this methodology" — semantically different from
    "we couldn't compute it".
  - `state="unavailable"`: should have worked but inputs were missing
    (no owner data, degenerate equity). FE shows a "complete the wizard"
    affordance.
"""

from decimal import Decimal
from typing import Any, Dict, Optional

from src.utils.decimal_helpers import to_decimal


# Methodologies for which the SDE owner-comp swap does not apply by
# construction. The lens disables itself with a "not applicable to this
# methodology" framing rather than a "data missing" CTA — surfacing the
# distinction is important so accountants don't think the engine
# silently dropped the swap.
NOT_APPLICABLE_METHODOLOGIES = frozenset(
    {
        "adjusted_nav",
        "asset_based",
        "asset-based",
        "nav",
        "startup",
        "startup_valuation",
        "scorecard",
        "berkus",
    }
)

# Methodologies that don't run Step 2.5 in isolation but DO benefit from
# the owner-comp swap (DCF, fiscal_4x). The fallback path computes the
# adjustment directly via OwnerCompensationAdjuster and uses an implied
# multiple derived from the equity and EBITDA.
FALLBACK_METHODOLOGIES = frozenset(
    {
        "dcf",
        "income",
        "fiscal_4x",
        "fiscal4x",
    }
)


# Hard-coded BE fiscal multiple — `fiscal_4x` valuations apply
# `book_equity + 4 * normalized_EBITDA`, so a one-euro change in
# normalized EBITDA moves equity by exactly 4 euros. This avoids the
# implied-multiple computation (which would be sensitive to book equity
# carrying weight) and gives the lens a stable, defensible multiple.
_FISCAL_4X_MULTIPLE = Decimal("4")


_OWNER_COMP_CATEGORY = "owner_compensation_risk"
_OWNER_COMP_ADJUSTMENT_NAME_HINT = "owner compensation"


def _coerce_decimal(value: Any) -> Optional[Decimal]:
    """Best-effort Decimal coercion. Returns None when the value is not numeric."""
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except Exception:
        return None


def _find_step_2_5_result(detailed_results: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Locate the Step 2.5 (multiple calibration / EBITDA normalization) result dict.

    The orchestrator stashes this under several keys depending on the path:
    - `multiples_valuation._step_results.step_2_5` (multiples flow)
    - `multiples_valuation._step_results.step_2_5_multiple_calibration` (newer naming)
    - `ebitda_normalization_results` (legacy alias on detailed_results)
    - `step_2_5_multiple_calibration` (newest direct alias)
    - `step_2_5_ebitda_normalization` (older direct alias)
    - `normalization_result` (generic fallback)
    """
    if not isinstance(detailed_results, dict):
        return None

    # 1. Walk into multiples_valuation._step_results
    multiples = detailed_results.get("multiples_valuation")
    if isinstance(multiples, dict):
        step_results = multiples.get("_step_results")
        if isinstance(step_results, dict):
            for key in (
                "step_2_5",
                "step_2_5_multiple_calibration",
                "step_2_5_ebitda_normalization",
                "ebitda_normalization",
            ):
                candidate = step_results.get(key)
                # StepOutput Pydantic objects expose `.result`; dicts hold it directly.
                if candidate is not None:
                    result_dict = (
                        candidate.get("result")
                        if isinstance(candidate, dict)
                        else getattr(candidate, "result", None)
                    )
                    if isinstance(result_dict, dict) and result_dict:
                        return result_dict
                    if isinstance(candidate, dict) and (
                        "quality_factors" in candidate or "ebitda_adjustments" in candidate
                    ):
                        return candidate

    # 2. Direct aliases on detailed_results
    for key in (
        "ebitda_normalization_results",
        "step_2_5_multiple_calibration",
        "step_2_5_ebitda_normalization",
        "normalization_result",
        "ebitda_normalization",
    ):
        candidate = detailed_results.get(key)
        if isinstance(candidate, dict) and (
            "quality_factors" in candidate or "ebitda_adjustments" in candidate
        ):
            return candidate

    return None


def _extract_owner_comp_adjustment(step_result: Dict[str, Any]) -> Optional[Decimal]:
    """Extract the EUR owner-compensation adjustment from a Step 2.5 result.

    Preferred source is `ebitda_adjustments[*].amount` where the entry's
    name mentions "owner compensation". Falls back to deriving from
    `normalized_ebitda - reported_ebitda` when only one adjustment was made
    in step 2.5 (owner-comp is the only EBITDA-side adjustment today).
    """
    adjustments = step_result.get("ebitda_adjustments")
    if isinstance(adjustments, list):
        for entry in adjustments:
            if not isinstance(entry, dict):
                continue
            name = str(entry.get("name", "")).lower()
            if _OWNER_COMP_ADJUSTMENT_NAME_HINT in name:
                amount = _coerce_decimal(entry.get("amount"))
                if amount is not None:
                    return amount

    reported = _coerce_decimal(step_result.get("reported_ebitda"))
    normalized = _coerce_decimal(step_result.get("normalized_ebitda"))
    if reported is not None and normalized is not None:
        return normalized - reported

    return None


def _extract_effective_multiple(
    step_result: Dict[str, Any], detailed_results: Dict[str, Any]
) -> Optional[Decimal]:
    """Extract the calibrated multiple actually used to value the company.

    Step 2.5's `multiple_after` is `base_multiple + quality_multiple_adjustment`.
    If that's missing (DCF-only path or older payload), fall back to
    `multiples_valuation.ebitda_multiple`.
    """
    after = _coerce_decimal(step_result.get("multiple_after"))
    if after is not None and after > 0:
        return after

    multiples = detailed_results.get("multiples_valuation")
    if isinstance(multiples, dict):
        for key in ("ebitda_multiple", "applied_multiple", "calibrated_multiple"):
            v = _coerce_decimal(multiples.get(key))
            if v is not None and v > 0:
                return v

    return None


def _extract_market_rate_and_actual(
    step_result: Dict[str, Any],
) -> tuple[Optional[Decimal], Optional[Decimal], str]:
    """Pull market_rate, actual owner_compensation, and data_quality from
    the owner-comp quality factor metadata when available.

    Step 2.5 currently does not surface these alongside `quality_factors`;
    the adjuster's metadata stays on the calculator's local result. We
    walk a few likely locations and gracefully degrade to (None, None,
    "unknown") when the engine didn't expose them.
    """
    # The calculator stashes raw amounts inside individual quality_factors
    # via the `description` text but not as structured fields. We surface
    # them via the explicit keys the calculator already returns.
    quality_factors = step_result.get("quality_factors")
    data_quality = "unknown"
    if isinstance(quality_factors, list):
        for factor in quality_factors:
            if isinstance(factor, dict) and factor.get("category") == _OWNER_COMP_CATEGORY:
                # Some payloads carry severity but not raw amounts; that's fine
                # — actual/market are best-effort context, not load-bearing.
                data_quality = "provided"
                break

    actual = _coerce_decimal(step_result.get("owner_compensation_actual"))
    market = _coerce_decimal(step_result.get("market_replacement_cost"))
    if actual is None or market is None:
        meta = step_result.get("owner_compensation_metadata")
        if isinstance(meta, dict):
            if actual is None:
                actual = _coerce_decimal(meta.get("owner_compensation"))
            if market is None:
                market = _coerce_decimal(meta.get("market_rate"))
            if "data_quality" in meta:
                data_quality = str(meta.get("data_quality") or data_quality)

    return actual, market, data_quality


def _normalize_locale(locale: Optional[str]) -> str:
    """Resolve a locale string to one of the supported keys.

    Falls back to ``nl`` (the platform default) for unknown / missing
    inputs. Matches the convention used by `services.defensibility.banner`
    and the `services.infrastructure.translations` module so the swap
    rationale stays in lockstep with surrounding report copy.
    """
    if not isinstance(locale, str):
        return "nl"
    key = locale.strip().lower().split("-", 1)[0]
    return key if key in ("nl", "en") else "nl"


# Localised templates for the rationale sentence emitted on the swap.
# Three branches mirror the swap math: above market (positive delta),
# below market (negative delta), at market (zero delta). The
# `data_quality == "estimated"` caveat appends as a separate sentence.
#
# The templates intentionally include the literal numbers (€amount, x.xx
# multiple) interpolated at format time. This keeps the engine's
# computed values inline with the human-readable explanation, which is
# the primary defensibility property the rationale provides.
_RATIONALE_TEMPLATES: Dict[str, Dict[str, str]] = {
    "en": {
        "above_market": (
            "Owner currently compensated above market. Replacing with a "
            "market-rate manager lifts buyer-side EBITDA; equity rises by "
            "{delta_abs}€ at the calibrated {multiple}x multiple."
        ),
        "below_market": (
            "Owner currently compensated below market. A buyer must hire "
            "a market-rate manager, reducing buyer-side EBITDA; equity "
            "falls by {delta_abs}€ at the calibrated {multiple}x multiple."
        ),
        "at_market": (
            "Owner compensation is at market rate; the Post-Deal lens "
            "has no material effect."
        ),
        "estimated_caveat": (
            "Owner compensation was estimated from revenue heuristics; "
            "the swap is directionally correct but lower-confidence than "
            "a provided figure."
        ),
        "fallback_unavailable": (
            "Owner compensation data not available for this valuation. "
            "Complete the wizard to enable the Post-Deal lens."
        ),
        "fallback_not_applicable": (
            "Post-Deal SDE swap does not apply to this methodology. "
            "Asset-based and startup methods do not derive value from "
            "owner-replaceable earnings."
        ),
    },
    "nl": {
        "above_market": (
            "Eigenaar wordt momenteel boven het marktloon vergoed. Bij "
            "vervanging door een marktconforme manager stijgt de "
            "koperszijde-EBITDA; het eigen vermogen stijgt met "
            "{delta_abs}€ tegen de gekalibreerde multiple van {multiple}x."
        ),
        "below_market": (
            "Eigenaar wordt momenteel onder het marktloon vergoed. Een "
            "koper moet een marktconforme manager inhuren, waardoor de "
            "koperszijde-EBITDA daalt; het eigen vermogen daalt met "
            "{delta_abs}€ tegen de gekalibreerde multiple van {multiple}x."
        ),
        "at_market": (
            "Eigenaarsbeloning ligt op marktniveau; de Na-deal weergave "
            "heeft geen materieel effect."
        ),
        "estimated_caveat": (
            "Eigenaarsbeloning is geschat op basis van omzetheuristieken; "
            "de swap is directioneel correct maar minder betrouwbaar dan "
            "een werkelijk opgegeven cijfer."
        ),
        "fallback_unavailable": (
            "Gegevens over eigenaarsbeloning zijn niet beschikbaar voor "
            "deze waardering. Vul de wizard in om de Na-deal weergave te "
            "activeren."
        ),
        "fallback_not_applicable": (
            "De Na-deal SDE-swap is niet van toepassing op deze methode. "
            "Vermogen-gebaseerde en startup-methoden ontlenen hun waarde "
            "niet aan vervangbare bedrijfsresultaten."
        ),
    },
}


def _format_amount(value: Decimal) -> str:
    """Format a Decimal as a thousands-separated integer string.

    Both NL and EN reports use the same `1,234,567` thousand-separator
    convention in headline numbers (Mercury and Venus follow suit), so
    we keep this single formatter rather than threading locale through
    every numeric format call.
    """
    return f"{value:,.0f}"


def _build_rationale(
    *,
    owner_comp_adj: Decimal,
    equity_delta: Decimal,
    effective_multiple: Decimal,
    data_quality: str,
    locale_key: str,
) -> str:
    """Compose the localised rationale + optional estimated-quality caveat."""
    L = _RATIONALE_TEMPLATES[locale_key]
    if owner_comp_adj > 0:
        body = L["above_market"].format(
            delta_abs=_format_amount(abs(equity_delta)),
            multiple=f"{effective_multiple:.2f}",
        )
    elif owner_comp_adj < 0:
        body = L["below_market"].format(
            delta_abs=_format_amount(abs(equity_delta)),
            multiple=f"{effective_multiple:.2f}",
        )
    else:
        body = L["at_market"]

    if data_quality == "estimated":
        return f"{body} {L['estimated_caveat']}"
    return body


def _normalize_methodology(methodology: Optional[str]) -> str:
    """Lower-case + strip a methodology label for set membership tests."""
    if not isinstance(methodology, str):
        return ""
    return methodology.strip().lower()


def _compute_fallback_swap_inputs(
    detailed_results: Dict[str, Any],
    request: Any,
    pre_mid: Decimal,
    methodology_key: str,
) -> Optional[Dict[str, Any]]:
    """Compute owner-comp adj + multiple for methods that bypass Step 2.5.

    Used by DCF and fiscal_4x. Calls `OwnerCompensationAdjuster` directly
    using current-year revenue + business category from the request, then
    derives an applied multiple specific to the methodology:

    - **DCF**: implied EBITDA multiple = `pre_mid / current_year_ebitda`.
      Justification: the DCF equity result IS what the market would pay
      for the current EBITDA stream, so the implied multiple is a
      defensible-by-construction translation between the two frames.
    - **fiscal_4x**: stable `4x` multiple per the BE fiscal heuristic.

    Returns ``None`` when the inputs can't sustain the calculation
    (no revenue, no EBITDA, missing OwnerCompensationAdjuster). The
    caller falls back to the generic `applied=False` shape.
    """
    # Defensive lazy import — orchestration builders shouldn't pull on
    # step modules at import time.
    try:
        from src.api.routes.valuation.steps.step_2_5_multiple_calibration.modules.owner_compensation_adjuster import (
            OwnerCompensationAdjuster,
        )
    except ImportError:
        return None

    cyd = getattr(request, "current_year_data", None)
    if cyd is None:
        return None
    revenue = _coerce_decimal(getattr(cyd, "revenue", None))
    ebitda = _coerce_decimal(getattr(cyd, "ebitda", None))
    owner_comp_input = _coerce_decimal(getattr(cyd, "owner_compensation", None))
    business_category = getattr(request, "business_type_category", None) or getattr(
        request, "industry", None
    )
    location = getattr(request, "location", None) or "Belgium"

    if revenue is None or revenue <= 0:
        return None

    try:
        adjuster = OwnerCompensationAdjuster()
        adjustment_amount, _explanation, meta = adjuster.calculate_adjustment(
            owner_comp_input,
            revenue,
            business_category,
            location,
        )
    except Exception:
        return None

    actual = _coerce_decimal(meta.get("owner_compensation"))
    market = _coerce_decimal(meta.get("market_rate"))
    data_quality = str(meta.get("data_quality") or "unknown")

    if methodology_key in ("fiscal_4x", "fiscal4x"):
        effective_multiple = _FISCAL_4X_MULTIPLE
    else:
        # DCF / income — implied multiple = pre_deal_equity / EBITDA. If
        # EBITDA is missing or non-positive the implied multiple is
        # undefined; bail out rather than emit a misleading number.
        if ebitda is None or ebitda <= 0:
            return None
        effective_multiple = pre_mid / ebitda

    if effective_multiple <= 0:
        return None

    return {
        "owner_comp_adj": _coerce_decimal(adjustment_amount) or Decimal("0"),
        "effective_multiple": effective_multiple,
        "owner_compensation_actual": actual,
        "market_replacement_cost": market,
        "data_quality": data_quality,
    }


def compute_post_deal_swap(
    detailed_results: Dict[str, Any],
    pre_deal_equity_mid: Decimal,
    pre_deal_equity_low: Optional[Decimal] = None,
    pre_deal_equity_high: Optional[Decimal] = None,
    locale: Optional[str] = None,
    methodology: Optional[str] = None,
    request: Any = None,
) -> Dict[str, Any]:
    """Compute the post-deal equity swap payload for the response.

    Returns a dict with the structured fields the FE consumes. Always
    populated — when the swap can't be computed, `applied=False` and
    `post_deal_equity_value == pre_deal_equity_value`. Callers can
    forward this dict to `response_dict["owner_compensation_swap"]`
    and pull `post_deal_equity_value` for the top-level field.

    `locale` selects the rationale language (NL / EN). Defaults to NL —
    the platform's primary locale and the default for unrecognised
    values. The numeric formatting (€ amounts, multiples) does not vary
    by locale; only the surrounding sentence does.

    `methodology` is the valuation method label (e.g. ``"DCF"``,
    ``"adjusted_nav"``). Drives 9-method coverage:
      - For Step-2.5-running methods (multiples / SDE / ARR / adaptive),
        the swap reads the calibrated multiple + owner-comp adj from
        Step 2.5.
      - For DCF and fiscal_4x, the helper invokes the OwnerCompensationAdjuster
        directly and derives a defensible per-method multiple.
      - For NAV / startup, the swap is marked `state="not_applicable"`
        — the methodology doesn't have an SDE owner-comp dimension by
        construction.

    `request` is the original ValuationRequest; needed for the fallback
    path to read current-year revenue / EBITDA / business category /
    location. When omitted, the fallback path can't run and DCF /
    fiscal_4x fall to `state="unavailable"`.
    """
    locale_key = _normalize_locale(locale)
    methodology_key = _normalize_methodology(methodology)
    pre_mid = _coerce_decimal(pre_deal_equity_mid) or Decimal("0")
    pre_low = _coerce_decimal(pre_deal_equity_low)
    pre_high = _coerce_decimal(pre_deal_equity_high)

    def _fallback(state: str) -> Dict[str, Any]:
        rationale_key = (
            "fallback_not_applicable"
            if state == "not_applicable"
            else "fallback_unavailable"
        )
        return {
            "applied": False,
            "state": state,
            "pre_deal_equity_value": pre_mid,
            "post_deal_equity_value": pre_mid,
            "pre_deal_equity_low": pre_low,
            "post_deal_equity_low": pre_low,
            "pre_deal_equity_high": pre_high,
            "post_deal_equity_high": pre_high,
            "owner_compensation_actual": None,
            "market_replacement_cost": None,
            "owner_compensation_adjustment": None,
            "effective_multiple": None,
            "equity_delta": Decimal("0"),
            "data_quality": state,
            "rationale": _RATIONALE_TEMPLATES[locale_key][rationale_key],
        }

    # 1. Methodology gate: NAV / startup don't have an SDE swap dimension.
    if methodology_key in NOT_APPLICABLE_METHODOLOGIES:
        return _fallback("not_applicable")

    if pre_mid <= 0:
        return _fallback("unavailable")

    # 2. Primary path: Step 2.5 result (multiples / SDE / ARR / adaptive).
    step_result = _find_step_2_5_result(detailed_results)
    owner_comp_adj: Optional[Decimal] = None
    effective_multiple: Optional[Decimal] = None
    actual: Optional[Decimal] = None
    market: Optional[Decimal] = None
    data_quality: str = "unknown"

    if step_result is not None:
        owner_comp_adj = _extract_owner_comp_adjustment(step_result)
        effective_multiple = _extract_effective_multiple(step_result, detailed_results)
        actual, market, data_quality = _extract_market_rate_and_actual(step_result)

    # 3. Fallback path: DCF or fiscal_4x. Run the adjuster directly using
    #    the request inputs and derive a per-method multiple.
    if (
        (owner_comp_adj is None or effective_multiple is None or effective_multiple <= 0)
        and methodology_key in FALLBACK_METHODOLOGIES
        and request is not None
    ):
        fb = _compute_fallback_swap_inputs(
            detailed_results, request, pre_mid, methodology_key
        )
        if fb is not None:
            owner_comp_adj = fb["owner_comp_adj"]
            effective_multiple = fb["effective_multiple"]
            actual = fb["owner_compensation_actual"]
            market = fb["market_replacement_cost"]
            data_quality = fb["data_quality"]

    if owner_comp_adj is None:
        return _fallback("unavailable")
    if effective_multiple is None or effective_multiple <= 0:
        return _fallback("unavailable")

    equity_delta = owner_comp_adj * effective_multiple
    post_mid = pre_mid + equity_delta

    # Pydantic enforces `gt=0` on equity fields — clamp pathological cases.
    # If the swap pushes equity at-or-below zero the swap is degenerate and
    # we fall back to "no swap" rather than emit a misleading number.
    if post_mid <= 0:
        return _fallback("unavailable")

    # Apply the same proportional delta to low/high so the range slides
    # together with the mid. This is the simplest defensible behavior —
    # the engine's mid-to-range spread reflects multiples dispersion, not
    # owner-comp uncertainty, so the range shape is preserved.
    ratio = post_mid / pre_mid if pre_mid > 0 else Decimal("1")
    post_low = (pre_low * ratio) if pre_low is not None and pre_low > 0 else None
    post_high = (pre_high * ratio) if pre_high is not None and pre_high > 0 else None

    rationale = _build_rationale(
        owner_comp_adj=owner_comp_adj,
        equity_delta=equity_delta,
        effective_multiple=effective_multiple,
        data_quality=data_quality,
        locale_key=locale_key,
    )

    return {
        "applied": True,
        # `state` discriminates the FE rendering. "applied" mirrors
        # `applied=True` and `not_applicable` / `unavailable` mirror the
        # two distinct fallback reasons. Always set so the FE can switch
        # on a single field instead of inferring from missing values.
        "state": "applied",
        "pre_deal_equity_value": pre_mid,
        "post_deal_equity_value": post_mid,
        "pre_deal_equity_low": pre_low,
        "post_deal_equity_low": post_low,
        "pre_deal_equity_high": pre_high,
        "post_deal_equity_high": post_high,
        "owner_compensation_actual": actual,
        "market_replacement_cost": market,
        "owner_compensation_adjustment": owner_comp_adj,
        "effective_multiple": effective_multiple,
        "equity_delta": equity_delta,
        "data_quality": data_quality,
        "rationale": rationale,
    }
