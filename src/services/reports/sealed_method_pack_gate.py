"""Fail-closed composition gate for publishable M&A memorandum method packs."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from decimal import Decimal, InvalidOperation

from src.services.reports.report_benchmark_contracts import (
    benchmark_contract_is_resolved,
    missing_benchmark_provenance,
    normalize_benchmark_contract,
)
from src.services.reports.report_pagination import SME_REPORT_MANIFEST
from src.services.reports.sealed_report_pack import sealed_template_registry


class SealedMethodPackError(ValueError):
    def __init__(self, code: str, message: str, diagnostics: object | None = None):
        super().__init__(message)
        self.code = code
        self.diagnostics = diagnostics


_METHOD_SECTION_IDS = {
    section.section_id
    for section in SME_REPORT_MANIFEST
    if section.method_key is not None
}
_PROHIBITED_MEMORANDUM_SECTIONS = {
    "business_growth_maturity",
    "sellability",
    "transaction_readiness",
}
_SEALED_TEMPLATE_REGISTRY = sealed_template_registry()


def _record(value: object) -> Mapping[str, object]:
    return value if isinstance(value, Mapping) else {}


def _decimal(value: object) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    return number if number.is_finite() else None


def _missing_records(container: Mapping[str, object], keys: Sequence[str]) -> list[str]:
    return [key for key in keys if not _record(container.get(key))]


def _has_rows(value: object) -> bool:
    return (
        isinstance(value, Sequence)
        and not isinstance(value, (str, bytes, bytearray))
        and len(value) > 0
    )


def _require_method_controls(
    method: str,
    missing: Sequence[str],
) -> None:
    if missing:
        raise SealedMethodPackError(
            "SEALED_METHOD_PROFESSIONAL_CONTROLS_INCOMPLETE",
            f"The {method} memorandum lacks one or more professional control schedules.",
            {"method": method, "missing": sorted(set(missing))},
        )


def _validate_dcf_controls(context: Mapping[str, object]) -> None:
    missing: list[str] = []
    if (_decimal(context.get("dcf_wacc")) or Decimal("0")) <= 0:
        missing.append("dcf_wacc")
    if not str(context.get("dcf_terminal_value_methodology") or "").strip():
        missing.append("dcf_terminal_value_methodology")
    if context.get("dcf_mid_year_discounting") is None:
        missing.append("dcf_mid_year_discounting")
    if not _has_rows(context.get("dcf_pv_fcf_projections")):
        missing.append("dcf_pv_fcf_projections")
    matrix = _record(context.get("dcf_sensitivity_matrix_2d"))
    if not _record(matrix.get("matrix")):
        missing.append("dcf_sensitivity_matrix_2d.matrix")
    buildup = _record(context.get("dcf_wacc_buildup"))
    direct_wacc = buildup.get("mode") == "direct_sector_wacc"
    if not direct_wacc:
        for key in ("cost_of_equity", "cost_of_debt", "equity_weight", "debt_weight"):
            if (
                _decimal(buildup.get(key)) is None
                and _decimal(context.get(f"dcf_{key}")) is None
            ):
                missing.append(f"dcf_wacc_buildup.{key}")
    _require_method_controls("dcf", missing)


def _validate_sde_controls(context: Mapping[str, object]) -> None:
    missing: list[str] = []
    for key in ("sde_value", "sde_multiple", "sde_owner_salary"):
        if _decimal(context.get(key)) is None:
            missing.append(key)
    replacement_cost = next(
        (
            context.get(key)
            for key in (
                "sde_replacement_owner_compensation",
                "replacement_owner_compensation",
                "owner_replacement_compensation",
            )
            if context.get(key) is not None
        ),
        None,
    )
    if _decimal(replacement_cost) is None:
        missing.append("replacement_owner_compensation")
    if not _has_rows(context.get("sde_components")):
        missing.append("sde_components")
    _require_method_controls("sde", missing)


def _validate_nav_controls(context: Mapping[str, object]) -> None:
    missing: list[str] = []
    if _decimal(context.get("nav_corrected_value")) is None:
        missing.append("nav_corrected_value")
    audit = _record(context.get("nav_audit_trail"))
    if not audit and not _has_rows(context.get("nav_asset_schedule")):
        missing.append("nav_audit_trail|nav_asset_schedule")
    if audit and _decimal(audit.get("tax_latency_deduction")) is None:
        missing.append("nav_audit_trail.tax_latency_deduction")
    _require_method_controls("adjusted_nav", missing)


def _validate_sotp_controls(context: Mapping[str, object]) -> None:
    missing: list[str] = []
    holding = _record(context.get("holding_sotp"))
    entities = holding.get("entity_rows")
    if not _has_rows(entities):
        missing.append("holding_sotp.entity_rows")
    else:
        assert isinstance(entities, Sequence)
        for index, raw in enumerate(entities):
            entity = _record(raw)
            for key in ("entity_name", "method", "ownership_pct"):
                if entity.get(key) in (None, ""):
                    missing.append(f"holding_sotp.entity_rows[{index}].{key}")
            if entity.get("currency") in (None, "") and holding.get("currency") in (
                None,
                "",
            ):
                missing.append(f"holding_sotp.entity_rows[{index}].currency")
            if entity.get("equity_value_mid_contribution") is None:
                missing.append(
                    f"holding_sotp.entity_rows[{index}].equity_value_mid_contribution"
                )
    for key in (
        "participation_book_value_elimination",
        "other_equity_value_elimination",
        "sotp_value_impact_elimination",
    ):
        if key not in holding:
            missing.append(f"holding_sotp.{key}")
    _require_method_controls("holding_sotp", missing)


def _validate_revenue_controls(context: Mapping[str, object]) -> None:
    if context.get("is_startup_valuation_report"):
        return
    startup = _record(context.get("startup_report"))
    traction = _record(startup.get("traction"))
    missing = [
        f"startup_report.traction.{key}"
        for key in (
            "mrr_growth_rate_pct",
            "net_revenue_retention_pct",
            "gross_margin_pct",
        )
        if _decimal(traction.get(key)) is None
    ]
    _require_method_controls("revenue_saas", missing)


def _validate_method_professional_controls(
    context: Mapping[str, object], method_ids: set[str]
) -> None:
    if "dcf" in method_ids:
        _validate_dcf_controls(context)
    if "sde" in method_ids:
        _validate_sde_controls(context)
    if "adjusted_nav" in method_ids:
        _validate_nav_controls(context)
    if "holding_sotp" in method_ids:
        _validate_sotp_controls(context)
    if {"revenue_multiple", "saas_appendix"}.intersection(method_ids):
        _validate_revenue_controls(context)


def _validate_benchmark_contract(
    context: Mapping[str, object], section_ids: Sequence[str]
) -> None:
    multiple_sections = {
        "upswitch_adaptive",
        "ebitda_multiple",
        "revenue_multiple",
        "saas_appendix",
    }
    if not multiple_sections.intersection(section_ids):
        return
    contract = normalize_benchmark_contract(context.get("benchmark_contract"))
    missing = missing_benchmark_provenance(contract)
    if not benchmark_contract_is_resolved(contract) or missing:
        raise SealedMethodPackError(
            "SEALED_BENCHMARK_PROVENANCE_INCOMPLETE",
            "A market method requires one resolved, source-complete benchmark contract.",
            {"missing": missing, "status": contract.get("status")},
        )
    if contract.get("is_borrowed") is True:
        has_independent_crosscheck = bool(
            {"dcf", "adjusted_nav", "holding_sotp"}.intersection(section_ids)
            or (_decimal(context.get("dcf_weight")) or Decimal("0")) > 0
        )
        if not has_independent_crosscheck:
            raise SealedMethodPackError(
                "SEALED_BORROWED_BENCHMARK_CROSSCHECK_REQUIRED",
                "A borrowed benchmark cannot support a stand-alone market conclusion.",
                {
                    "source_business_type_id": contract.get("source_business_type_id"),
                    "source_primary_nace_code": contract.get(
                        "source_primary_nace_code"
                    ),
                },
            )


def _validate_startup_pack(context: Mapping[str, object]) -> None:
    startup = _record(context.get("startup_report"))
    required_records = (
        "canonical",
        "weights",
        "defensibility",
        "dilution_scenario",
    )
    missing = _missing_records(startup, required_records)
    if not startup.get("stage"):
        missing.append("stage")
    if not (
        _record(startup.get("regional_reference"))
        or _record(startup.get("sector_comparables"))
    ):
        missing.append("regional_reference|sector_comparables")
    canonical = _record(startup.get("canonical"))
    low = _decimal(canonical.get("pre_money_low"))
    mid = _decimal(canonical.get("pre_money_mid"))
    high = _decimal(canonical.get("pre_money_high"))
    if low is None or mid is None or high is None or low < 0 or not low <= mid <= high:
        missing.append("canonical.ordered_pre_money_range")

    traction = _record(startup.get("traction"))
    recurring_revenue = _decimal(traction.get("arr")) or _decimal(traction.get("mrr"))
    if recurring_revenue is not None and recurring_revenue > 0:
        for key in ("mrr_growth_rate_pct", "monthly_churn_pct"):
            if _decimal(traction.get(key)) is None:
                missing.append(f"traction.{key}")
        burn = _decimal(traction.get("burn_rate_monthly"))
        if (
            burn is not None
            and burn > 0
            and _decimal(traction.get("runway_months")) is None
        ):
            missing.append("traction.runway_months")
    if missing:
        raise SealedMethodPackError(
            "SEALED_STARTUP_PACK_INCOMPLETE",
            "The startup method pack lacks required stage, method, benchmark, traction or dilution evidence.",
            {"missing": sorted(set(missing))},
        )


def _validate_liquidation_pack(context: Mapping[str, object]) -> None:
    if str(context.get("locale") or "").lower().startswith("fr"):
        raise SealedMethodPackError(
            "SEALED_LOCALE_PACK_INCOMPLETE",
            "The French liquidation memorandum is blocked until its specialist translation pack is complete.",
        )
    liquidation = _record(context.get("liquidation_report"))
    required_records = (
        "premise",
        "asset_schedule",
        "priority_cascade_orderly",
        "priority_cascade_forced",
        "tax_leakage_orderly",
        "tax_leakage_forced",
        "wind_down_orderly",
        "wind_down_forced",
        "disposal_schedule_pv_orderly",
        "disposal_schedule_pv_forced",
        "sensitivity",
        "premise_reconciliation",
        "disclosure",
        "statement_of_affairs",
        "audit_trail",
    )
    missing = _missing_records(liquidation, required_records)
    if missing:
        raise SealedMethodPackError(
            "SEALED_LIQUIDATION_PACK_INCOMPLETE",
            "The liquidation method pack lacks premise, realization, creditor, tax, timing or audit evidence.",
            {"missing": missing},
        )


def _validate_manifest_core(
    context: Mapping[str, object],
) -> tuple[list[Mapping[str, object]], list[str]]:
    raw_sections = context.get("sealed_report_sections")
    if not isinstance(raw_sections, Sequence) or isinstance(raw_sections, (str, bytes)):
        raise SealedMethodPackError(
            "SEALED_METHOD_MANIFEST_MISSING",
            "Publishable rendering requires the audited method-pack manifest.",
        )
    sections = [_record(section) for section in raw_sections]
    section_ids = [str(section.get("id") or "") for section in sections]
    if len(section_ids) != len(set(section_ids)):
        raise SealedMethodPackError(
            "SEALED_METHOD_MANIFEST_DUPLICATE",
            "The audited method-pack manifest contains duplicate sections.",
            {"section_ids": section_ids},
        )
    memorandum = _record(context.get("sealed_memorandum"))
    memorandum_scope = _record(memorandum.get("scope"))
    professional = _record(memorandum_scope.get("professional"))
    business = _record(memorandum_scope.get("business"))
    normalizations = _record(memorandum.get("normalizations"))
    expected_ids = list(_SEALED_TEMPLATE_REGISTRY)
    if professional.get("enabled") is not True:
        expected_ids.remove("professional_basis")
    if business.get("enabled") is not True:
        expected_ids.remove("business_market_analysis")
        expected_ids.remove("method_selection")
    if normalizations.get("compact_on_overview") is True:
        expected_ids.remove("normalization_bridge")
    if section_ids != expected_ids:
        raise SealedMethodPackError(
            "SEALED_METHOD_MANIFEST_INCOMPLETE",
            "The common memorandum core is incomplete or out of order.",
            {"section_ids": section_ids, "expected": expected_ids},
        )
    if _PROHIBITED_MEMORANDUM_SECTIONS.intersection(section_ids):
        raise SealedMethodPackError(
            "SEALED_METHOD_MANIFEST_SCOPE_VIOLATION",
            "The valuation memorandum includes a separately commissioned deliverable.",
            {"section_ids": section_ids},
        )
    for payload in sections:
        section_id = str(payload.get("id") or "")
        expected_template = _SEALED_TEMPLATE_REGISTRY.get(section_id)
        if (
            expected_template is None
            or payload.get("pdf_template") != expected_template
        ):
            raise SealedMethodPackError(
                "SEALED_METHOD_MANIFEST_UNREGISTERED",
                "The method-pack manifest references an unaudited template.",
                {"section_id": section_id, "pdf_template": payload.get("pdf_template")},
            )
    return sections, section_ids


def _validate_sme_manifest(context: Mapping[str, object]) -> None:
    sections, section_ids = _validate_manifest_core(context)
    method_section = next(
        (section for section in sections if section.get("id") == "method_analysis"),
        {},
    )
    raw_method_ids = method_section.get("method_family_ids")
    method_ids = (
        {str(value) for value in raw_method_ids}
        if isinstance(raw_method_ids, Sequence)
        and not isinstance(raw_method_ids, (str, bytes))
        else set()
    )
    if "fiscal_reference" in method_ids:
        raise SealedMethodPackError(
            "FISCAL_REFERENCE_SEPARATE_ARTIFACT_REQUIRED",
            "The Belgian fiscal reference is a separate advisor work product, not a valuation-memorandum method.",
            {"method_family_ids": sorted(method_ids)},
        )
    if not _METHOD_SECTION_IDS.intersection(method_ids):
        raise SealedMethodPackError(
            "SEALED_METHOD_PACK_MISSING",
            "The memorandum has no eligible valuation method pack.",
            {"method_family_ids": sorted(method_ids)},
        )

    incomplete: list[dict[str, object]] = []
    raw_coverages = method_section.get("method_component_coverages")
    coverages = (
        list(raw_coverages)
        if isinstance(raw_coverages, Sequence)
        and not isinstance(raw_coverages, (str, bytes))
        else []
    )
    for payload in coverages:
        payload = _record(payload)
        coverage = _record(payload.get("coverage"))
        missing = coverage.get("missing_required_context_keys")
        if (
            isinstance(missing, Sequence)
            and not isinstance(missing, (str, bytes))
            and missing
        ):
            incomplete.append(
                {"section_id": payload.get("id"), "missing": list(missing)}
            )
    if incomplete:
        raise SealedMethodPackError(
            "SEALED_METHOD_EVIDENCE_INCOMPLETE",
            "One or more selected methods lack required report evidence.",
            incomplete,
        )

    _validate_benchmark_contract(context, sorted(method_ids))
    _validate_method_professional_controls(context, method_ids)

    sustainable_ebitda = _decimal(
        context.get("sustainable_ebitda") or context.get("ebitda_normalized")
    )
    if (
        sustainable_ebitda is not None
        and sustainable_ebitda <= 0
        and {
            "ebitda_multiple",
            "upswitch_adaptive",
        }.intersection(method_ids)
    ):
        raise SealedMethodPackError(
            "NEGATIVE_EBITDA_EARNINGS_METHOD_PROHIBITED",
            "A non-positive sustainable EBITDA cannot support an earnings-multiple conclusion.",
            {
                "sustainable_ebitda": str(sustainable_ebitda),
                "method_family_ids": sorted(method_ids),
            },
        )


def assert_sealed_method_pack(context: Mapping[str, object]) -> None:
    """Reject legacy fallback composition and incomplete method-family packs."""

    if context.get("recommended_asking_price") is not None:
        raise SealedMethodPackError(
            "SEALED_DELIVERABLE_SCOPE_VIOLATION",
            "Asking-price strategy is not part of the valuation memorandum.",
        )
    if (
        context.get("show_transaction_readiness_section")
        or context.get("show_business_growth_maturity_section")
        or context.get("show_sellability_section")
        or context.get("has_nav_deal_structure")
    ):
        raise SealedMethodPackError(
            "SEALED_DELIVERABLE_SCOPE_VIOLATION",
            "Buyer readiness, transaction strategy and growth planning are not part of the valuation memorandum.",
        )
    if context.get("is_startup_valuation_report"):
        _validate_manifest_core(context)
        if not context.get("valuation_methodology_display"):
            raise SealedMethodPackError(
                "SEALED_STARTUP_PACK_INCOMPLETE",
                "The startup method pack lacks its governed calculation projection.",
            )
        _validate_startup_pack(context)
        return
    if context.get("is_liquidation_report"):
        _validate_manifest_core(context)
        _validate_liquidation_pack(context)
        return
    _validate_sme_manifest(context)
