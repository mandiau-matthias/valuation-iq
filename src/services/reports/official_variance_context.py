"""Official filing trust and variance context for report aggregation."""

from typing import Mapping, Optional, Protocol

from src.utils.decimal_helpers import safe_float

NON_COMPARABLE_REVENUE_SOURCES = {"gross_margin", "gross_margin_revenue_proxy"}


class OfficialVarianceTranslations(Protocol):
    """Translation fields required by the official variance table."""

    exec_revenue_label: str
    dcf_row_ebitda: str


def _normalized_string(value: object) -> str:
    return str(value).strip().lower() if value is not None else ""


def _list_or_none(value: object) -> list[object] | None:
    return value if isinstance(value, list) else None


def official_revenue_is_comparable(official_financials: Mapping[str, object]) -> bool:
    """Whether official revenue represents turnover and can be compared to user revenue."""
    revenue_source = _normalized_string(
        official_financials.get("revenue_source") or official_financials.get("revenueSource")
    )
    return revenue_source not in NON_COMPARABLE_REVENUE_SOURCES


def official_inputs_all_rejected(official_financials: Mapping[str, object]) -> bool:
    """Whether official filing rows were retained as evidence but rejected as inputs."""
    status = _normalized_string(
        official_financials.get("valuation_input_status")
        or official_financials.get("valuationInputStatus")
    )
    if status == "all_rejected":
        return True
    valuation_input_years = _list_or_none(
        official_financials.get("valuation_input_years")
        if "valuation_input_years" in official_financials
        else official_financials.get("valuationInputYears")
    )
    excluded_years = _list_or_none(
        official_financials.get("excluded_valuation_years")
        if "excluded_valuation_years" in official_financials
        else official_financials.get("excludedValuationYears")
    )
    return valuation_input_years == [] and bool(excluded_years)


def official_trust_match_eligible(official_financials: Mapping[str, object]) -> bool:
    """
    Whether to show the positive NBB alignment line in the report.

    Rules only: locale copy stays in the translation snapshot used by templates.
    """
    if not official_financials.get("has_official_financials"):
        return False
    if official_inputs_all_rejected(official_financials):
        return False
    if not official_revenue_is_comparable(official_financials):
        return False
    badge = official_financials.get("verification_badge") or {}
    if not isinstance(badge, dict) or badge.get("state") != "verified":
        return False
    variance_analysis = official_financials.get("variance_analysis") or {}
    if not isinstance(variance_analysis, dict):
        return False
    state = variance_analysis.get("state")
    explanation_required = bool(variance_analysis.get("explanationRequired"))
    severity = variance_analysis.get("severity")
    if severity == "hard":
        return False
    if explanation_required and state == "pending":
        return False
    return True


def official_variance_pct(
    user_value: Optional[float],
    official_value: Optional[float],
) -> Optional[float]:
    """Return absolute percentage variance between user input and official filing value."""
    if (
        user_value is None
        or official_value is None
        or official_value == 0
        or not isinstance(official_value, (int, float))
    ):
        return None
    try:
        user_float = float(user_value)
        official_float = float(official_value)
        if not (
            float("-inf") < user_float < float("inf")
            and float("-inf") < official_float < float("inf")
        ):
            return None
        return abs((user_float - official_float) / abs(official_float)) * 100.0
    except (TypeError, ValueError, ZeroDivisionError):
        return None


def build_official_variance_comparison_rows(
    official_financials: Mapping[str, object],
    user_revenue: Optional[float],
    user_ebitda: Optional[float],
    translations: OfficialVarianceTranslations,
) -> list[dict[str, object]]:
    """Official vs valuation-input figures for the report variance table."""
    rows: list[dict[str, object]] = []
    if not official_financials.get("has_official_financials"):
        return rows
    if official_inputs_all_rejected(official_financials):
        return rows

    official_revenue = official_financials.get("revenue")
    official_ebitda = official_financials.get("ebitda")
    official_revenue_float = safe_float(official_revenue) if official_revenue is not None else None
    official_ebitda_float = safe_float(official_ebitda) if official_ebitda is not None else None

    if official_revenue_float is not None and official_revenue_is_comparable(official_financials):
        rows.append(
            {
                "label": translations.exec_revenue_label,
                "official": official_revenue_float,
                "user": user_revenue,
                "variance_pct": official_variance_pct(user_revenue, official_revenue_float),
            }
        )
    if official_ebitda_float is not None:
        rows.append(
            {
                "label": translations.dcf_row_ebitda,
                "official": official_ebitda_float,
                "user": user_ebitda,
                "variance_pct": official_variance_pct(user_ebitda, official_ebitda_float),
            }
        )
    return rows
