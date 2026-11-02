"""Generate the versioned ValuationInputCatalog from the executable schema."""

from __future__ import annotations

from collections.abc import Mapping

from src.api.schemas.stateless_api import CalculateRequest
from src.api.schemas.valuation_contracts import ValuationInputCatalog, ValuationInputFieldSpec


def build_valuation_input_catalog() -> ValuationInputCatalog:
    schema = CalculateRequest.model_json_schema()
    fields: list[ValuationInputFieldSpec] = []
    _walk_schema(schema, root=schema, path="", inherited_required=False, output=fields)
    # Several legacy-compatible request envelopes intentionally remain open
    # dictionaries at runtime. JSON Schema can only describe the envelope, so
    # overlay the governed Venus subfields explicitly; otherwise the catalog
    # would claim parity while hiding the method inputs advisors actually edit.
    known_paths = {field.path for field in fields}
    for path, field_schema in _opaque_venus_field_schemas().items():
        if path not in known_paths:
            fields.append(_field_spec(path, field_schema, required=False))
    return ValuationInputCatalog(
        fields=sorted(fields, key=lambda field: field.path),
        conditional_sections=[
            {
                "section": "dcf",
                "when": "include_dcf=true or methodology in [DCF, HYBRID]",
                "dependencies": [
                    "economic_context",
                    "historical_years[].free_cash_flow when dcf_input_mode=fcff_only",
                ],
            },
            {
                "section": "holding_sotp",
                "when": "holdings_consolidation is present",
                "dependencies": [
                    "holdings_consolidation.parent",
                    "holdings_consolidation.subsidiaries[]",
                    "holdings_consolidation.eliminations",
                ],
            },
            {
                "section": "liquidation",
                "when": "selected_method=liquidation or liquidation_inputs is present",
                "dependencies": ["liquidation_inputs", "current_year"],
            },
            {
                "section": "startup",
                "when": "selected_method=startup_valuation",
                "dependencies": ["startup_inputs", "cap_table"],
            },
            {
                "section": "owner_dependency",
                "when": "owner_dependency_factors is present",
                "dependencies": ["owner_dependency_factors"],
            },
        ],
        monetary_policy={
            "calculation_type": "Decimal",
            "missing_value_policy": "exclude_or_flag_never_silent_zero",
            "reported_adjusted_valued_separation": True,
            "rounding": "round_at_explicit_presentation_boundaries_only",
            "currency": "explicit ISO-4217; no implicit EUR relabelling",
            "adaptive_percentage_units": "percentage_inputs.v1 per-field units; unmarked fields retain legacy interpretation",
        },
    )


def _walk_schema(
    node: Mapping[str, object],
    *,
    root: Mapping[str, object],
    path: str,
    inherited_required: bool,
    output: list[ValuationInputFieldSpec],
) -> None:
    resolved = _resolve(node, root)
    properties = resolved.get("properties")
    if isinstance(properties, Mapping):
        required_fields = set(resolved.get("required") or [])
        for key, raw_child in properties.items():
            if not isinstance(raw_child, Mapping):
                continue
            child_path = f"{path}.{key}" if path else str(key)
            _walk_schema(
                raw_child,
                root=root,
                path=child_path,
                inherited_required=inherited_required or key in required_fields,
                output=output,
            )
        return

    items = resolved.get("items")
    if isinstance(items, Mapping):
        item_path = f"{path}[]"
        item_resolved = _resolve(items, root)
        if isinstance(item_resolved.get("properties"), Mapping):
            _walk_schema(
                item_resolved,
                root=root,
                path=item_path,
                inherited_required=inherited_required,
                output=output,
            )
            return

    if not path:
        return
    output.append(_field_spec(path, resolved, required=inherited_required))


def _resolve(node: Mapping[str, object], root: Mapping[str, object]) -> Mapping[str, object]:
    reference = node.get("$ref")
    if isinstance(reference, str) and reference.startswith("#/$defs/"):
        definitions = root.get("$defs")
        if isinstance(definitions, Mapping):
            target = definitions.get(reference.rsplit("/", 1)[-1])
            if isinstance(target, Mapping):
                return {**target, **{key: value for key, value in node.items() if key != "$ref"}}
    for combinator in ("anyOf", "oneOf", "allOf"):
        variants = node.get(combinator)
        if isinstance(variants, list):
            non_null = [
                _resolve(item, root)
                for item in variants
                if isinstance(item, Mapping) and item.get("type") != "null"
            ]
            if len(non_null) == 1:
                return {
                    **non_null[0],
                    **{key: value for key, value in node.items() if key != combinator},
                }
    return node


def _field_spec(
    path: str,
    schema: Mapping[str, object],
    *,
    required: bool,
) -> ValuationInputFieldSpec:
    unit = str(schema.get("x-unit") or _unit(path))
    affects_value = _affects_value(path)
    affects_uncertainty = affects_value or _affects_uncertainty(path)
    validation = {
        key: schema[key]
        for key in ("minimum", "maximum", "minLength", "maxLength", "pattern", "enum")
        if key in schema
    }
    return ValuationInputFieldSpec(
        field_id=path.replace("[]", "_item").replace(".", "__"),
        path=path,
        data_type=str(schema.get("type") or schema.get("format") or "object"),
        required=required,
        description=(str(schema.get("description")) if schema.get("description") else None),
        unit=unit,
        currency_treatment=(
            "denominated_in_request_currency"
            if unit == "currency"
            else "declares_request_currency" if unit == "iso_4217" else "not_applicable"
        ),
        business_applicability=_business_applicability(path),
        evidence_requirement=_evidence_requirement(path, affects_value),
        validation=validation,
        provenance_requirement=(
            "evidence_or_decision_reference_required_for_priced_use"
            if affects_value
            else "source_or_actor_metadata_when_available"
        ),
        affects_value=affects_value,
        affects_uncertainty=affects_uncertainty,
    )


def _unit(path: str) -> str:
    token = path.lower()
    if token.endswith("currency"):
        return "iso_4217"
    if any(part in token for part in ("percentage", "_pct", "tax_rate", "weight")):
        return "percentage_or_fraction_as_documented"
    if "multiple" in token:
        return "turns"
    if any(
        part in token
        for part in (
            "revenue",
            "ebitda",
            "cash_flow",
            "assets",
            "liabilities",
            "debt",
            "cash",
            "equity",
            "amount",
            "capex",
            "income",
            "expense",
            "capital",
            "temporary_difference",
            "post_money",
            "pre_money",
            "valuation_cap",
            "enterprise_value",
            "investment",
        )
    ):
        return "currency"
    if token.endswith("year") or ".year" in token:
        return "fiscal_year"
    return "dimensionless_or_text"


def _opaque_venus_field_schemas() -> dict[str, dict[str, object]]:
    """Catalog-only schemas for typed values carried in open runtime bags.

    Runtime compatibility remains unchanged (unknown future keys still pass
    through), while humans and AI receive field-level type/unit/validation and
    evidence semantics for every valuation-relevant Venus method input.
    """

    fields: dict[str, dict[str, object]] = {
        "business_context.percentage_input_contract.schema_version": {
            "type": "string",
            "x-unit": "policy_version",
            "enum": ["percentage_inputs.v1"],
            "description": "Versioned per-field units for adaptive DCF, SaaS and revenue-quality inputs.",
        },
        "business_context.percentage_input_contract.units": {
            "type": "object",
            "x-unit": "unit_map",
            "description": "Supported adaptive field name to percentage_points or fraction. Values are never inferred from magnitude when declared.",
        },
    }

    def add(
        prefix: str,
        names: tuple[str, ...],
        *,
        data_type: str = "number",
        unit: str = "dimensionless_or_text",
        minimum: int | float | None = None,
        maximum: int | float | None = None,
    ) -> None:
        for name in names:
            schema: dict[str, object] = {"type": data_type, "x-unit": unit}
            if minimum is not None:
                schema["minimum"] = minimum
            if maximum is not None:
                schema["maximum"] = maximum
            fields[f"{prefix}.{name}"] = schema

    add(
        "business_context",
        (
            "dcf_revenue_growth_pct",
            "dcf_ebitda_margin_pct",
            "dcf_capex_pct",
            "dcf_da_pct",
            "dcf_nwc_pct",
            "dcf_tax_rate_pct",
            "dcf_wacc_pct",
            "dcf_terminal_growth_pct",
            "dcf_risk_free_rate_pct",
            "dcf_equity_risk_premium_pct",
            "dcf_cost_of_debt_pct",
            "dcf_debt_equity_pct",
            "dcf_tax_shield_pct",
        ),
        unit="percentage_or_fraction_as_documented",
    )
    add("business_context", ("dcf_beta",), unit="dimensionless_or_text", minimum=0)
    add("business_context", ("dcf_exit_multiple",), unit="turns", minimum=0)
    fields["business_context.dcf_discounting_convention"] = {
        "type": "string",
        "enum": ["mid_year", "year_end"],
        "x-unit": "dimensionless_or_text",
    }
    fields["business_context.dcf_terminal_value_method"] = {
        "type": "string",
        "enum": ["perpetual_growth", "exit_multiple"],
        "x-unit": "dimensionless_or_text",
    }
    fields["business_context.dcf_tax_shield_projections[]"] = {
        "type": "number",
        "x-unit": "currency",
    }

    add(
        "business_context",
        (
            "nav_real_estate_adjustment",
            "nav_inventory_adjustment",
            "nav_hidden_reserves",
            "nav_goodwill_writeoff",
            "nav_receivables_adjustment",
            "nav_other_revaluations",
            "nav_off_balance_items",
            "nav_real_estate_book_value",
            "nav_real_estate_appraisal_value",
            "taxable_profit",
            "director_remuneration",
            "deal_goodwill_amount",
            "deal_seller_share_basis",
            "saas_arr",
            "saas_mrr",
            "saas_cac",
            "saas_sm_spend",
            "rev_recurring_amount",
            "rev_top_client_amount",
            "rev_contract_backlog",
            "rev_capitalized_rd_amount",
        ),
        unit="currency",
    )
    add(
        "business_context",
        (
            "nav_tax_latency_pct",
            "deal_buyer_discount_rate_pct",
            "deal_registration_duty_pct",
            "saas_arr_growth_pct",
            "saas_churn_pct",
            "saas_customer_churn_pct",
            "saas_nrr_pct",
            "saas_gross_margin_pct",
            "saas_customer_concentration_pct",
            "saas_expansion_revenue_pct",
            "rev_recurring_pct",
            "rev_top_client_concentration_pct",
            "rev_gross_churn_pct",
        ),
        unit="percentage_or_fraction_as_documented",
    )
    fields["business_context.deal_type"] = {
        "type": "string",
        "enum": ["share", "asset", "compare"],
        "x-unit": "dimensionless_or_text",
    }
    add(
        "business_context",
        (
            "deal_seller_is_individual",
            "is_financial_company",
            "is_holding_more_than_50pct_shares",
            "sme_rate_override",
        ),
        data_type="boolean",
    )
    for asset in (
        "real_estate",
        "inventory",
        "receivables",
        "hidden_reserves",
        "other_revaluations",
    ):
        fields[f"business_context.nav_per_asset_tax_rates.{asset}"] = {
            "type": "number",
            "minimum": 0,
            "maximum": 100,
            "x-unit": "percentage_or_fraction_as_documented",
        }
    add(
        "business_context.nav_equipment_revaluation",
        ("original_cost", "tax_book_value", "economic_book_value"),
        unit="currency",
        minimum=0,
    )
    add(
        "business_context.nav_equipment_revaluation",
        ("acquisition_year",),
        data_type="integer",
        unit="fiscal_year",
        minimum=1900,
        maximum=2100,
    )
    add(
        "business_context.nav_equipment_revaluation",
        ("economic_useful_life_years",),
        data_type="integer",
        unit="years",
        minimum=1,
    )

    add(
        "liquidation_inputs",
        (
            "monthly_rent",
            "paid_up_capital",
            "deferred_tax_liabilities",
            "realised_capital_gains",
            "taxable_reserves",
            "multiples_value_override",
        ),
        unit="currency",
    )
    add(
        "liquidation_inputs",
        ("headcount", "runway_months_orderly", "runway_months_forced"),
        data_type="integer",
        unit="count",
        minimum=0,
    )
    add(
        "liquidation_inputs",
        ("distress_wacc_orderly", "distress_wacc_forced", "identifiable_intangibles_uplift_pct"),
        unit="percentage_or_fraction_as_documented",
        minimum=0,
    )
    add(
        "liquidation_inputs.tax_context",
        ("shareholder_tax_basis", "exempt_liquidation_reserve", "other_box2_income"),
        unit="currency",
        minimum=0,
    )
    add(
        "liquidation_inputs.tax_context.incremental_corporate_tax",
        ("orderly", "forced"),
        unit="currency",
        minimum=0,
    )
    add("liquidation_inputs.tax_context", ("tax_year",), data_type="integer", unit="year")
    for field in ("shareholder_scope", "evidence_reference"):
        fields[f"liquidation_inputs.tax_context.{field}"] = {
            "type": "string",
            "x-unit": "dimensionless_or_text",
        }
    fields["liquidation_inputs.owner_premise_override"] = {
        "type": "string",
        "enum": ["orderly_liquidation", "forced_liquidation"],
        "x-unit": "dimensionless_or_text",
    }
    for bucket in (
        "super_preferent_employees",
        "preferent_tax",
        "preferent_other",
        "secured",
        "unsecured",
        "subordinated",
        "estate_costs",
    ):
        fields[f"liquidation_inputs.liability_buckets.{bucket}"] = {
            "type": "number",
            "minimum": 0,
            "x-unit": "currency",
        }
    for asset in (
        "land",
        "buildings",
        "machinery_equipment",
        "vehicles",
        "it_equipment",
        "intangibles",
        "inventory_raw",
        "inventory_wip",
        "inventory_finished",
        "trade_receivables",
        "other_receivables",
        "cash",
    ):
        fields[f"liquidation_inputs.asset_overrides.{asset}.adjusted_value"] = {
            "type": "number",
            "minimum": 0,
            "x-unit": "currency",
        }

    add(
        "fiscal_inputs",
        ("acquisition_cost", "anchor_2_value", "anchor_3_value", "anchor_4_value"),
        unit="currency",
        minimum=0,
    )
    fields["fiscal_inputs.company_role"] = {
        "type": "string",
        "x-unit": "dimensionless_or_text",
    }
    fields["fiscal_inputs.internal_transfer"] = {
        "type": "boolean",
        "x-unit": "dimensionless_or_text",
    }
    fields["fiscal_inputs.ebitda_basis"] = {
        "type": "string",
        "enum": ["statutair", "genormaliseerd"],
        "x-unit": "dimensionless_or_text",
    }
    fields["fiscal_inputs.reference_date"] = {
        "type": "string",
        "format": "date",
        "x-unit": "date",
    }
    fields["fiscal_inputs.anchors_acknowledged"] = {
        "type": "boolean",
        "x-unit": "dimensionless_or_text",
    }
    return fields


def _affects_value(path: str) -> bool:
    prefixes = (
        "current_year",
        "historical_years",
        "normalizations",
        "business_context.dcf_",
        "business_context.nav_",
        "business_context.deal_",
        "business_context.saas_",
        "business_context.rev_",
        "business_context.taxable_profit",
        "business_context.director_remuneration",
        "business_context.is_financial_company",
        "business_context.is_holding_more_than_50pct_shares",
        "business_context.sme_rate_override",
        "business_type_calibration",
        "economic_context",
        "owner_dependency",
        "tax_latencies",
        "balance_sheet_adjustments",
        "holdings_consolidation",
        "liquidation_inputs",
        "fiscal_inputs",
        "startup_inputs",
        "cap_table",
        "user_weights",
        "real_estate_",
        "estimated_market_rent",
        "multiple_calibration_adjustment",
        "business_type_multiple_overrides",
        "effective_multiple_override",
        "historical_ebitda_weighting",
        "historical_ebitda_weights",
        "multiple_type_weights",
        "risk_analysis_enabled",
        "advisor_discount_weights",
        "discount_floor_factor",
        "business_type_segments",
        "shares_for_sale",
        "dcf_input_mode",
        "methodology",
        "selected_method",
    )
    return path.startswith(prefixes)


def _affects_uncertainty(path: str) -> bool:
    return any(
        token in path
        for token in (
            "evidence",
            "benchmark",
            "confidence",
            "source",
            "forecast",
            "override",
            "official_financials",
        )
    )


def _business_applicability(path: str) -> list[str]:
    if path.startswith("holdings_consolidation"):
        return ["holding", "patrimonium", "group"]
    if path.startswith("startup_inputs") or path.startswith("cap_table"):
        return ["startup", "venture"]
    if path.startswith("liquidation_inputs"):
        return ["liquidation", "distressed", "orderly_wind_down"]
    if path.startswith("owner_dependency"):
        return ["owner_managed_sme"]
    return ["all_applicable_business_archetypes"]


def _evidence_requirement(path: str, affects_value: bool) -> str:
    if path.startswith("valuation_case"):
        return "versioned_contract"
    if path.startswith(("current_year", "historical_years")):
        return "reported_fact_or_explicit_forecast"
    if path in {"methodology", "selected_method", "include_dcf", "include_multiples"}:
        return "explicit_instruction_and_versioned_method_eligibility_policy"
    if path == "asking_price_buffer_pct":
        return "accepted_decision_or_versioned_transaction_pricing_policy"
    if affects_value:
        return "accepted_decision_or_versioned_policy"
    return "contextual"
