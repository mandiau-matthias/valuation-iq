from collections.abc import Mapping
from decimal import Decimal, InvalidOperation
from typing import Optional

from src.utils.percentage_input_contract import declared_percentage

SAAS_TOKENS = ("saas", "software", "b2b_saas", "saas_software")
_LOCALE_SPACES = "\u00a0\u2007\u202f"


def _decimal_from_scalar(value: object) -> Optional[Decimal]:
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _clean_numeric_string(value: object) -> Optional[str]:
    text = str(value).strip()
    if not text:
        return None
    text = "".join(ch for ch in text if ch not in _LOCALE_SPACES)
    if not text:
        return None
    if text.endswith("\uff05") or text.endswith("%"):
        text = text[:-1].strip()
    return text


def _normalize_mixed_decimal_separators(text: str) -> str:
    if text.rfind(".") > text.rfind(","):
        return text.replace(",", "")
    return text.replace(".", "").replace(",", ".")


def _normalize_comma_separator(text: str) -> str:
    parts = text.split(",")
    if len(parts) != 2:
        return text.replace(",", "")

    left, right = parts
    left_digits = left.lstrip("-+").isdigit()
    if left_digits and len(right) in (1, 2) and right.isdigit():
        return f"{left}.{right}"
    return text.replace(",", "")


def _looks_like_dot_thousands(parts: list[str]) -> bool:
    first = parts[0].lstrip("-+")
    return (
        len(parts) > 1
        # A leading zero always denotes a decimal fraction in valuation
        # inputs (for example 0.015 = 1.5%). Treating it as a thousands group
        # silently turns 1.5% into 15%, which is catastrophic for WACC and
        # terminal-growth sensitivities.
        and first != "0"
        and first.isdigit()
        and 1 <= len(first) <= 3
        and all(len(part) == 3 and part.isdigit() for part in parts[1:])
    )


def _normalize_dot_separator(text: str) -> str:
    parts = text.split(".")
    if _looks_like_dot_thousands(parts):
        return text.replace(".", "")
    return text


def _normalize_decimal_separators(text: str) -> str:
    if "," in text and "." in text:
        return _normalize_mixed_decimal_separators(text)
    if "," in text:
        return _normalize_comma_separator(text)
    if "." in text:
        return _normalize_dot_separator(text)
    return text


def _parse_loose_decimal(value: object) -> Optional[Decimal]:
    """Parse JSON/UI numbers and strings like ``\"5\"``, ``\"5%\"``, ``\"1,234.56\"``, ``\"1.234,56\"``."""
    if value is None or value == "":
        return None
    # bool is a subclass of int in Python; never treat flags as numeric inputs
    if isinstance(value, bool):
        return None
    if isinstance(value, Decimal):
        return value
    if isinstance(value, (int, float)):
        return _decimal_from_scalar(value)

    numeric_text = _clean_numeric_string(value)
    if numeric_text is None:
        return None
    return _decimal_from_scalar(_normalize_decimal_separators(numeric_text))


def _parse_loose_bool(value: object) -> Optional[bool]:
    if isinstance(value, bool):
        return value
    if value is None:
        return None
    normalized = str(value).strip().lower().replace("-", "_").replace(" ", "_")
    if normalized in {"true", "1", "yes", "y", "mid_year", "midyear"}:
        return True
    if normalized in {"false", "0", "no", "n", "year_end", "period_end", "end_of_year"}:
        return False
    return None


def get_business_context(request: object) -> dict[str, object]:
    raw = getattr(request, "business_context", None)
    return raw if isinstance(raw, dict) else {}


def get_decimal_override(request: object, key: str) -> Optional[Decimal]:
    value = get_business_context(request).get(key)
    return _parse_loose_decimal(value)


def get_direct_decimal_override(request: object, key: str) -> Optional[Decimal]:
    return _parse_loose_decimal(getattr(request, key, None))


def _normalize_user_percent(raw: Decimal) -> Decimal:
    """
    Map UI percent entry to a 0–1 fraction.

    - 25, 110 → divide by 100
    - 1, -1 → divide by 100 (1% / -1%; avoids treating 1 as 100%)
    - 0.25, 0.85 → kept as fraction
    """
    if abs(raw) > Decimal("1"):
        return raw / Decimal("100")
    if raw == Decimal("1") or raw == Decimal("-1"):
        return raw / Decimal("100")
    return raw


def get_percent_override(request: object, key: str) -> Optional[Decimal]:
    return get_business_context_percent(get_business_context(request), key)


def get_direct_percent_override(request: object, key: str) -> Optional[Decimal]:
    raw = get_direct_decimal_override(request, key)
    if raw is None:
        return None
    return _normalize_user_percent(raw)


def get_effective_dcf_wacc_override(request: object) -> Optional[Decimal]:
    direct_wacc = get_percent_override(request, "dcf_wacc_pct")
    if direct_wacc is not None:
        return direct_wacc

    risk_free_rate = get_percent_override(request, "dcf_risk_free_rate_pct")
    equity_risk_premium = get_percent_override(request, "dcf_equity_risk_premium_pct")
    beta = get_decimal_override(request, "dcf_beta")
    cost_of_debt = get_percent_override(request, "dcf_cost_of_debt_pct")
    debt_share = get_percent_override(request, "dcf_debt_equity_pct")
    tax_shield = get_percent_override(request, "dcf_tax_shield_pct")

    required = (
        risk_free_rate,
        equity_risk_premium,
        beta,
        cost_of_debt,
        debt_share,
        tax_shield,
    )
    if any(value is None for value in required):
        return None

    safe_debt_share = min(max(debt_share, Decimal("0")), Decimal("0.95"))
    equity_share = Decimal("1") - safe_debt_share
    safe_tax_shield = min(max(tax_shield, Decimal("0")), Decimal("1"))
    cost_of_equity = risk_free_rate + beta * equity_risk_premium
    after_tax_debt_cost = cost_of_debt * (Decimal("1") - safe_tax_shield)
    return (equity_share * cost_of_equity) + (safe_debt_share * after_tax_debt_cost)


def get_dcf_da_pct_override(request: object) -> Optional[Decimal]:
    return get_percent_override(request, "dcf_da_pct")


def get_dcf_tax_rate_override(request: object) -> Optional[Decimal]:
    return get_percent_override(request, "dcf_tax_rate_pct")


def get_dcf_exit_multiple_override(request: object) -> Optional[Decimal]:
    return get_decimal_override(request, "dcf_exit_multiple")


def get_dcf_mid_year_discounting(request: object) -> bool:
    """Resolve DCF cash-flow timing from adaptive input payloads.

    Defaults to mid-year to preserve existing product behavior. Accountant
    templates can set ``dcf_discounting_convention=year_end`` or
    ``dcf_mid_year_discounting=false`` to benchmark year-end models.
    """
    context = get_business_context(request)

    explicit_bool = _parse_loose_bool(context.get("dcf_mid_year_discounting"))
    if explicit_bool is not None:
        return explicit_bool

    convention = (
        context.get("dcf_discounting_convention")
        or context.get("dcf_timing_convention")
        or context.get("discounting_convention")
    )
    normalized = str(convention or "").strip().lower().replace("-", "_").replace(" ", "_")
    if normalized in {"year_end", "period_end", "end_of_year", "eoy"}:
        return False
    if normalized in {"mid_year", "midyear", "mid_period", "mid_period_cash_flow"}:
        return True

    return True


def get_dcf_tax_shield_projection_overrides(request: object) -> list[Decimal]:
    """Return explicit APV debt tax-shield cash flows from adaptive payloads.

    These are nominal annual tax-shield amounts, not percentages. The DCF
    calculator discounts them separately and bridges operating DCF to APV.
    """
    from src.domain.dcf.apv_inputs import tax_shield_schedule

    return tax_shield_schedule(get_business_context(request))


def get_recurring_revenue_override(request: object) -> Optional[Decimal]:
    """
    Request-level recurring revenue share.

    Uses legacy rules on the direct attribute: values **> 1** are treated as whole
    percent (e.g. 85 → 0.85); values in **(0, 1]** are kept as fractions, so **1.0
    means 100% recurring** (common for all-MRR businesses). This intentionally
    differs from `_normalize_user_percent`, which maps ±1 to ±1%.

    Fallback `rev_recurring_pct` from business_context uses `_normalize_user_percent`.
    """
    context_pct = get_percent_override(request, "rev_recurring_pct")
    adaptive_pct = context_pct
    if adaptive_pct is None:
        adaptive_pct = get_direct_percent_override(request, "rev_recurring_pct")
    direct = getattr(request, "recurring_revenue_percentage", None)
    if direct is not None:
        try:
            direct_decimal = Decimal(str(direct))
            if direct_decimal > Decimal("1"):
                direct_decimal = direct_decimal / Decimal("100")
            if direct_decimal > 0 or adaptive_pct is None:
                return direct_decimal
        except (InvalidOperation, TypeError, ValueError):
            pass
    return adaptive_pct


def get_customer_concentration_override(request: object) -> Optional[Decimal]:
    revenue_quality = get_percent_override(request, "rev_top_client_concentration_pct")
    if revenue_quality is not None:
        return revenue_quality
    revenue_quality = get_direct_percent_override(request, "rev_top_client_concentration_pct")
    if revenue_quality is not None:
        return revenue_quality
    saas_concentration = get_percent_override(request, "saas_customer_concentration_pct")
    if saas_concentration is not None:
        return saas_concentration
    return get_direct_percent_override(request, "saas_customer_concentration_pct")


def get_recurring_revenue_amount_override(request: object) -> Optional[Decimal]:
    """Return recurring revenue as a currency amount from adaptive inputs."""
    direct = getattr(request, "rev_recurring_amount", None)
    parsed_direct = _parse_loose_decimal(direct)
    if parsed_direct is not None:
        return parsed_direct
    return get_decimal_override(request, "rev_recurring_amount")


def get_customer_concentration_amount_override(request: object) -> Optional[Decimal]:
    """Return top-client revenue as a currency amount from adaptive inputs."""
    direct = getattr(request, "rev_top_client_amount", None)
    parsed_direct = _parse_loose_decimal(direct)
    if parsed_direct is not None:
        return parsed_direct
    return get_decimal_override(request, "rev_top_client_amount")


def get_contract_backlog_override(request: object) -> Optional[Decimal]:
    """Return contracted backlog as a currency amount from adaptive inputs."""
    direct = getattr(request, "rev_contract_backlog", None)
    parsed_direct = _parse_loose_decimal(direct)
    if parsed_direct is not None:
        return parsed_direct
    return get_decimal_override(request, "rev_contract_backlog")


def get_business_context_decimal(context: Mapping[str, object], key: str) -> Optional[Decimal]:
    return _parse_loose_decimal(context.get(key))


def get_business_context_percent(context: Mapping[str, object], key: str) -> Optional[Decimal]:
    declared = declared_percentage(context, key)
    if declared is not None:
        return declared
    raw = get_business_context_decimal(context, key)
    if raw is None:
        return None
    return _normalize_user_percent(raw)


def is_saas_context(
    *,
    business_context: Optional[Mapping[str, object]] = None,
    business_type_id: Optional[str] = None,
    business_model: Optional[str] = None,
    industry: Optional[str] = None,
) -> bool:
    """Decide whether the SaaS sub-pipeline should run.

    Returns True when EITHER the industry/business-type tokens look like
    SaaS, OR the user explicitly entered SaaS metrics (ARR or MRR).
    The actual *eligibility* of the ARR multiple as a primary lens is a
    stricter check — see ``src.domain.saas_eligibility``. This function
    only decides whether the SaaS path is worth evaluating at all.
    """
    context = business_context or {}
    context_tokens = [
        str(context.get("business_category") or "").lower(),
        str(context.get("business_type") or "").lower(),
        str(context.get("sector_tag") or "").lower(),
    ]
    direct_tokens = [
        str(business_type_id or "").lower(),
        str(business_model or "").lower(),
        str(industry or "").lower(),
    ]
    combined = " ".join(context_tokens + direct_tokens)
    if any(token in combined for token in SAAS_TOKENS):
        return True

    # Explicit-signal fallback: user entered ARR or MRR. Eligibility is
    # still checked downstream; this only opens the gate so the
    # subcalculator can produce a verdict instead of silently skipping.
    arr = _parse_loose_decimal(context.get("saas_arr"))
    if arr is not None and arr > 0:
        return True
    mrr = _parse_loose_decimal(context.get("saas_mrr"))
    if mrr is not None and mrr > 0:
        return True

    return False
