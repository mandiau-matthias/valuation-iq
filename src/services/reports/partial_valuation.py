"""Reuse monetary methods for partial inputs; never infer EBITDA from absence."""

from decimal import ROUND_HALF_EVEN, Decimal, localcontext
from types import SimpleNamespace
from typing import cast

from pydantic import BaseModel

from src.api.schemas.partial_valuation import PartialValuationRequest, PartialValuationResponse
from src.api.schemas.stateless_response_schemas import MethodResult
from src.config.country_packs import country_pack
from src.domain.explicit_fcff import explicit_fcff_payload
from src.domain.financial_arithmetic import money
from src.domain.method_keys import CANONICAL_RUNTIME_METHOD_KEYS, MethodKey
from src.domain.methods.dcf import calculate_dcf_result
from src.domain.methods.ebitda_multiple import calculate_ebitda_result
from src.domain.methods.revenue_multiple import calculate_revenue_result
from src.services.reports.stateless_valuation_run import canonical_hash


class PartialCalculationInputError(ValueError):
    """A known, unsupported input at the calculation boundary, never a runtime fallback."""


def _validate_calculation_decimals(model: BaseModel, path: str = "inputs") -> None:
    for name, value in model.__dict__.items():
        field_path = f"{path}.{name}"
        if isinstance(value, Decimal):
            if not value.is_finite() or value.copy_abs() >= Decimal("1e18"):
                raise PartialCalculationInputError(
                    f"{field_path} exceeds supported financial magnitude"
                )
            if value != value.quantize(Decimal(".00000001")):
                raise PartialCalculationInputError(f"{field_path} exceeds eight decimal places")
        elif isinstance(value, BaseModel):
            _validate_calculation_decimals(value, field_path)
        elif isinstance(value, list):
            for index, item in enumerate(value):
                if isinstance(item, BaseModel):
                    _validate_calculation_decimals(item, f"{field_path}[{index}]")


def calculate_partial_valuation(
    request: PartialValuationRequest,
    *,
    source_policy: str = "indicative",
) -> PartialValuationResponse:
    """Calculate disclosed indicative values; verification is a distinct policy.

    Source labels never establish verification. The default private assessment
    keeps its existing explicit-assumption/no-certification disclosures. Strict
    source consumers can request the sealed diagnostic-only policy explicitly.
    """
    if source_policy not in {"indicative", "verified_sources_only"}:
        raise ValueError("Unsupported partial valuation source policy")
    scenario = _calculate_partial_diagnostics(request)
    if source_policy == "indicative":
        return scenario
    from src.services.reports.partial_source_policy import seal_unverified_assessment

    return seal_unverified_assessment(scenario)


def _calculate_partial_diagnostics(
    request: PartialValuationRequest,
) -> PartialValuationResponse:
    """Shared indicative arithmetic; this never attests source verification."""
    # The shared process's Decimal context must not alter a saved financial result.
    with localcontext() as context:
        context.prec = 50
        context.rounding = ROUND_HALF_EVEN
        _validate_calculation_decimals(request)
        return _calculate_partial_valuation(request)


def _calculate_partial_valuation(
    request: PartialValuationRequest,
) -> PartialValuationResponse:
    financials = request.financials
    methods = {
        key: MethodResult(
            method_key=cast(MethodKey, key),
            label=key,
            available=False,
            value=None,
            unavailable_reason="Required method-specific financial or market evidence is unavailable.",
        )
        for key in CANONICAL_RUNTIME_METHOD_KEYS
    }
    assumptions = []
    pack = country_pack(request.country_code or "")
    pack_eligible = pack is not None and (
        pack.effective_from <= request.valuation_date
        and (pack.effective_to is None or request.valuation_date <= pack.effective_to)
        and pack.certification_state not in ("expired", "revoked")
        and financials.currency == pack.currency
    )
    if not pack_eligible:
        assumptions.append(
            "No applicable country/currency methodology pack at the measurement date; no numerical method is eligible. No implicit FX conversion is applied."
        )
    if pack_eligible:
        assumptions.append(
            "Supplied-input scenarios support indicative arithmetic only. Country-specific accounting, tax applicability, market evidence and professional certification are not verified by this calculation."
        )
    if financials.fiscal_year is None:
        assumptions.append("The earnings period is unknown; earnings multiples are unavailable.")
    bridge_known = all(
        value is not None
        for value in (
            financials.financial_debt,
            financials.cash,
            financials.nwc_adjustment,
        )
    )
    if bridge_known:
        assert (
            financials.financial_debt is not None
            and financials.cash is not None
            and financials.nwc_adjustment is not None
        )
        bridge = dict(
            total_debt=financials.financial_debt,
            cash=financials.cash,
            nwc_adjustment=financials.nwc_adjustment,
            ownership_multiplier=Decimal(1),
        )
    else:
        bridge = dict(
            total_debt=Decimal(0),
            cash=Decimal(0),
            nwc_adjustment=Decimal(0),
            ownership_multiplier=Decimal(1),
        )
    for reference in (
        request.references if pack_eligible and financials.fiscal_year is not None else []
    ):
        key = "ebitda_multiple" if reference.metric == "ebitda" else "omzet_multiple"
        assert pack is not None
        if (request.valuation_date - reference.observed_on).days > pack.benchmark_freshness_days:
            methods[key].unavailable_reason = "Market reference is stale at the measurement date."
            continue
        if (
            reference.currency != financials.currency
            or reference.country_code != request.country_code
            or reference.period_kind != financials.period_kind
        ):
            methods[key].unavailable_reason = (
                "Reference currency, country or earnings period is incompatible."
            )
            continue
        amount = getattr(financials, reference.metric)
        if amount is None:
            methods[key].unavailable_reason = (
                f"{reference.metric} is missing; it is not an observed zero."
            )
            continue
        if reference.metric == "ebitda":
            result = calculate_ebitda_result(
                ebitda=amount,
                ev_ebitda_multiple=reference.median,
                p25_multiple=reference.low,
                p75_multiple=reference.high,
                saas_adjustment=None,
                total_adjustment=Decimal(0),
                **bridge,
            )
        else:
            calibration = SimpleNamespace(
                ev_revenue_median=reference.median,
                ev_revenue_p25=reference.low,
                ev_revenue_p75=reference.high,
            )
            result = calculate_revenue_result(
                revenue=amount,
                calibration=calibration,
                total_adjustment=Decimal(0),
                total_debt=bridge["total_debt"],
                cash=bridge["cash"],
                ownership_multiplier=bridge["ownership_multiplier"],
                nwc_adjustment=bridge["nwc_adjustment"],
            )
        if not bridge_known and result.enterprise_value is not None:
            # The wrapper is used only for EV arithmetic. Its internal zero bridge
            # is discarded, not presented or committed as a shareholder estimate.
            result = result.model_copy(
                update={
                    "value": result.enterprise_value,
                    "value_low": result.enterprise_value_low,
                    "value_high": result.enterprise_value_high,
                    "equity_value": None,
                    "equity_value_low": None,
                    "equity_value_high": None,
                    "value_basis": "enterprise_value",
                    "available": result.enterprise_value > 0,
                    "unavailable_reason": None,
                }
            )
            result.details = {
                key: value
                for key, value in (result.details or {}).items()
                if not key.startswith("equity")
            }
            result.details["equity_bridge_status"] = "unavailable_missing_completion_accounts"
        if result.details is not None:
            result.details["reference_evidence_status"] = reference.evidence_status
            result.details["reference_source"] = reference.source_reference
            result.details["reference_observed_on"] = reference.observed_on.isoformat()
        methods[key] = result
        if reference.evidence_status == "disclosed_assumption":
            assumptions.append(
                f"{reference.metric} multiple is a disclosed assumption: {reference.source_reference}"
            )
    forecast = request.fcff_forecast
    if forecast is not None and pack_eligible and pack is not None:
        if forecast.currency != financials.currency:
            methods["dcf"].unavailable_reason = (
                "Forecast currency is incompatible; no implicit FX conversion."
            )
        else:
            try:
                payload = explicit_fcff_payload(forecast)
            except ValueError as exc:
                methods["dcf"].unavailable_reason = str(exc)
            else:
                result = calculate_dcf_result(
                    dcf_results=payload, dcf_exclusion_reason=None, **bridge
                )
                result.details = dict(
                    result.details or {},
                    **{
                        key: payload[key]
                        for key in (
                            "explicit_fcff_ledger",
                            "terminal_present_value",
                            "discount_timing",
                            "forecast_source",
                            "forecast_evidence_status",
                            "financing_tax_shield",
                        )
                    },
                )
                if not bridge_known and result.enterprise_value is not None:
                    result = result.model_copy(
                        update={
                            "value": result.enterprise_value,
                            "value_low": result.enterprise_value_low,
                            "value_high": result.enterprise_value_high,
                            "equity_value": None,
                            "equity_value_low": None,
                            "equity_value_high": None,
                            "value_basis": "enterprise_value",
                            "available": result.enterprise_value > 0,
                            "unavailable_reason": (
                                None
                                if result.enterprise_value > 0
                                else "No positive enterprise value."
                            ),
                        }
                    )
                    result.details = {
                        key: value
                        for key, value in (result.details or {}).items()
                        if not key.startswith("equity")
                    }
                    result.details["equity_bridge_status"] = (
                        "unavailable_missing_completion_accounts"
                    )
                methods["dcf"] = result
                assumptions.append(
                    "DCF prices the supplied unlevered forecast at annual interval ends; no APV financing benefit or inferred tax/reinvestment is added."
                )
    assets = request.fair_value_assets
    if assets is not None and pack_eligible and pack is not None:
        if (
            assets.currency != financials.currency
            or assets.valuation_date != request.valuation_date
        ):
            methods["adjusted_nav"].unavailable_reason = (
                "Appraisal currency or measurement date is incompatible."
            )
        else:
            value = money(
                assets.fair_value_assets
                - assets.all_liabilities
                - assets.disposal_costs
                - assets.tax_latencies
            )
            methods["adjusted_nav"] = MethodResult(
                method_key="adjusted_nav",
                label="Supplied fair-value net assets",
                value=value,
                equity_value=value,
                value_low=value,
                value_high=value,
                equity_value_low=value,
                equity_value_high=value,
                available=value > 0,
                unavailable_reason=(None if value > 0 else "Net asset deficit is preserved."),
                details={
                    "asset_ledger": assets.model_dump(mode="json"),
                    "liabilities_included_once": True,
                    "range_basis": {
                        "kind": "point_only",
                        "statistical_coverage": None,
                        "empirical_percentiles": False,
                    },
                },
            )
            assumptions.append(
                "Net asset value uses supplied fair values, all liabilities, disposal costs and tax latencies; no second EV-to-equity bridge is applied."
            )
    if not bridge_known:
        assumptions.append(
            "Enterprise-value methods cannot report shareholder value until financial debt, unrestricted cash and the NWC adjustment are supplied."
        )
    # These four calculators operate on explicit amounts/references, not inferred
    # country tax or accounting rules. Certification profiles remain unchanged.
    # Commit this scope beside every numerical result for all consumers.
    for method in methods.values():
        if method.value is not None or method.enterprise_value is not None:
            assert pack is not None
            method.details = dict(
                method.details or {},
                methodology_scope={
                    "schema_version": "supplied_input_scenario.v1",
                    "country_pack_version": pack.pack_version,
                    "country_code": request.country_code,
                    "currency": financials.currency,
                    "arithmetic_basis": "explicit_supplied_inputs",
                    "local_evidence_verified": False,
                    "certified": False,
                },
            )
    fields = {
        "schema_version": (
            "partial_valuation.v2"
            if request.country_code is None
            or financials.currency is None
            or financials.fiscal_year is None
            else "partial_valuation.v1"
        ),
        "evidence_revision_id": request.evidence_revision_id,
        "conclusion": (
            "numerical_methods_available"
            if any(method.available for method in methods.values())
            else (
                "numerical_results_only"
                if any(
                    method.value is not None or method.enterprise_value is not None
                    for method in methods.values()
                )
                else "no_numerical_basis"
            )
        ),
        "valuation_basis": "standalone_100_percent_control",
        "inputs": request.model_dump(mode="json"),
        "methods": {key: value.model_dump(mode="json") for key, value in methods.items()},
        "assumptions": assumptions,
        "advisor_acceptance_required": False,
        "private_save_allowed": True,
    }
    digest = canonical_hash(fields)
    return cast(
        PartialValuationResponse,
        PartialValuationResponse.model_validate(
            dict(fields, content_sha256=digest, assessment_id=f"partial_{digest}")
        ),
    )
