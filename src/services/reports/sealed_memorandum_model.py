"""Construct the only data model accepted by sealed memorandum templates."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from src.services.reports.report_design_manifest import (
    build_cover_motif,
    build_report_design_manifest,
)
from src.services.reports.sealed_memorandum_errors import SealedMemorandumModelError
from src.services.reports.sealed_memorandum_financials import (
    financial_history_rows,
    normalization_rows,
)
from src.services.reports.sealed_memorandum_i18n import sealed_memorandum_copy
from src.services.reports.sealed_memorandum_methods import build_method_pages
from src.services.reports.sealed_report_charts import (
    benchmark_distribution_chart,
    bridge_chart_rows,
    bridge_direction_chart,
    financial_history_chart,
    method_chart_rows,
    three_value_bars,
)
from src.services.reports.stateless_valuation_run import canonical_hash


def _map(value: object) -> Mapping[str, object]:
    return value if isinstance(value, Mapping) else {}


def _rows(value: object) -> list[object]:
    return (
        list(value)
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray))
        else []
    )


def _source_reference_rows(value: object) -> list[dict[str, str]]:
    references: list[dict[str, str]] = []
    for index, item in enumerate(_rows(value), start=1):
        if not isinstance(item, Mapping):
            references.append({"label": str(item), "detail": ""})
            continue
        label = str(
            item.get("title")
            or item.get("source_kind")
            or item.get("provider")
            or f"Source {index}"
        )
        detail = str(
            item.get("source_id")
            or item.get("document_hash")
            or item.get("url")
            or item.get("locator")
            or ""
        )
        references.append({"label": label, "detail": detail})
    return references


def _verification_id(value: object) -> str:
    text = str(value or "—").strip()
    return text[:12] if re.fullmatch(r"[0-9a-f]{64}", text) else text


def _decimal(value: object) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    return number if number.is_finite() else None


def _currency(value: object, locale: str, *, signed: bool = False) -> str:
    number = _decimal(value)
    if number is None:
        return "—"
    rounded = number.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    sign = ""
    if signed:
        sign = "+" if rounded > 0 else "−" if rounded < 0 else ""
    absolute = abs(int(rounded))
    if locale == "en":
        return f"{sign}€{absolute:,}"
    grouped = f"{absolute:,}".replace(",", "." if locale == "nl" else " ")
    return f"{sign}€ {grouped}" if locale == "nl" else f"{sign}{grouped} €"


def _display_factory(locale: str):
    def display(value: object, kind: str) -> str:
        if value is None or value == "":
            return "—"
        number = _decimal(value)
        if kind == "currency":
            return _currency(value, locale)
        if kind == "signed_currency":
            return _currency(value, locale, signed=True)
        if kind == "multiple":
            return "—" if number is None else f"{number.quantize(Decimal('0.01'))}×"
        if kind == "percent_ratio":
            return "—" if number is None else f"{(number * 100).quantize(Decimal('0.1'))}%"
        if kind == "percent":
            return "—" if number is None else f"{number.quantize(Decimal('0.1'))}%"
        if kind == "integer":
            return "—" if number is None else str(int(number))
        if kind == "months":
            unit = {"nl": "maanden", "fr": "mois", "en": "months"}[locale]
            return "—" if number is None else f"{number.quantize(Decimal('0.1'))} {unit}"
        return str(value)

    return display


def _field(
    field_id: str,
    label: str,
    value: object,
    kind: str,
    display,
) -> dict[str, object] | None:
    if value is None or value == "":
        return None
    return {
        "field_id": field_id,
        "label": label,
        "raw": str(value),
        "display": display(value, kind),
    }


def _compact_fields(*fields: dict[str, object] | None) -> list[dict[str, object]]:
    return [field for field in fields if field is not None]


def _bridge_field(
    field_id: str,
    label: str,
    value: Decimal | None,
    display,
    *,
    operator: str | None = None,
    signed_effect: bool = False,
) -> dict[str, object] | None:
    if value is None:
        return None
    resolved_operator = operator
    display_value = value
    if signed_effect:
        resolved_operator = "+" if value >= 0 else "−"
        display_value = abs(value)
    field = _field(field_id, label, value, "currency", display)
    if field is None:
        return None
    field["display"] = display(display_value, "currency")
    field["operator"] = resolved_operator or ""
    return field


def _required_range(context: Mapping[str, object], prefix: str) -> tuple[Decimal, Decimal, Decimal]:
    low = _decimal(context.get(f"{prefix}_low"))
    mid = _decimal(context.get(prefix) or context.get(f"{prefix}_mid"))
    high = _decimal(context.get(f"{prefix}_high"))
    if low is None or mid is None or high is None or low > mid or mid > high:
        raise SealedMemorandumModelError(
            f"sealed memorandum requires ordered {prefix} low/mid/high"
        )
    return low, mid, high


def _reviewed_and_rejected_methods(
    context: Mapping[str, object],
    method_pages: list[dict[str, object]],
    copy: Mapping[str, str],
) -> list[dict[str, str]]:
    reviewed = [
        {
            "method_id": str(page["method_id"]),
            "label": str(page["title"]),
            "status": copy["eligible"],
            "reason": str(page["eligibility_reason"]),
        }
        for page in method_pages
    ]
    raw_rejected = context.get("rejected_methods") or context.get("method_rejections")
    for index, raw in enumerate(_rows(raw_rejected)):
        row = _map(raw)
        reason = row.get("reason") or row.get("rationale") or row.get("unavailable_reason")
        label = row.get("label") or row.get("method") or row.get("method_key")
        if not label or not reason:
            raise SealedMemorandumModelError(f"rejected method {index} requires label and reason")
        reviewed.append(
            {
                "method_id": str(row.get("method_key") or label),
                "label": str(label),
                "status": copy["rejected"],
                "reason": str(reason),
            }
        )
    exclusion = context.get("dcf_exclusion_reason")
    if exclusion and not any(row["method_id"] == "dcf" for row in reviewed):
        reviewed.append(
            {
                "method_id": "dcf",
                "label": copy["dcf_method"],
                "status": copy["rejected"],
                "reason": str(exclusion),
            }
        )
    return reviewed


def build_sealed_memorandum_model(context: dict[str, object]) -> dict[str, object]:
    locale = str(context.get("locale") or "nl").strip().lower()[:2]
    copy = sealed_memorandum_copy(locale)
    display = _display_factory(locale)
    scope = _map(context.get("engagement_scope"))
    registry = _map(context.get("registry_snapshot"))
    if not scope or not registry:
        raise SealedMemorandumModelError(
            "sealed memorandum requires engagement and registry snapshots"
        )

    equity_low, equity_mid, equity_high = _required_range(context, "equity_value")
    enterprise_value = _decimal(
        context.get("enterprise_value_mid") or context.get("enterprise_value")
    )
    enterprise_low = _decimal(context.get("enterprise_value_low"))
    enterprise_high = _decimal(context.get("enterprise_value_high"))
    enterprise_range = (enterprise_low, enterprise_value, enterprise_high)
    if any(value is not None for value in enterprise_range) and (
        any(value is None for value in enterprise_range)
        or not enterprise_low <= enterprise_value <= enterprise_high
    ):
        raise SealedMemorandumModelError(
            "sealed memorandum requires a complete ordered enterprise-value range"
        )
    net_debt = _decimal(context.get("net_debt")) or Decimal("0")
    debt = _decimal(
        context.get("total_debt") if context.get("total_debt") is not None else context.get("debt")
    )
    cash = _decimal(
        context.get("cash_balance")
        if context.get("cash_balance") is not None
        else context.get("cash")
    )
    if debt is None or cash is None:
        raise SealedMemorandumModelError(
            "sealed memorandum requires canonical gross debt and cash values"
        )
    if debt < 0 or cash < 0:
        raise SealedMemorandumModelError(
            "sealed memorandum rejects negative gross debt or cash signs"
        )
    expected_net_debt = debt - cash
    if abs(expected_net_debt - net_debt) > Decimal("1"):
        raise SealedMemorandumModelError(
            "sealed memorandum net debt does not reconcile to gross debt less cash"
        )
    nwc = _decimal(context.get("nwc_surplus_deficit") or context.get("nwc_adjustment")) or Decimal(
        "0"
    )
    tax = _decimal(context.get("tax_latency_net_impact")) or Decimal("0")
    method_pages = build_method_pages(context, copy, display)
    if not method_pages:
        raise SealedMemorandumModelError("sealed memorandum contains no reportable method family")

    assurance = str(context.get("report_assurance_level") or "indicative")
    assurance_label = (
        copy["approval_controlled"] if assurance == "advisor_approved" else copy["indicative"]
    )
    selected_method_value = (
        context.get("valuation_methodology_display")
        or context.get("selected_method")
        or context.get("methodology")
    )
    if not selected_method_value:
        raise SealedMemorandumModelError("sealed memorandum requires the canonical selected method")
    selected_method_key = str(selected_method_value).strip().lower()
    page_by_key = {
        "upswitch_adaptive": "market",
        "ebitda_multiple": "market",
        "revenue_multiple": "revenue_startup",
        "arr_multiple": "revenue_startup",
        "startup_valuation": "revenue_startup",
        "dcf": "dcf",
        "sde": "sde",
        "sde_multiple": "sde",
        "adjusted_nav": "adjusted_nav",
        "holding_sotp": "holding_sotp",
        "liquidation_analysis": "liquidation",
    }
    selected_page_id = page_by_key.get(selected_method_key)
    selected_page = next(
        (page for page in method_pages if page.get("method_id") == selected_page_id),
        None,
    )
    selected_method = (
        str(selected_page["title"]) if selected_page is not None else str(selected_method_value)
    )
    reported_ebitda = context.get("current_reported_ebitda") or _map(
        context.get("earnings_basis_ledger")
    ).get("reported_ebitda")
    normalization_total = context.get("total_adjustments") or _map(
        context.get("earnings_basis_ledger")
    ).get("total_adjustments")
    normalizations = normalization_rows(context, copy, display)
    financial_history = financial_history_rows(context, scope, copy, display)
    professional_review = _map(context.get("professional_review"))
    professional_reviewer = _map(professional_review.get("reviewer"))
    design_manifest = _map(context.get("report_design_manifest"))
    if not design_manifest:
        design_manifest = build_report_design_manifest(branding={}, locale=locale)
        context["report_design_manifest"] = design_manifest
        context["report_design_manifest_hash"] = canonical_hash(design_manifest)
    cover_motif = build_cover_motif(
        industry=context.get("business_type_title") or context.get("industry"),
        category=context.get("business_type_category"),
        company_name=context.get("company_name"),
        advisor_logo=_map(design_manifest.get("advisor_logo")),
    )
    normalization_summary = _compact_fields(
        _field(
            "normalization.reported_ebitda",
            copy["reported_ebitda"],
            reported_ebitda,
            "currency",
            display,
        ),
        _field(
            "normalization.total_adjustments",
            copy["adjustments"],
            normalization_total,
            "signed_currency",
            display,
        ),
        _field(
            "normalization.sustainable_ebitda",
            copy["sustainable_ebitda"],
            context.get("sustainable_ebitda"),
            "currency",
            display,
        ),
    )
    normalization_chart_labels = {
        "nl": ("Gerapporteerd", "Correcties", "Duurzaam"),
        "fr": ("Publié", "Ajustements", "Soutenable"),
        "en": ("Reported", "Adjustments", "Sustainable"),
    }[locale]
    normalization_chart_rows = [
        {**row, "label": normalization_chart_labels[index]}
        for index, row in enumerate(normalization_summary)
    ]
    selected_market_field: Mapping[str, object] | None = None
    benchmark_rows: list[Mapping[str, object]] = []
    for method_page in method_pages:
        method_page["chart"] = (
            None
            if method_page.get("method_id") == "market"
            else three_value_bars(
                method_chart_rows(method_page),
                chart_id=f"method_{method_page.get('method_id')}",
            )
        )
        if method_page.get("method_id") != "market":
            continue
        benchmark_rows = [
            row for row in _rows(method_page.get("benchmark_rows")) if isinstance(row, Mapping)
        ]
        selected_market_field = next(
            (
                row
                for row in _rows(method_page.get("rows"))
                if isinstance(row, Mapping)
                and str(row.get("field_id") or "").endswith(".applied_multiple")
            ),
            None,
        )
        break
    model = {
        "schema_version": "sealed_memorandum_display.v1",
        "locale": locale,
        "labels": dict(copy),
        "identity": {
            "company_name": str(context.get("company_name") or "—"),
            "industry": str(context.get("business_type_title") or context.get("industry") or "—"),
            "registration_number": str(context.get("registration_number") or "—"),
            "report_id": str(context.get("report_id_display") or context.get("report_id") or "—"),
            "advisor_firm": str(context.get("accountant_firm_name") or "—"),
            "advisor_logo_data_uri": context.get("accountant_logo_url"),
            "assurance_level": assurance,
            "assurance_label": assurance_label,
            "approval_disclosure": copy["approval_ledger"],
            "render_snapshot_sha256": str(context.get("render_snapshot_sha256") or "—"),
            "verification_id": _verification_id(context.get("render_snapshot_sha256")),
            "design_manifest_hash": str(context.get("report_design_manifest_hash") or "—"),
            "cover_motif": cover_motif,
        },
        "scope": {
            "rows": _compact_fields(
                _field(
                    "scope.purpose",
                    copy["purpose"],
                    scope.get("purpose"),
                    "text",
                    display,
                ),
                _field(
                    "scope.intended_users",
                    copy["intended_users"],
                    ", ".join(str(value) for value in _rows(scope.get("intended_users"))),
                    "text",
                    display,
                ),
                _field(
                    "scope.subject_interest",
                    copy["subject_interest"],
                    scope.get("subject_interest"),
                    "text",
                    display,
                ),
                _field(
                    "scope.ownership_percentage",
                    copy["ownership"],
                    scope.get("ownership_percentage"),
                    "percent",
                    display,
                ),
                _field(
                    "scope.basis_of_value",
                    copy["basis"],
                    scope.get("basis_of_value"),
                    "text",
                    display,
                ),
                _field(
                    "scope.premise_of_value",
                    copy["premise"],
                    scope.get("premise_of_value"),
                    "text",
                    display,
                ),
                _field(
                    "scope.valuation_date",
                    copy["valuation_date"],
                    scope.get("valuation_date"),
                    "text",
                    display,
                ),
                _field(
                    "scope.evidence_date",
                    copy["evidence_date"],
                    scope.get("evidence_date"),
                    "text",
                    display,
                ),
            ),
            "included_periods": [str(value) for value in _rows(scope.get("source_periods"))],
            "excluded_periods": [str(value) for value in _rows(scope.get("excluded_periods"))],
            "valuation_date": str(scope.get("valuation_date")),
            "limitations": [str(value) for value in _rows(scope.get("scope_limitations"))],
            "information_reliance": str(scope.get("information_reliance") or "—"),
            "conflict_disclosures": [
                str(value) for value in _rows(scope.get("conflict_disclosures"))
            ],
            "registry": {
                "source": str(registry.get("source") or "KBO"),
                "data_version": str(registry.get("data_version") or "—"),
                "snapshot_date": str(registry.get("snapshot_date") or "—"),
                "archive_sha256": str(registry.get("archive_sha256") or "—"),
            },
            "professional": {
                "enabled": bool(
                    scope.get("issue_date")
                    and scope.get("legal_rights")
                    and _rows(scope.get("investigations_performed"))
                    and _rows(scope.get("assumptions"))
                    and scope.get("material_uncertainty")
                ),
                "issue_date": str(scope.get("issue_date") or "—"),
                "legal_rights": str(scope.get("legal_rights") or "—"),
                "investigations_performed": [
                    str(value) for value in _rows(scope.get("investigations_performed"))
                ],
                "investigations_not_performed": [
                    str(value) for value in _rows(scope.get("investigations_not_performed"))
                ],
                "assumptions": [str(value) for value in _rows(scope.get("assumptions"))],
                "special_assumptions": [
                    str(value) for value in _rows(scope.get("special_assumptions"))
                ],
                "material_uncertainty": str(scope.get("material_uncertainty") or "—"),
                "material_esg_factors": [
                    str(value) for value in _rows(scope.get("material_esg_factors"))
                ],
            },
            "business": {
                "enabled": bool(
                    scope.get("company_business_model")
                    and _rows(scope.get("products_services"))
                    and scope.get("market_sector_overview")
                    and scope.get("competition_overview")
                    and _rows(scope.get("material_business_risks"))
                ),
                "business_model": str(scope.get("company_business_model") or "—"),
                "products_services": [
                    str(value) for value in _rows(scope.get("products_services"))
                ],
                "customer_concentration": str(scope.get("customer_concentration") or "—"),
                "supplier_dependencies": [
                    str(value) for value in _rows(scope.get("supplier_dependencies"))
                ],
                "key_person_dependencies": [
                    str(value) for value in _rows(scope.get("key_person_dependencies"))
                ],
                "market_sector_overview": str(scope.get("market_sector_overview") or "—"),
                "competition_overview": str(scope.get("competition_overview") or "—"),
                "material_business_risks": [
                    str(value) for value in _rows(scope.get("material_business_risks"))
                ],
            },
        },
        "company_overview": {
            "facts": _compact_fields(
                _field(
                    "company.registration_number",
                    copy["registration_number"],
                    context.get("registration_number"),
                    "text",
                    display,
                ),
                _field(
                    "company.business_type",
                    copy["business_type"],
                    context.get("business_type_title") or context.get("industry"),
                    "text",
                    display,
                ),
                _field(
                    "company.nace_code",
                    copy["nace_code"],
                    context.get("nace_code"),
                    "text",
                    display,
                ),
                _field(
                    "company.legal_form",
                    copy["legal_form"],
                    context.get("legal_form"),
                    "text",
                    display,
                ),
                _field(
                    "company.location",
                    copy["location"],
                    context.get("city"),
                    "text",
                    display,
                ),
                _field(
                    "company.founded",
                    copy["founded"],
                    context.get("founding_year") or context.get("incorporated_on"),
                    "text",
                    display,
                ),
            ),
            "financial_history": financial_history,
            "financial_history_chart": financial_history_chart(
                financial_history, series_labels=copy
            ),
        },
        "conclusion": {
            "selected_method": selected_method,
            "equity_mid": display(equity_mid, "currency"),
            "equity_mid_field_id": "conclusion.equity_value.mid",
            "equity_low": display(equity_low, "currency"),
            "equity_low_field_id": "conclusion.equity_value.low",
            "equity_high": display(equity_high, "currency"),
            "equity_high_field_id": "conclusion.equity_value.high",
            "enterprise_value": display(enterprise_value, "currency"),
            "enterprise_value_field_id": "conclusion.enterprise_value.mid",
            "range_classification": copy["range_label"],
            "principal_value_drivers": [
                str(value) for value in _rows(scope.get("principal_value_drivers"))
            ],
            "principal_caveats": [str(value) for value in _rows(scope.get("principal_caveats"))],
        },
        "bridge": {
            "rows": _compact_fields(
                _bridge_field(
                    "bridge.enterprise_value",
                    copy["enterprise_value"],
                    enterprise_value,
                    display,
                ),
                _bridge_field("bridge.debt", copy["debt"], debt, display, operator="−"),
                _bridge_field("bridge.cash", copy["cash"], cash, display, operator="+"),
                _bridge_field(
                    "bridge.nwc",
                    copy["working_capital_adjustment"],
                    nwc,
                    display,
                    signed_effect=True,
                ),
                _bridge_field("bridge.tax", copy["tax_latency"], tax, display, signed_effect=True),
                _bridge_field(
                    "bridge.equity_value",
                    copy["equity_value"],
                    equity_mid,
                    display,
                    operator="=",
                ),
            ),
            "net_debt": _field(
                "bridge.net_debt",
                copy["net_cash"] if net_debt < 0 else copy["net_debt"],
                net_debt,
                "currency",
                display,
            ),
            "chart": None,
        },
        "sensitivity": {
            "has_enterprise_value": enterprise_value is not None,
            "rows": [
                {
                    "scenario": copy[scenario],
                    "enterprise_value": (
                        _field(
                            f"sensitivity.{scenario}.enterprise_value",
                            copy["enterprise_value"],
                            enterprise,
                            "currency",
                            display,
                        )
                        if enterprise is not None
                        else None
                    ),
                    "equity_value": _field(
                        f"sensitivity.{scenario}.equity_value",
                        copy["equity_value"],
                        equity,
                        "currency",
                        display,
                    ),
                }
                for scenario, enterprise, equity in (
                    ("downside", enterprise_low, equity_low),
                    ("central", enterprise_value, equity_mid),
                    ("upside", enterprise_high, equity_high),
                )
            ],
        },
        "normalizations": {
            "summary_rows": normalization_summary,
            "decisions": normalizations,
            "compact_on_overview": not bool(scope.get("sustainable_earnings_commentary")),
            "commentary": str(scope.get("sustainable_earnings_commentary") or ""),
            "chart": three_value_bars(
                normalization_chart_rows,
                chart_id="normalization_bridge",
            ),
        },
        "method_pages": method_pages,
        "benchmark_chart": benchmark_distribution_chart(
            benchmark_rows,
            selected_market_field,
        ),
        "method_review": _reviewed_and_rejected_methods(context, method_pages, copy),
        "evidence": {
            "valuation_run_hash": str(context.get("sealed_valuation_run_hash") or "—"),
            "evidence_bundle_hash": str(context.get("sealed_evidence_bundle_hash") or "—"),
            "benchmark_hash": str(
                context.get("sealed_benchmark_hash") or context.get("benchmark_hash") or "—"
            ),
            "source_references": _source_reference_rows(context.get("source_references")),
            "data_quality_status": str(
                context.get("data_quality_status") or context.get("data_quality") or "—"
            ),
            "verification_rows": [
                {
                    "label": copy["valuation_run_hash"],
                    "short": _verification_id(context.get("sealed_valuation_run_hash")),
                    "full": str(context.get("sealed_valuation_run_hash") or "—"),
                },
                {
                    "label": copy["evidence_bundle_hash"],
                    "short": _verification_id(context.get("sealed_evidence_bundle_hash")),
                    "full": str(context.get("sealed_evidence_bundle_hash") or "—"),
                },
                {
                    "label": copy["benchmark_hash"],
                    "short": _verification_id(context.get("sealed_benchmark_hash")),
                    "full": str(context.get("sealed_benchmark_hash") or "—"),
                },
                {
                    "label": copy["design"],
                    "short": _verification_id(context.get("report_design_manifest_hash")),
                    "full": str(context.get("report_design_manifest_hash") or "—"),
                },
            ],
        },
        "attestation": {
            "body": copy["attestation_body"],
            "no_ivs": copy["no_ivs"],
            "limitations": [str(value) for value in _rows(scope.get("scope_limitations"))],
            "reviewer_name": str(professional_reviewer.get("name") or "—"),
            "reviewer_credentials": [
                str(value) for value in _rows(professional_reviewer.get("credentials"))
            ],
            "independence_confirmed": professional_reviewer.get("independence_confirmed") is True,
            "standards_profile": str(
                professional_review.get("standards_profile") or "EVS_BV_2026_ALIGNED"
            ),
            "standards_profile_label": copy["standards_profile"],
            "claim_state": (
                copy["aligned_no_compliance_claim"]
                if professional_review.get("claim_state") in (None, "aligned_no_compliance_claim")
                else str(professional_review.get("claim_state"))
            ),
        },
    }
    model["bridge"]["chart"] = bridge_direction_chart(
        bridge_chart_rows(model["bridge"]["rows"], locale)
    )
    context["report_certification_footer_label"] = assurance_label
    context["sealed_memorandum"] = model
    return model
