"""DCF policy and context helpers around the core valuation math.

The functions in this module normalize request metadata and shape reporting
payloads. They deliberately avoid changing valuation formulas.
"""

from decimal import Decimal
from typing import Optional, cast

from src.domain.dcf_types import WACCComponents
from src.utils.decimal_helpers import to_decimal


def _float_or_default(value: object, default: float) -> float:
    if value is None:
        return default
    try:
        return float(cast(Decimal, to_decimal(value)))
    except (ValueError, TypeError, ArithmeticError):
        return default


def build_wacc_buildup(
    wacc_components: Optional[WACCComponents],
) -> Optional[dict[str, object]]:
    """Shape WACC component details for transparent API/report payloads."""
    if wacc_components is None:
        return None

    buildup: dict[str, object] = {
        "formula": "Risicovrije rente + bèta × aandelenrisicopremie + omvangspremie + bedrijfsspecifiek risico",
        "cost_of_equity_formula": "Rf + Beta x ERP + SP + CSR",
        "risk_free_rate": wacc_components.risk_free_rate,
        "beta": wacc_components.beta,
        "equity_risk_premium": wacc_components.market_risk_premium,
        "size_premium": wacc_components.size_premium,
        "company_specific_risk": wacc_components.company_specific_risk,
        "cost_of_equity": wacc_components.cost_of_equity,
        "cost_of_debt": wacc_components.cost_of_debt,
        "equity_weight": wacc_components.equity_weight,
        "debt_weight": wacc_components.debt_weight,
        "tax_rate": wacc_components.tax_rate,
        "debt_yield": wacc_components.debt_yield,
        "tax_shield": wacc_components.tax_shield,
        "wacc": wacc_components.wacc,
    }
    # The sealed public-Adaptive v3 control reads `wacc_evidence` off this
    # buildup to prove the applied WACC against its capital-structure decision
    # (`public_valuation_audit._modeled_dcf_wacc_reconciles`). Only the sibling
    # builder `stateless_dcf_runtime.wacc_buildup_from_components` emitted it,
    # and the DCF calculator does not call that one — so every public valuation
    # carrying a DCF contribution failed closed as
    # `modeled_dcf_wacc_unreconciled`. Emit the same block from the same
    # components here; shape is kept identical to the sibling on purpose.
    evidence = getattr(wacc_components, "evidence", None)
    if evidence is not None:
        buildup["wacc_evidence"] = {
            "capital_structure_source": evidence.capital_structure_source,
            "capital_structure_fallback": evidence.capital_structure_fallback,
            "fallback_reason": evidence.fallback_reason,
            "confidence": evidence.confidence,
            "warnings": list(evidence.warnings),
            "risk_free_rate_source": evidence.risk_free_rate_source,
            "market_risk_premium_source": evidence.market_risk_premium_source,
            "beta_source": evidence.beta_source,
            "cost_of_debt_source": evidence.cost_of_debt_source,
            "tax_rate_source": evidence.tax_rate_source,
        }
    return buildup


def overlay_user_capm_on_wacc_buildup(
    wacc_buildup: Optional[dict[str, object]],
    request: object,
) -> Optional[dict[str, object]]:
    """Replace buildup CAPM inputs with advisor-entered business_context values (decimal fractions)."""
    if wacc_buildup is None:
        return None

    from src.utils.adaptive_input_helpers import get_decimal_override, get_percent_override

    out = dict(wacc_buildup)
    from src.utils.percentage_input_contract import percentage_input_provenance

    units = percentage_input_provenance(getattr(request, "business_context", None) or {})
    if units is not None:
        out["percentage_input_contract"] = units
    risk_free = get_percent_override(request, "dcf_risk_free_rate_pct")
    if risk_free is not None:
        out["risk_free_rate"] = float(risk_free)
    erp = get_percent_override(request, "dcf_equity_risk_premium_pct")
    if erp is not None:
        out["equity_risk_premium"] = float(erp)
        out["market_risk_premium"] = float(erp)
    beta = get_decimal_override(request, "dcf_beta")
    if beta is not None:
        out["beta"] = float(beta)
    cost_of_debt = get_percent_override(request, "dcf_cost_of_debt_pct")
    if cost_of_debt is not None:
        out["cost_of_debt"] = float(cost_of_debt)
    debt_share = get_percent_override(request, "dcf_debt_equity_pct")
    if debt_share is not None:
        debt_weight = max(0.0, min(float(debt_share), 0.95))
        out["debt_weight"] = debt_weight
        out["equity_weight"] = 1.0 - debt_weight
    tax_shield = get_percent_override(request, "dcf_tax_shield_pct")
    if tax_shield is not None:
        out["tax_rate"] = float(tax_shield)
        out["tax_shield"] = float(tax_shield)
    size_premium = get_percent_override(request, "dcf_size_premium_pct")
    if size_premium is not None:
        out["size_premium"] = float(size_premium)
    company_specific_risk = get_percent_override(request, "dcf_company_specific_risk_pct")
    if company_specific_risk is not None:
        out["company_specific_risk"] = float(company_specific_risk)
    return out


def apply_manual_wacc_override_to_buildup(
    wacc_buildup: Optional[dict[str, object]],
    wacc: Decimal,
) -> Optional[dict[str, object]]:
    """Reflect an advisor WACC override in the transparent WACC buildup payload."""
    if wacc_buildup is None:
        return None

    adjusted = dict(wacc_buildup)
    applied_wacc = float(wacc)
    adjusted["wacc"] = applied_wacc
    adjusted["wacc_override_applied"] = True

    equity_weight = _float_or_default(adjusted.get("equity_weight"), 1.0)
    if equity_weight <= 0:
        return adjusted

    debt_weight = _float_or_default(adjusted.get("debt_weight"), max(0.0, 1.0 - equity_weight))
    cost_of_debt = _float_or_default(adjusted.get("cost_of_debt"), 0.0)
    tax_rate = min(max(_float_or_default(adjusted.get("tax_rate"), 0.0), 0.0), 1.0)
    after_tax_debt_contribution = debt_weight * cost_of_debt * (1.0 - tax_rate)
    implied_cost_of_equity = (applied_wacc - after_tax_debt_contribution) / equity_weight
    adjusted["cost_of_equity"] = implied_cost_of_equity

    risk_free_rate = _float_or_default(adjusted.get("risk_free_rate"), 0.0)
    beta = _float_or_default(adjusted.get("beta"), 1.0)
    equity_risk_premium = _float_or_default(adjusted.get("equity_risk_premium"), 0.0)
    company_specific_risk = _float_or_default(adjusted.get("company_specific_risk"), 0.0)
    adjusted["size_premium"] = (
        implied_cost_of_equity - risk_free_rate - beta * equity_risk_premium - company_specific_risk
    )
    return adjusted


def calculate_terminal_value_split(
    pv_fcf_projections: list[Decimal],
    pv_terminal_value: Decimal,
) -> tuple[Optional[Decimal], Optional[Decimal]]:
    """Return terminal and explicit forecast value share as percentages."""
    explicit_forecast_value = sum((to_decimal(value) for value in pv_fcf_projections), Decimal("0"))
    total_value = explicit_forecast_value + to_decimal(pv_terminal_value)
    if total_value <= 0:
        return None, None

    terminal_value_pct = (to_decimal(pv_terminal_value) / total_value) * Decimal("100")
    explicit_forecast_pct = (explicit_forecast_value / total_value) * Decimal("100")
    return terminal_value_pct, explicit_forecast_pct


def extract_has_audit(request: object) -> Optional[bool]:
    """Extract audited-financials flag without pricing missing data as unaudited."""
    for attr in ("has_audit", "audited_financials", "is_audited"):
        value = getattr(request, attr, None)
        if isinstance(value, bool):
            return value

    business_context = getattr(request, "business_context", None)
    if isinstance(business_context, dict):
        for key in ("has_audit", "audited_financials", "is_audited"):
            value = business_context.get(key)
            if isinstance(value, bool):
                return value
    return None


def extract_owner_dependency_score(
    request: object,
    *,
    logger: object | None = None,
) -> Optional[Decimal]:
    """Legacy owner scores are disclosure-only; WACC never prices them."""
    del request, logger
    return None
