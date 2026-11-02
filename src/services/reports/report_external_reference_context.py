"""Governed external-reference disclosure and reported-earnings presentation.

This module only projects sealed evidence. It does not calculate valuations,
fetch market data, or mutate the sealed valuation run.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from typing import TypeAlias, cast

from src.api.schemas.stateless_api import GenerateReportRequest

ReportMap: TypeAlias = dict[str, object]

_EXTERNAL_REFERENCE_COUNTRY_LABELS = {
    "BE": {"nl": "Belgische", "en": "Belgian", "fr": "belge"},
    "FR": {"nl": "Franse", "en": "French", "fr": "française"},
    "IE": {"nl": "Ierse", "en": "Irish", "fr": "irlandaise"},
}


_EXTERNAL_REFERENCE_GEOGRAPHY_ALIASES = {
    # Two kinds of alias must be present or a legitimate descriptor fails
    # closed:
    #   * adjective STEMS ("belgisch" covers belgische/belgisch),  because the
    #     noun "belgie" is not a substring of the adjective "belgische";
    #   * sub-national descriptors, because a Flemish/Walloon/Brussels-scoped
    #     observation is still a Belgian observation (the M&A Monitor publishes
    #     "Vlaanderen — alle groottes" cells).
    "BE": (
        "be",
        "belgium",
        "belgian",
        "belgie",
        "belgië",
        "belgisch",
        "belgique",
        "belge",
        "vlaanderen",
        "vlaams",
        "flanders",
        "flemish",
        "wallonie",
        "wallonië",
        "walloon",
        "waals",
        "brussel",
        "bruxelles",
        "brussels",
    ),
    # Stems are chosen so they cannot match unrelated words: "francais" covers
    # francaise, and the accented "français" covers "française", but "franc"
    # is deliberately absent (it would match "franchise"). Likewise no bare
    # "iers" for IE (it would match "dossiers").
    "FR": ("fr", "france", "french", "frans", "franse", "francais", "français"),
    "IE": ("ie", "ireland", "irish", "ierse", "eire", "éire", "irlande", "irlandais"),
}


def _external_reference_country_label(country_code: str, language: str | None) -> str:
    locale = str(language or "en").strip().lower()[:2]
    labels = _EXTERNAL_REFERENCE_COUNTRY_LABELS.get(country_code)
    if labels is None:
        raise ValueError("governed external market reference country is unsupported")
    return labels.get(locale) or labels["en"]


def _external_reference_geography_matches(country_code: str, geography: object) -> bool:
    normalized = " ".join(str(geography or "").strip().lower().replace("/", " ").split())
    aliases = _EXTERNAL_REFERENCE_GEOGRAPHY_ALIASES.get(country_code, ())
    return bool(
        normalized
        and any(
            alias == normalized
            # Two-letter country codes are too ambiguous to accept as a token
            # inside free text (for example, English "to be confirmed").
            # Long-form jurisdiction names may appear in a scoped descriptor.
            or (len(alias) > 2 and alias in normalized)
            for alias in aliases
        )
    )


def _decimal_or_zero(value: object) -> Decimal:
    try:
        return Decimal(str(value or 0))
    except (ValueError, TypeError, ArithmeticError):
        return Decimal("0")


def _optional_decimal(value: object) -> Decimal | None:
    """Parse a monetary/ratio input without turning missing evidence into zero."""
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (ValueError, TypeError, ArithmeticError):
        return None


def _reported_ebitda_maintainability_check(
    actuals: list[dict[str, object]],
) -> dict[str, object] | None:
    """Compare the latest reported EBITDA with prior reported history.

    This is a presentation-only maintainability signal.  It never normalizes
    EBITDA, changes forecast inputs or contributes to the valuation result.
    """

    valid: list[tuple[int, Decimal]] = []
    for row in actuals:
        year = row.get("year")
        ebitda = _optional_decimal(row.get("reported_ebitda"))
        if not isinstance(year, int) or ebitda is None or ebitda <= 0:
            continue
        valid.append((year, ebitda))
    valid.sort(key=lambda item: item[0])
    if len(valid) < 3:
        return None

    latest_year, latest_ebitda = valid[-1]
    previous_year, previous_ebitda = valid[-2]
    prior = valid[:-1]
    prior_average = sum((value for _, value in prior), Decimal("0")) / Decimal(len(prior))
    if previous_ebitda <= 0 or prior_average <= 0:
        return None
    return {
        "latest_year": latest_year,
        "previous_year": previous_year,
        "latest_ebitda": latest_ebitda,
        "previous_ebitda": previous_ebitda,
        "prior_years_label": f"{prior[0][0]}–{prior[-1][0]}",
        "prior_average": prior_average,
        "yoy_pct": (latest_ebitda / previous_ebitda - Decimal("1")) * Decimal("100"),
        "vs_prior_average_pct": (latest_ebitda / prior_average - Decimal("1")) * Decimal("100"),
    }


def _reported_ebitda_movement_bridge(
    actual_rows: list[object],
) -> dict[str, object] | None:
    """Decompose the latest reported-EBITDA movement into its drivers.

    A headline "EBITDA grew 23%" tells a buyer nothing about whether the growth
    is repeatable. Trading growth, a gross-margin rate shift and a one-line
    overhead cut all land in the same number, and only the first two survive a
    change of owner without evidence. This splits the movement into volume,
    gross-margin rate, operating expenses and personnel so the reader sees how
    much of the priced earnings base came from trading.

    Presentation only: it never changes the valuation basis, the multiple or
    the forecast. Returns ``None`` unless both years carry the full cost
    breakdown, and always discloses any amount it cannot allocate rather than
    forcing the bridge to tie.
    """

    def _line(row: object) -> dict[str, Decimal] | None:
        revenue = _optional_decimal(getattr(row, "revenue", None))
        gross_profit = _optional_decimal(getattr(row, "gross_profit", None))
        opex = _optional_decimal(getattr(row, "operating_expenses", None))
        personnel = _optional_decimal(getattr(row, "personnel_costs", None))
        reported = _optional_decimal(getattr(row, "reported_ebitda", None)) or _optional_decimal(
            getattr(row, "ebitda", None)
        )
        if (
            None in (revenue, gross_profit, opex, personnel, reported)
            or not revenue
            or revenue <= 0
        ):
            return None
        return {
            "revenue": revenue,
            "gross_profit": cast(Decimal, gross_profit),
            "operating_expenses": cast(Decimal, opex),
            "personnel_costs": cast(Decimal, personnel),
            "reported_ebitda": cast(Decimal, reported),
        }

    ordered = sorted(
        (row for row in actual_rows if isinstance(getattr(row, "year", None), int)),
        key=lambda item: getattr(item, "year"),
    )
    if len(ordered) < 2:
        return None
    current_row, previous_row = ordered[-1], ordered[-2]
    current, previous = _line(current_row), _line(previous_row)
    if current is None or previous is None:
        return None

    previous_margin_rate = previous["gross_profit"] / previous["revenue"]
    volume = (current["revenue"] - previous["revenue"]) * previous_margin_rate
    margin_rate = (current["gross_profit"] - previous["gross_profit"]) - volume
    operating_expenses = previous["operating_expenses"] - current["operating_expenses"]
    personnel = previous["personnel_costs"] - current["personnel_costs"]

    total_movement = current["reported_ebitda"] - previous["reported_ebitda"]
    allocated = volume + margin_rate + operating_expenses + personnel
    unallocated = total_movement - allocated
    cost_driven = operating_expenses + personnel
    return {
        "previous_year": getattr(previous_row, "year"),
        "current_year": getattr(current_row, "year"),
        "previous_ebitda": previous["reported_ebitda"],
        "current_ebitda": current["reported_ebitda"],
        "total_movement": total_movement,
        "revenue_growth_pct": (current["revenue"] / previous["revenue"] - Decimal("1"))
        * Decimal("100"),
        "previous_gross_margin_pct": previous_margin_rate * Decimal("100"),
        "current_gross_margin_pct": current["gross_profit"] / current["revenue"] * Decimal("100"),
        "volume": volume,
        "margin_rate": margin_rate,
        "operating_expenses": operating_expenses,
        "personnel": personnel,
        "unallocated": unallocated if abs(unallocated) >= Decimal("0.01") else None,
        "cost_driven_share_pct": (
            cost_driven / total_movement * Decimal("100")
            if total_movement > 0 and cost_driven > 0
            else None
        ),
        "previous_operating_expense_ratio_pct": previous["operating_expenses"]
        / previous["revenue"]
        * Decimal("100"),
        "current_operating_expense_ratio_pct": current["operating_expenses"]
        / current["revenue"]
        * Decimal("100"),
    }


def _sealed_source_reconciliation_notes(run: object) -> list[str]:
    """Select source/arithmetic disclosures committed to the run snapshot."""

    response_snapshot = _as_report_mapping(getattr(run, "response_snapshot", None))
    raw = response_snapshot.get("risk_factors")
    if not isinstance(raw, list):
        return []
    prefixes = (
        "Bronreconciliatie:",
        "De management/NBB-verschillen",
        "De NBB-geschiedenis",
    )
    notes: list[str] = []
    for value in raw:
        note = str(value or "").strip()
        if note.startswith(prefixes):
            notes.append(note)
    return notes


def _as_report_mapping(value: object) -> dict[str, object]:
    if isinstance(value, Mapping):
        return dict(value)
    if hasattr(value, "model_dump"):
        dumped = value.model_dump(mode="json")
        return dict(dumped) if isinstance(dumped, Mapping) else {}
    return {}


def _apply_governed_external_market_context(
    context: ReportMap,
    request: GenerateReportRequest,
) -> None:
    """Expose a sealed non-statistical market contract without Index semantics."""
    multiples_results = request.valuation_result.multiples_results or {}
    is_external = multiples_results.get("multiples_source") == (
        "GOVERNED_EXTERNAL_MARKET_REFERENCE"
    )
    context["is_governed_external_market_reference"] = is_external
    if not is_external:
        return

    raw_contract = multiples_results.get("external_market_reference_contract")
    contract = dict(cast(dict[str, object], raw_contract)) if isinstance(raw_contract, dict) else {}
    request_country = str(request.country_code or "").strip().upper()
    contract_country = str(contract.get("country_code") or "").strip().upper()
    if not request_country or contract_country != request_country:
        raise ValueError("governed external market reference country must match the report country")
    country_label = _external_reference_country_label(request_country, request.language)
    low = _decimal_or_zero(contract.get("range_low_multiple"))
    mid = _decimal_or_zero(contract.get("applied_multiple"))
    high = _decimal_or_zero(contract.get("range_high_multiple"))
    if not (low > 0 and low <= mid <= high):
        raise ValueError("governed external market reference range is incomplete")
    business_type_id = str(contract.get("business_type_id") or "selected-business-type")
    business_type_label = request.business_type_label or business_type_id.replace("_", " ").title()
    if business_type_id == "pharmacy" and (request.language or "nl").lower().startswith("nl"):
        business_type_label = "Apotheek"
    raw_sources = contract.get("sources")
    sources = raw_sources if isinstance(raw_sources, list) else []
    if not sources or any(
        not isinstance(source, dict)
        or not _external_reference_geography_matches(
            request_country,
            source.get("geography"),
        )
        for source in sources
    ):
        raise ValueError(
            "governed external market reference sources must match the contract country"
        )
    first_source = sources[0] if sources and isinstance(sources[0], dict) else {}
    metrics = request.valuation_result.financial_metrics or {}
    basis = _decimal_or_zero(context.get("valuation_basis_value"))
    sealed_run_multiples = _as_report_mapping(
        getattr(request.valuation_result.valuation_run, "multiples_results", None)
    )
    market_ev_low = _optional_decimal(sealed_run_multiples.get("enterprise_value_low"))
    market_ev_mid = _optional_decimal(sealed_run_multiples.get("enterprise_value"))
    market_ev_high = _optional_decimal(sealed_run_multiples.get("enterprise_value_high"))

    actual_rows = [*request.historical_years_data]
    if request.current_year_data is not None:
        actual_rows.append(request.current_year_data)
    source_reconciled_actuals: list[dict[str, object]] = []
    for row in sorted(actual_rows, key=lambda item: item.year):
        revenue = row.revenue
        ebitda = row.reported_ebitda if row.reported_ebitda is not None else row.ebitda
        depreciation = (
            row.depreciation_amortization
            if row.depreciation_amortization is not None
            else row.depreciation
        )
        margin = (ebitda / revenue * Decimal("100")) if revenue else None
        source_reconciled_actuals.append(
            {
                "year": row.year,
                "revenue": revenue,
                "ebit": row.ebit,
                "depreciation_amortization": depreciation,
                "reported_ebitda": ebitda,
                "ebitda_margin_pct": margin,
                "source_identifier": row.source_identifier,
            }
        )

    if business_type_id == "pharmacy" and request.current_year_data is not None:
        current = request.current_year_data
        revenue = _optional_decimal(current.revenue)
        inventory = _optional_decimal(current.inventory)
        receivables = _optional_decimal(current.accounts_receivable)
        payables = _optional_decimal(current.accounts_payable)
        buildings = _optional_decimal(current.buildings)
        cash = _optional_decimal(current.cash)
        debt = _optional_decimal(current.total_debt)
        inventory_ratio_pct = (
            inventory / revenue * Decimal("100")
            if inventory is not None and revenue is not None and revenue > 0
            else None
        )
        operating_nwc = (
            receivables + inventory - payables
            if receivables is not None and inventory is not None and payables is not None
            else None
        )
        operating_nwc_ratio_pct = (
            operating_nwc / revenue * Decimal("100")
            if operating_nwc is not None and revenue is not None and revenue > 0
            else None
        )
        # Owner-manager pay and premises are the two adjustments that most often
        # move a community-pharmacy price, and both are invisible in a filed
        # abbreviated schema. Sizing them here turns "confirm remuneration" and
        # "evidence rent" from a checklist item into a quantified exposure the
        # reader can act on. Sector reference points (wages 10-15% of turnover,
        # roughly one FTE per EUR 350k-500k of turnover) come from the BDO
        # Belgian pharmacy white paper carried in the sealed contract sources.
        personnel_costs = _optional_decimal(current.personnel_costs)
        personnel_ratio_pct = (
            personnel_costs / revenue * Decimal("100")
            if personnel_costs is not None and revenue is not None and revenue > 0
            else None
        )
        context["pharmacy_transaction_diligence"] = {
            "personnel_costs": personnel_costs,
            "personnel_ratio_pct": personnel_ratio_pct,
            # Filed social-balance FTE (rubric 9087) — employees only; the
            # owner/titularis and self-employed staff are excluded, which is
            # exactly why it sharpens the owner-dependence warning.
            "filed_employee_fte": _optional_decimal(current.filed_employee_fte),
            "personnel_ratio_below_sector_norm": (
                personnel_ratio_pct is not None and personnel_ratio_pct < Decimal("10")
            ),
            "implied_fte_low": (revenue / Decimal("500000") if revenue else None),
            "implied_fte_high": (revenue / Decimal("350000") if revenue else None),
            # Enterprise-value effect of charging EUR 10k of annual market rent,
            # at the multiple this report actually applied.
            "rent_sensitivity_ev_per_10k": (Decimal("10000") * mid if mid else None),
            "inventory": inventory,
            "inventory_ratio_pct": inventory_ratio_pct,
            "operating_nwc": operating_nwc,
            "operating_nwc_ratio_pct": operating_nwc_ratio_pct,
            "buildings_book_value": buildings,
            "cash": cash,
            "financial_debt": debt,
            "permit_status": "review_required",
            "titular_pharmacist_status": "review_required",
            "premises_status": "review_required",
            "inventory_status": "review_required",
            "supplier_reimbursement_status": "review_required",
            "completion_accounts_status": "review_required",
        }
    external_step = {
        "label": "Externe surveyreferentie",
        "short_label": "Externe referentie",
        "kind": "base",
        "tone": "brand",
        "start_value": 0,
        "end_value": float(mid),
        "multiple": float(mid),
        "impact": None,
        "ev": float(mid * basis),
        "ref": "†",
        "description": (
            "Geen Upswitch Index-contract; geen empirische percentielen, "
            "steekproef of pharmacy-transactieattributie."
        ),
    }
    context.update(
        {
            "has_industry_benchmarks": False,
            "has_benchmark_reference_multiple": False,
            "show_benchmark_reference_without_table": False,
            "benchmark_multiple_mid": None,
            "benchmark_multiple_low": None,
            "benchmark_multiple_high": None,
            "benchmark_sample_size": None,
            "benchmark_contract": None,
            "bridge_contract_resolved": False,
            "multiple_source": "GOVERNED_EXTERNAL_MARKET_REFERENCE",
            "industry": business_type_label,
            "sector": business_type_label,
            "business_type_title": business_type_label,
            "cover_sub_line": business_type_label,
            "external_market_reference_contract": contract,
            "external_market_reference_contract_id": contract.get("contract_id"),
            "external_market_reference_title": first_source.get("source_title"),
            "external_market_reference_summary": first_source.get("evidence_summary"),
            "external_market_reference_is_non_statistical": True,
            "headline_ebitda_is_reported": True,
            "source_reconciled_actuals": source_reconciled_actuals,
            "ebitda_maintainability_check": (
                _reported_ebitda_maintainability_check(source_reconciled_actuals)
            ),
            "reported_ebitda_movement_bridge": _reported_ebitda_movement_bridge(actual_rows),
            "source_reconciliation_notes": _sealed_source_reconciliation_notes(
                request.valuation_result.valuation_run
            ),
            # The closing multiple-sourcing and discount-build-up addenda render
            # for the governed reference through their dedicated governed
            # branches: sources come verbatim from the sealed contract, the
            # corridor is named a sensitivity band (never P25/P50/P75), and the
            # discount waterfall documents the zero-adjustment state explicitly
            # rather than being omitted — an absent page reads as "not checked",
            # while the rendered page proves the multiple was not massaged.
            "show_multiple_evidence_appendix": True,
            "show_discount_methodology_appendix": True,
            "multiple_low": float(low),
            "base_multiple": float(mid),
            "applied_multiple": float(mid),
            "multiple_high": float(high),
            "governed_market_enterprise_value_low": market_ev_low,
            "governed_market_enterprise_value_mid": market_ev_mid,
            "governed_market_enterprise_value_high": market_ev_high,
            "is_external_reference_range": True,
            "multiple_waterfall_steps": [external_step],
            "calibration_steps": [external_step],
            "discount_waterfall": [external_step],
            "management_turnover_unaudited": (
                str(metrics.get("revenue_source") or "").lower() == "management_workbook_unaudited"
            ),
            "data_inputs": (
                [
                    "Managementomzet (niet-geauditeerd)",
                    "Gerapporteerde EBITDA (brongebonden)",
                    "Upswitch-modelscenario 2026–2030 (geen managementprognose)",
                ]
                if (request.language or "nl").lower().startswith("nl")
                else context.get("data_inputs")
            ),
            "show_size_discount_skipped_note": False,
            "adaptive_methodology_justification": (
                f"De marktcomponent gebruikt een verzegelde {country_label.lower()} externe "
                f"referentie van {mid:.2f}× gerapporteerde EBITDA, met {low:.2f}×–"
                f"{high:.2f}× als sensitiviteitscorridor. Dit is geen Upswitch "
                "Index-contract, geen pharmacy-transactiepercentiel en geen "
                "statistische steekproef."
            ),
            "methodology_statement": (
                "De marktcomponent gebruikt uitsluitend de verzegelde externe "
                "EV/EBITDA-referentie; empirische percentielen en steekproefgrootte "
                "zijn bewust null. De DCF-component wordt afzonderlijk uit expliciete "
                "FCFF-prognoses berekend."
            ),
        }
    )

    # Keep the advisor appendix as explicit as the calculation contract. This
    # evidence deliberately bypasses benchmark provenance because an external
    # reference must not acquire Index percentiles or sample-size semantics.
    transparency = context.get("advisor_multiple_transparency")
    transparency = dict(transparency) if isinstance(transparency, dict) else {}
    nace_suffix = f" · NACE {request.nace_code}" if request.nace_code else ""
    transparency["benchmark_evidence"] = {
        "label": "Externe surveyreferentie — niet-statistisch",
        "basis_label": "EV/EBITDA — externe surveyreferentie",
        "business_type_title": f"{business_type_label}{nace_suffix}",
        "low": str(low),
        "mid": str(mid),
        "high": str(high),
        "range_type": "advisor_defined_external_reference_range",
        "data_source": first_source.get("source_title"),
        "source_url": first_source.get("source_url"),
        "source_hash": first_source.get("content_sha256"),
        "published_on": first_source.get("published_on"),
        "retrieved_on": first_source.get("retrieved_on"),
        "geography": first_source.get("geography"),
        "metric_definition": first_source.get("metric_definition"),
        "evidence_summary": first_source.get("evidence_summary"),
        "sample_disclosure": first_source.get("sample_disclosure"),
        "sample_size": None,
        "percentiles": {"p25": None, "p50": None, "p75": None},
        "contract_id": contract.get("contract_id"),
        "methodology_version": contract.get("methodology_version"),
        "limitations": contract.get("limitations") or [],
        "is_upswitch_index": False,
    }
    transparency.update(
        {
            "earnings_basis": (
                f"Gerapporteerde EBITDA FY{request.reporting_year}"
                if request.reporting_year is not None
                else "Gerapporteerde EBITDA"
            ),
            "earnings_basis_rationale": (
                "Gerapporteerde, niet-genormaliseerde EBITDA; "
                "er zijn geen normalisaties toegepast."
            ),
            "reported_earnings": str(basis),
            "adjusted_earnings": str(basis),
            "risk_analysis_enabled": False,
            "risk_analysis_reference_only": True,
            "discount_floor_factor_percent": None,
            "discount_rows": [],
            "blend_rows": [],
            "segment_rows": [],
            "multiple_rows": [
                {
                    "label": "Sectorale surveyreferentie",
                    "multiple": str(mid),
                    "adjustment": None,
                    "enterprise_value": str(mid * basis),
                    "rationale": (
                        "Verzegelde externe referentie; geen Index-contract, "
                        "pharmacy closed-deal mediaan of empirische percentielset."
                    ),
                    "source": first_source.get("source_title"),
                }
            ],
        }
    )

    weighted_ev = _decimal_or_zero(request.valuation_result.enterprise_value_mid)
    weighted_equity = _decimal_or_zero(request.valuation_result.equity_value_mid)
    cash = _decimal_or_zero((request.valuation_result.financial_metrics or {}).get("cash"))
    debt = _decimal_or_zero((request.valuation_result.financial_metrics or {}).get("total_debt"))
    transparency["equity_bridge"] = {
        "rows": [
            {
                "label": "Gewogen ondernemingswaarde (EV)",
                "amount": str(weighted_ev),
                "operator": None,
            },
            {
                "label": "Toevoegen: voorlopige kas",
                "amount": str(cash),
                "operator": "+",
            },
            {
                "label": "Aftrek: financiële schuld",
                "amount": str(debt),
                "operator": "−",
            },
            {
                "label": "Illustratieve aandelenwaarde",
                "amount": str(weighted_equity),
                "operator": "=",
            },
        ],
        "disclosures": [
            "Illustratief per de financiële referentiedatum — geen raming van de "
            "netto-verkoopopbrengst. Restricted cash, minimum operationele kas, "
            "leases, schuldachtige posten (waaronder aandeelhoudersrekeningen en "
            "fiscale/sociale passiva), vastgoedperimeter, genormaliseerd "
            "werkkapitaal en completion accounts zijn nog niet volledig "
            "geverifieerd."
        ],
        "reconciles": abs(weighted_ev + cash - debt - weighted_equity) <= Decimal("0.01"),
    }
    context["advisor_multiple_transparency"] = transparency

    # The report waterfall must begin at the weighted EV conclusion, not at the
    # standalone market leg.  Cash/debt are then bridged exactly once.
    context["value_waterfall_intro_text"] = (
        "Van de gewogen ondernemingswaarde naar een uitsluitend illustratieve "
        "aandelenwaarde; kas, schuld en overige completion-accountsposten worden "
        "afzonderlijk behandeld."
    )
    context["valuation_waterfall_steps"] = [
        {
            "label": "Gewogen ondernemingswaarde",
            "short_label": "EV synthese",
            "kind": "subtotal",
            "tone": "brand",
            "start_value": 0,
            "end_value": float(weighted_ev),
            "delta_value": float(weighted_ev),
        },
        {
            "label": "Kas (voorlopig)",
            "short_label": "Kas",
            "kind": "increase",
            "tone": "positive",
            "start_value": float(weighted_ev),
            "end_value": float(weighted_ev + cash),
            "delta_value": float(cash),
        },
        {
            "label": "Financiële schuld",
            "short_label": "Schuld",
            "kind": "decrease",
            "tone": "negative",
            "start_value": float(weighted_ev + cash),
            "end_value": float(weighted_ev + cash - debt),
            "delta_value": float(-debt),
        },
        {
            "label": "Illustratieve aandelenwaarde",
            "short_label": "Equity (ill.)",
            "kind": "total",
            "tone": "brand",
            "start_value": 0,
            "end_value": float(weighted_equity),
            "delta_value": float(weighted_equity),
        },
    ]
