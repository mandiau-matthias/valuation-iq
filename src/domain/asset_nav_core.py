from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from math import isinf, isnan
from typing import Optional

from src.config.belgian_tax import STANDARD_CIT_RATE, resolve_corporate_tax_rate
from src.domain.models import YearData

ADJUSTED_NAV_LABEL = "Gecorrigeerde NAV (Intrinsieke Waarde)"

# Flat deferred-tax assumptions on corporate asset gains. Asset ownership
# alone does not evidence a reduced tax regime or an exemption. Advisors
# can supply an evidenced per-asset/global rate for the actual transaction.
NAV_DEFAULT_PER_ASSET_TAX_RATES: dict[str, Decimal] = {
    "real_estate": STANDARD_CIT_RATE,
    "inventory": STANDARD_CIT_RATE,  # 25%
    "receivables": STANDARD_CIT_RATE,
    "hidden_reserves": STANDARD_CIT_RATE,
    "other_revaluations": STANDARD_CIT_RATE,
}


@dataclass(frozen=True)
class NavBalanceBaseline:
    total_assets: Decimal
    total_liabilities: Decimal


@dataclass(frozen=True)
class NavAdjustmentContext:
    context: dict[str, object]
    inventory_adjustment: Optional[Decimal]
    real_estate_adjustment: Optional[Decimal]
    real_estate_book: Optional[Decimal]
    real_estate_appraisal: Optional[Decimal]
    hidden_reserves: Optional[Decimal]
    goodwill_writeoff: Optional[Decimal]
    receivables_adjustment: Optional[Decimal]
    other_revaluations: Optional[Decimal]
    equipment_revaluation_payload: Optional[dict[str, object]]
    raw_tax_pct: Optional[Decimal]
    tax_latency_pct: Decimal
    sme_eligibility_payload: Optional[dict[str, object]]
    per_asset_rates: dict[str, Decimal]
    off_balance_items: Optional[Decimal]


@dataclass(frozen=True)
class NavDeferredTax:
    breakdown: list[dict[str, object]]
    deduction: Decimal
    gross_positive_adjustments: Decimal


@dataclass(frozen=True)
class NavEquityValues:
    equity_value: Decimal
    equity_value_low: Decimal
    equity_value_high: Decimal


def to_decimal_or_none(value: object) -> Optional[Decimal]:
    if value is None or value == "":
        return None
    if isinstance(value, (float, int)) and not isinstance(value, bool):
        if isinstance(value, float) and (isnan(value) or isinf(value)):
            return None
    if isinstance(value, Decimal):
        if value.is_nan() or value.is_infinite():
            return None
        return value
    try:
        d = Decimal(str(value))
        if d.is_nan() or d.is_infinite():
            return None
        return d
    except (InvalidOperation, TypeError, ValueError):
        return None


def derive_total_liabilities(
    balance_sheet: Mapping[str, object], total_assets: Decimal
) -> Optional[Decimal]:
    """Use an accounting total or the assets-minus-equity identity.

    Financial debt and current liabilities are subsets of total liabilities.
    Neither can stand in for the missing accounting total. An impossible
    negative derived liability must not be clamped to an invented zero.
    """
    total_liabilities = to_decimal_or_none(balance_sheet.get("total_liabilities"))
    if total_liabilities is not None:
        return total_liabilities if total_liabilities >= 0 else None

    total_equity = to_decimal_or_none(balance_sheet.get("total_equity"))
    if total_equity is not None:
        derived = total_assets - total_equity
        return derived if derived >= 0 else None

    return None


def nav_unavailable_payload(
    *,
    reason: str,
    code: str,
    missing_fields: Optional[list[str]] = None,
    remediation: Optional[str] = None,
    details: Optional[dict[str, object]] = None,
) -> dict[str, object]:
    """Standardized payload when adjusted NAV cannot be computed."""
    return {
        "available": False,
        "label": ADJUSTED_NAV_LABEL,
        "unavailable_reason": reason,
        "unavailable_code": code,
        "missing_fields": list(missing_fields or []),
        "remediation": remediation,
        "details": details or {},
    }


def compute_equipment_economic_meerwaarde(
    raw: object, reporting_year: int
) -> Optional[tuple[Decimal, dict[str, object]]]:
    """Reconstruct equipment economic book value vs. tax book value."""
    if not isinstance(raw, Mapping):
        return None
    original_cost = to_decimal_or_none(raw.get("original_cost"))
    tax_book = to_decimal_or_none(raw.get("tax_book_value"))
    economic_book_override = to_decimal_or_none(raw.get("economic_book_value"))
    useful_life = to_decimal_or_none(raw.get("economic_useful_life_years"))
    acq_year = raw.get("acquisition_year")

    if economic_book_override is not None and tax_book is not None:
        meerwaarde = (economic_book_override - tax_book).quantize(Decimal("0.01"))
        return meerwaarde, {
            "original_cost": float(original_cost) if original_cost is not None else None,
            "tax_book_value": float(tax_book),
            "economic_book_value": float(economic_book_override),
            "meerwaarde": float(meerwaarde),
            "method": "user_supplied_economic_book",
        }

    if original_cost is None or tax_book is None or useful_life is None or acq_year is None:
        return None

    try:
        age = max(0, int(reporting_year) - int(acq_year))
    except (TypeError, ValueError):
        return None
    if useful_life <= 0:
        return None

    age_dec = Decimal(age)
    depreciated_pct = min(age_dec / useful_life, Decimal("1"))
    economic_book = (original_cost * (Decimal("1") - depreciated_pct)).quantize(Decimal("0.01"))
    if economic_book < 0:
        economic_book = Decimal("0")
    meerwaarde = (economic_book - tax_book).quantize(Decimal("0.01"))
    return meerwaarde, {
        "original_cost": float(original_cost),
        "acquisition_year": int(acq_year),
        "age_years": age,
        "economic_useful_life_years": float(useful_life),
        "tax_book_value": float(tax_book),
        "economic_book_value": float(economic_book),
        "meerwaarde": float(meerwaarde),
        "method": "straight_line_economic_depreciation",
    }


def resolve_nav_balance_baseline(
    balance_sheet: Optional[Mapping[str, object]],
) -> tuple[Optional[NavBalanceBaseline], Optional[dict[str, object]]]:
    if not balance_sheet:
        return None, nav_unavailable_payload(
            reason="Balansgegevens vereist — totale activa ontbreken.",
            code="NAV_BALANCE_SHEET_MISSING",
            missing_fields=[
                "current_year_data.total_assets",
                "current_year_data.total_liabilities",
            ],
            remediation=(
                "Vul minstens totale activa en passiva in vanuit de recentste balans "
                "om Gecorrigeerde NAV te berekenen."
            ),
        )

    total_assets = to_decimal_or_none(balance_sheet.get("total_assets"))
    if total_assets is None:
        return None, nav_unavailable_payload(
            reason="Balansgegevens vereist — totale activa ontbreken.",
            code="NAV_TOTAL_ASSETS_MISSING",
            missing_fields=["current_year_data.total_assets"],
            remediation="Vul totale activa in met een positief bedrag.",
        )
    if total_assets <= 0:
        return None, nav_unavailable_payload(
            reason="Balansgegevens vereist — totale activa moeten positief zijn.",
            code="NAV_TOTAL_ASSETS_NON_POSITIVE",
            missing_fields=["current_year_data.total_assets"],
            remediation="Corrigeer totale activa naar een positief bedrag uit de balans.",
            details={"total_assets": float(total_assets)},
        )

    total_liabilities = derive_total_liabilities(balance_sheet, total_assets)
    if total_liabilities is None:
        return None, nav_unavailable_payload(
            reason="Balansgegevens vereist — totale verplichtingen zijn niet betrouwbaar afleidbaar.",
            code="NAV_TOTAL_LIABILITIES_UNRESOLVABLE",
            missing_fields=[
                "current_year_data.total_liabilities|current_year_data.total_equity"
            ],
            remediation=(
                "Vul totale verplichtingen of volledig eigen vermogen uit dezelfde balans in. "
                "Financiële schuld of kortlopende verplichtingen alleen zijn onvoldoende."
            ),
        )
    return NavBalanceBaseline(total_assets, total_liabilities), None


def _bounded_percentage(value: Decimal) -> Decimal:
    return max(Decimal("0"), min(value, Decimal("100")))


def _resolve_real_estate_adjustment(
    context: Mapping[str, object],
) -> tuple[Optional[Decimal], Optional[Decimal], Optional[Decimal]]:
    real_estate_book = to_decimal_or_none(context.get("nav_real_estate_book_value"))
    real_estate_appraisal = to_decimal_or_none(context.get("nav_real_estate_appraisal_value"))
    if real_estate_book is not None and real_estate_appraisal is not None:
        adjustment = (real_estate_appraisal - real_estate_book).quantize(Decimal("0.01"))
    else:
        adjustment = to_decimal_or_none(context.get("nav_real_estate_adjustment"))
    return adjustment, real_estate_book, real_estate_appraisal


def _resolve_per_asset_tax_rates(context: Mapping[str, object]) -> dict[str, Decimal]:
    raw_per_asset = context.get("nav_per_asset_tax_rates") or {}
    if not isinstance(raw_per_asset, Mapping):
        return {}
    rates: dict[str, Decimal] = {}
    for key, value in raw_per_asset.items():
        parsed = to_decimal_or_none(value)
        if parsed is not None:
            rates[str(key)] = _bounded_percentage(parsed)
    return rates


def _resolve_tax_latency(
    context: Mapping[str, object],
    *,
    country_code: str,
) -> tuple[Optional[Decimal], Decimal, Optional[dict[str, object]]]:
    raw_tax_pct = to_decimal_or_none(context.get("nav_tax_latency_pct"))
    if raw_tax_pct is not None:
        return raw_tax_pct, _bounded_percentage(raw_tax_pct), None

    eligibility = resolve_corporate_tax_rate(
        country_code=country_code,
        taxable_profit=to_decimal_or_none(context.get("taxable_profit")),
        director_remuneration=to_decimal_or_none(context.get("director_remuneration")),
        is_financial_company=context.get("is_financial_company"),
        is_holding_more_than_50pct_shares=context.get("is_holding_more_than_50pct_shares"),
        explicit_override=context.get("sme_rate_override"),
    )
    return None, eligibility.rate, eligibility.to_dict()


def resolve_nav_adjustment_context(
    business_context: Optional[Mapping[str, object]],
    *,
    reporting_year: int,
    country_code: str,
) -> NavAdjustmentContext:
    context = dict(business_context or {})
    real_estate_adjustment, real_estate_book, real_estate_appraisal = (
        _resolve_real_estate_adjustment(context)
    )
    raw_goodwill = to_decimal_or_none(context.get("nav_goodwill_writeoff"))
    other_revaluations = to_decimal_or_none(context.get("nav_other_revaluations"))
    equipment_meerwaarde = compute_equipment_economic_meerwaarde(
        context.get("nav_equipment_revaluation"),
        reporting_year,
    )
    equipment_revaluation_payload: Optional[dict[str, object]] = None
    if equipment_meerwaarde is not None:
        other_revaluations = (
            equipment_meerwaarde[0]
            if other_revaluations is None
            else other_revaluations + equipment_meerwaarde[0]
        )
        equipment_revaluation_payload = equipment_meerwaarde[1]

    raw_tax_pct, tax_latency_pct, sme_eligibility_payload = _resolve_tax_latency(
        context,
        country_code=country_code,
    )

    return NavAdjustmentContext(
        context=context,
        inventory_adjustment=to_decimal_or_none(context.get("nav_inventory_adjustment")),
        real_estate_adjustment=real_estate_adjustment,
        real_estate_book=real_estate_book,
        real_estate_appraisal=real_estate_appraisal,
        hidden_reserves=to_decimal_or_none(context.get("nav_hidden_reserves")),
        goodwill_writeoff=abs(raw_goodwill) if raw_goodwill is not None else None,
        receivables_adjustment=to_decimal_or_none(context.get("nav_receivables_adjustment")),
        other_revaluations=other_revaluations,
        equipment_revaluation_payload=equipment_revaluation_payload,
        raw_tax_pct=raw_tax_pct,
        tax_latency_pct=tax_latency_pct,
        sme_eligibility_payload=sme_eligibility_payload,
        per_asset_rates=_resolve_per_asset_tax_rates(context),
        off_balance_items=to_decimal_or_none(context.get("nav_off_balance_items")),
    )


def apply_nav_balance_sheet_adjustments(
    adjusted_balance_sheet: dict[str, object],
    nav_context: NavAdjustmentContext,
) -> None:
    if nav_context.inventory_adjustment is not None:
        current_inventory = to_decimal_or_none(adjusted_balance_sheet.get("inventory")) or Decimal(
            "0"
        )
        adjusted_balance_sheet["inventory"] = current_inventory + nav_context.inventory_adjustment
        current_total = to_decimal_or_none(adjusted_balance_sheet.get("total_assets")) or Decimal(
            "0"
        )
        adjusted_balance_sheet["total_assets"] = max(
            current_total + nav_context.inventory_adjustment,
            Decimal("0"),
        )
    if nav_context.goodwill_writeoff is not None:
        current_total = to_decimal_or_none(adjusted_balance_sheet.get("total_assets")) or Decimal(
            "0"
        )
        adjusted_balance_sheet["total_assets"] = max(
            current_total - nav_context.goodwill_writeoff,
            Decimal("0"),
        )
    if nav_context.receivables_adjustment is not None:
        current_ar = to_decimal_or_none(
            adjusted_balance_sheet.get("accounts_receivable")
        ) or Decimal("0")
        adjusted_balance_sheet["accounts_receivable"] = (
            current_ar + nav_context.receivables_adjustment
        )
        current_total = to_decimal_or_none(adjusted_balance_sheet.get("total_assets")) or Decimal(
            "0"
        )
        adjusted_balance_sheet["total_assets"] = max(
            current_total + nav_context.receivables_adjustment,
            Decimal("0"),
        )


def resolve_adjusted_total_assets(
    adjusted_balance_sheet: Mapping[str, object],
) -> tuple[Optional[Decimal], Optional[dict[str, object]]]:
    total_assets = to_decimal_or_none(adjusted_balance_sheet.get("total_assets"))
    if total_assets is not None and total_assets > 0:
        return total_assets, None
    return None, nav_unavailable_payload(
        reason="Balansgegevens vereist — totale activa moeten positief zijn.",
        code="NAV_ADJUSTED_TOTAL_ASSETS_NON_POSITIVE",
        missing_fields=["current_year_data.total_assets"],
        remediation=(
            "Controleer activa-aanpassingen (goodwill, debiteuren, voorraad) "
            "zodat aangepaste totale activa positief blijven."
        ),
        details={
            "adjusted_total_assets": float(total_assets) if total_assets is not None else None
        },
    )


def build_current_year_data(
    *,
    reporting_year: int,
    revenue: object,
    ebitda: object,
    total_assets: Decimal,
    total_liabilities: Decimal,
    adjusted_balance_sheet: Mapping[str, object],
) -> YearData:
    return YearData(
        year=reporting_year,
        revenue=to_decimal_or_none(revenue) or Decimal("0"),
        ebitda=to_decimal_or_none(ebitda) or Decimal("0"),
        total_assets=total_assets,
        current_assets=to_decimal_or_none(adjusted_balance_sheet.get("current_assets")),
        cash=to_decimal_or_none(adjusted_balance_sheet.get("cash")),
        accounts_receivable=to_decimal_or_none(adjusted_balance_sheet.get("accounts_receivable")),
        inventory=to_decimal_or_none(adjusted_balance_sheet.get("inventory")),
        total_liabilities=total_liabilities,
        current_liabilities=to_decimal_or_none(adjusted_balance_sheet.get("current_liabilities")),
        total_debt=to_decimal_or_none(adjusted_balance_sheet.get("total_debt")),
        total_equity=to_decimal_or_none(adjusted_balance_sheet.get("total_equity")),
    )


def _tax_rate_for_asset(
    asset_key: str,
    nav_context: NavAdjustmentContext,
    *,
    country_code: str,
) -> tuple[Decimal, str]:
    if asset_key in nav_context.per_asset_rates:
        return nav_context.per_asset_rates[asset_key], "user_override"
    if nav_context.raw_tax_pct is not None:
        return nav_context.tax_latency_pct, "global_user_rate"
    if asset_key in NAV_DEFAULT_PER_ASSET_TAX_RATES and (country_code or "BE").upper() == "BE":
        return NAV_DEFAULT_PER_ASSET_TAX_RATES[asset_key], "engine_default_per_asset"
    return nav_context.tax_latency_pct, "engine_default_global"


def calculate_deferred_tax(
    nav_context: NavAdjustmentContext,
    *,
    country_code: str,
) -> NavDeferredTax:
    per_asset_inputs: list[tuple[str, Optional[Decimal]]] = [
        ("real_estate", nav_context.real_estate_adjustment),
        ("hidden_reserves", nav_context.hidden_reserves),
        ("other_revaluations", nav_context.other_revaluations),
        ("inventory", nav_context.inventory_adjustment),
        ("receivables", nav_context.receivables_adjustment),
    ]
    breakdown: list[dict[str, object]] = []
    deduction_total = Decimal("0")
    gross_positive_adjustments = Decimal("0")

    for asset_key, value in per_asset_inputs:
        if value is None or value <= 0:
            continue
        gross_positive_adjustments += value
        rate, rate_source = _tax_rate_for_asset(
            asset_key,
            nav_context,
            country_code=country_code,
        )
        deduction = (value * rate / Decimal("100")).quantize(Decimal("0.01"))
        deduction_total += deduction
        breakdown.append(
            {
                "asset_class": asset_key,
                "meerwaarde": float(value),
                "rate_pct": float(rate),
                "deferred_tax": float(deduction),
                "rate_source": rate_source,
            }
        )

    return NavDeferredTax(
        breakdown=breakdown,
        deduction=deduction_total,
        gross_positive_adjustments=gross_positive_adjustments,
    )


def effective_tax_latency_pct(deferred_tax: NavDeferredTax) -> Optional[float]:
    if deferred_tax.gross_positive_adjustments <= 0:
        return None
    return float(
        (
            deferred_tax.deduction / deferred_tax.gross_positive_adjustments * Decimal("100")
        ).quantize(Decimal("0.01"))
    )


def ownership_multiplier_or_default(ownership_multiplier: Decimal) -> Decimal:
    return ownership_multiplier if ownership_multiplier > 0 else Decimal("1")


def off_balance_deduction(nav_context: NavAdjustmentContext) -> Decimal:
    if nav_context.off_balance_items is None:
        return Decimal("0")
    return abs(nav_context.off_balance_items)


def nav_equity_range(
    corrected_nav: Decimal,
    ownership_multiplier: Decimal,
) -> tuple[Decimal, Decimal]:
    range_a = ((corrected_nav * Decimal("0.90")) * ownership_multiplier).quantize(Decimal("0.01"))
    range_b = ((corrected_nav * Decimal("1.10")) * ownership_multiplier).quantize(Decimal("0.01"))
    return max(min(range_a, range_b), Decimal("0")), max(max(range_a, range_b), Decimal("0"))


def resolve_nav_equity_values(
    *,
    corrected_nav: Decimal,
    ownership_multiplier: Decimal,
    deferred_tax: NavDeferredTax,
    off_balance_deduction: Decimal,
    logger: object,
) -> tuple[Optional[NavEquityValues], Optional[dict[str, object]]]:
    equity_value_raw = (corrected_nav * ownership_multiplier).quantize(Decimal("0.01"))
    if equity_value_raw < Decimal("0") and hasattr(logger, "warning"):
        logger.warning(
            "Adjusted NAV clamped negative equity to 0: corrected_nav=%s, ownership=%.4f",
            corrected_nav,
            ownership_multiplier,
        )
    equity_value = max(equity_value_raw, Decimal("0"))
    if equity_value <= Decimal("0"):
        return None, nav_unavailable_payload(
            reason=(
                "Gecorrigeerd nettovermogen is negatief na aftrek van "
                "belastinglatenties en buitenbalansposten."
            ),
            code="NAV_CORRECTED_EQUITY_NON_POSITIVE",
            remediation=(
                "Herbekijk activa-aanpassingen, latente belastingen en buitenbalansposten; "
                "de gecorrigeerde NAV moet positief zijn."
            ),
            details={
                "corrected_nav": float(corrected_nav),
                "tax_latency_deduction": float(deferred_tax.deduction),
                "off_balance_deduction": float(off_balance_deduction),
            },
        )
    low, high = nav_equity_range(corrected_nav, ownership_multiplier)
    return NavEquityValues(equity_value, low, high), None


def attach_nav_detail_extras(
    details: dict[str, object],
    nav_context: NavAdjustmentContext,
) -> None:
    if nav_context.sme_eligibility_payload is not None:
        details["sme_eligibility"] = nav_context.sme_eligibility_payload
    if nav_context.real_estate_book is not None and nav_context.real_estate_appraisal is not None:
        details["real_estate_revaluation"] = {
            "book_value": float(nav_context.real_estate_book),
            "appraisal_value": float(nav_context.real_estate_appraisal),
            "meerwaarde": float(
                (nav_context.real_estate_appraisal - nav_context.real_estate_book).quantize(
                    Decimal("0.01")
                )
            ),
        }
    if nav_context.equipment_revaluation_payload is not None:
        details["equipment_revaluation"] = nav_context.equipment_revaluation_payload


def attach_deal_structure_comparison(
    details: dict[str, object],
    *,
    nav_context: NavAdjustmentContext,
    adjusted_balance_sheet: Mapping[str, object],
    total_assets: Decimal,
    total_liabilities: Decimal,
    corrected_nav: Decimal,
    country_code: str,
) -> None:
    deal_type = (nav_context.context.get("deal_type") or "").lower() or None
    if deal_type not in {"asset", "share", "compare", "both"}:
        return

    from src.domain.deal_structure import compare_deal_structures

    book_equity = to_decimal_or_none(adjusted_balance_sheet.get("total_equity"))
    if book_equity is None:
        book_equity = total_assets - total_liabilities
    buyer_discount_rate_pct = to_decimal_or_none(
        nav_context.context.get("deal_buyer_discount_rate_pct")
    )
    if buyer_discount_rate_pct is None:
        buyer_discount_rate_pct = Decimal("10")

    comparison = compare_deal_structures(
        headline_equity_value=corrected_nav,
        book_equity=book_equity,
        goodwill_in_asset_deal=to_decimal_or_none(nav_context.context.get("deal_goodwill_amount")),
        seller_share_basis=to_decimal_or_none(nav_context.context.get("deal_seller_share_basis")),
        seller_is_individual=nav_context.context.get("deal_seller_is_individual", True),
        buyer_discount_rate_pct=buyer_discount_rate_pct,
        country_code=country_code,
        taxable_profit=to_decimal_or_none(nav_context.context.get("taxable_profit")),
        director_remuneration=to_decimal_or_none(nav_context.context.get("director_remuneration")),
        sme_rate_override=nav_context.context.get("sme_rate_override"),
        registration_duty_pct=to_decimal_or_none(
            nav_context.context.get("deal_registration_duty_pct")
        )
        or Decimal("0"),
    )
    details["deal_structure_comparison"] = comparison.to_dict()
    details["deal_type_selected"] = deal_type


def build_nav_details(
    *,
    result: object,
    nav_context: NavAdjustmentContext,
    adjusted_balance_sheet: Mapping[str, object],
    total_assets: Decimal,
    total_liabilities: Decimal,
    corrected_nav: Decimal,
    nav_before_deductions: Decimal,
    deferred_tax: NavDeferredTax,
    off_balance_deduction: Decimal,
    equity_values: NavEquityValues,
    country_code: str,
) -> dict[str, object]:
    details: dict[str, object] = {
        "asset_based_evidence": True,
        "net_asset_value": float(corrected_nav),
        "net_asset_value_before_deductions": float(nav_before_deductions),
        "tax_latency_deduction": float(deferred_tax.deduction),
        "off_balance_deduction": float(off_balance_deduction),
        "enterprise_value": float(corrected_nav),
        "total_assets_book": float(result.total_assets_book),
        "total_liabilities_book": float(result.total_liabilities_book),
        "total_assets_adjusted": float(result.total_assets_adjusted),
        "total_liabilities_adjusted": float(result.total_liabilities_adjusted),
        "tangible_asset_value": float(result.tangible_asset_value),
        "intangible_asset_value": float(result.intangible_asset_value),
        "equity_range_low": float(equity_values.equity_value_low),
        "equity_range_high": float(equity_values.equity_value_high),
        "methodology": result.methodology,
        "confidence": result.confidence.value,
        "asset_adjustments": [adj.to_dict() for adj in result.asset_adjustments],
        "deferred_tax_breakdown": deferred_tax.breakdown,
        "gross_positive_adjustments": float(deferred_tax.gross_positive_adjustments),
        "effective_tax_latency_pct": effective_tax_latency_pct(deferred_tax),
    }
    attach_nav_detail_extras(details, nav_context)
    attach_deal_structure_comparison(
        details,
        nav_context=nav_context,
        adjusted_balance_sheet=adjusted_balance_sheet,
        total_assets=total_assets,
        total_liabilities=total_liabilities,
        corrected_nav=corrected_nav,
        country_code=country_code,
    )
    if result.warnings:
        details["warnings"] = result.warnings
    manual_adjustments = manual_nav_adjustments_payload(nav_context)
    if manual_adjustments is not None:
        details["manual_nav_adjustments"] = manual_adjustments
    return details


def build_available_nav_payload(
    *,
    result: object,
    corrected_nav: Decimal,
    equity_values: NavEquityValues,
    details: dict[str, object],
) -> dict[str, object]:
    return {
        "available": True,
        "label": ADJUSTED_NAV_LABEL,
        "methodology_code": "ASSET_BASED",
        "methodology_label": result.methodology,
        "confidence_level": result.confidence.value.upper(),
        "equity_value": equity_values.equity_value,
        "equity_value_low": equity_values.equity_value_low,
        "equity_value_high": equity_values.equity_value_high,
        "enterprise_value": corrected_nav.quantize(Decimal("0.01")),
        "details": details,
        "warnings": result.warnings,
    }


def manual_nav_adjustments_payload(
    nav_context: NavAdjustmentContext,
) -> Optional[dict[str, float]]:
    balance_sheet_adjustments = {
        "real_estate_adjustment": nav_context.real_estate_adjustment,
        "inventory_adjustment": nav_context.inventory_adjustment,
        "hidden_reserves": nav_context.hidden_reserves,
        "goodwill_writeoff": (
            -nav_context.goodwill_writeoff if nav_context.goodwill_writeoff is not None else None
        ),
        "receivables_adjustment": nav_context.receivables_adjustment,
        "other_revaluations": nav_context.other_revaluations,
    }
    if not any(value is not None for value in balance_sheet_adjustments.values()):
        return None
    return {
        key: float(value) for key, value in balance_sheet_adjustments.items() if value is not None
    }
