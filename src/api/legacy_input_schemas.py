"""Shared input DTOs for the legacy valuation API contract."""

from decimal import Decimal
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field, model_validator

from src.domain.financial_observations import validate_financial_observation_values

JsonObject = Dict[str, object]


class YearDataInput(BaseModel):
    """Financial data for a single year (request)."""

    year: int = Field(..., ge=2000, le=2100, description="Fiscal year")
    financial_observations: Dict[
        str, Literal["observed", "derived", "missing", "placeholder", "unknown"]
    ] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_observation_values(self) -> "YearDataInput":
        validate_financial_observation_values(self.financial_observations, self.__dict__)
        return self

    revenue: Decimal = Field(..., ge=0, description="Annual revenue in the request currency")
    ebitda: Decimal = Field(..., description="EBITDA (can be negative)")
    reported_ebitda: Optional[Decimal] = Field(
        None,
        description="Source-reported EBITDA before accepted normalization decisions",
    )
    normalized_ebitda: Optional[Decimal] = Field(
        None,
        description="EBITDA after accepted/verified normalization decisions",
    )

    ebitda_normalized: Optional[bool] = Field(
        False, description="True if EBITDA has been user-normalized"
    )
    ebitda_normalization_metadata: Optional[JsonObject] = Field(
        None, description="Metadata about user normalization adjustments"
    )

    operating_revenue: Optional[Decimal] = None
    financial_income: Optional[Decimal] = None
    extraordinary_income: Optional[Decimal] = None
    extraordinary_items: Optional[Decimal] = None
    accounting_basis_policy: Optional[str] = Field(None, min_length=1, max_length=120)
    # Signed source costs and reversals; these fields never approve normalizations.
    operating_impairments: Optional[Decimal] = Field(None, allow_inf_nan=False)
    operating_provisions: Optional[Decimal] = Field(None, allow_inf_nan=False)
    non_recurring_operating_expenses: Optional[Decimal] = Field(None, allow_inf_nan=False)
    non_recurring_financial_expenses: Optional[Decimal] = Field(None, allow_inf_nan=False)
    unclassified_pnl_expenses: Optional[Decimal] = Field(None, allow_inf_nan=False)
    total_operating_income: Optional[Decimal] = Field(None, allow_inf_nan=False)
    non_recurring_operating_income: Optional[Decimal] = Field(None, allow_inf_nan=False)
    non_recurring_financial_income: Optional[Decimal] = Field(None, allow_inf_nan=False)
    unclassified_pnl_income: Optional[Decimal] = Field(None, allow_inf_nan=False)
    cogs: Optional[Decimal] = Field(None, ge=0, description="Cost of Goods Sold")
    gross_profit: Optional[Decimal] = None
    operating_expenses: Optional[Decimal] = Field(None, ge=0)
    ebit: Optional[Decimal] = None
    depreciation: Optional[Decimal] = Field(None, ge=0)
    depreciation_amortization: Optional[Decimal] = Field(None, ge=0)
    amortization: Optional[Decimal] = Field(None, ge=0)
    interest_expense: Optional[Decimal] = Field(None, ge=0)
    tax_expense: Optional[Decimal] = Field(None, ge=0)
    owner_director_compensation: Optional[Decimal] = Field(None, ge=0)
    personnel_costs: Optional[Decimal] = Field(None, ge=0)
    rent_expense: Optional[Decimal] = Field(None, ge=0)
    net_income: Optional[Decimal] = None

    total_assets: Optional[Decimal] = Field(None, ge=0)
    current_assets: Optional[Decimal] = Field(None, ge=0)
    fixed_assets: Optional[Decimal] = Field(None, ge=0)
    cash: Optional[Decimal] = Field(None, ge=0)
    accounts_receivable: Optional[Decimal] = Field(None, ge=0)
    accounts_payable: Optional[Decimal] = Field(None, ge=0)
    inventory: Optional[Decimal] = Field(None, ge=0)
    total_liabilities: Optional[Decimal] = Field(None, ge=0)
    current_liabilities: Optional[Decimal] = Field(None, ge=0)
    short_term_debt: Optional[Decimal] = Field(None, ge=0)
    total_debt: Optional[Decimal] = Field(None, ge=0)
    total_equity: Optional[Decimal] = None
    # Consolidated dossiers only — MAR 6960x "belang van derden" booked result
    # share (advisor F08). Drives the indicative minority haircut in the
    # EV→equity bridge; 6961x employee profit participation is excluded at the
    # Hermes source. Pydantic ignores undeclared extras, so the field must be
    # declared here to survive request parsing.
    minority_interest_result_share: Optional[Decimal] = Field(
        None,
        description=(
            "Booked minority result share (MAR 6960x) on a consolidated trial "
            "balance — indicative proxy for the minority deduction in the "
            "EV→equity bridge"
        ),
    )

    # Liquidation-relevant balance-sheet line items for Hermes/manual prefill.
    # Non-negative: negative paid-up capital/DTL represent different lines.
    paid_up_capital: Optional[Decimal] = Field(None, ge=0)
    capital_subsidies: Optional[Decimal] = Field(None, ge=0)
    deferred_tax_liabilities: Optional[Decimal] = Field(None, ge=0)
    other_provisions: Optional[Decimal] = Field(None, ge=0)

    other_receivables: Optional[Decimal] = Field(None, ge=0)
    inventory_finished: Optional[Decimal] = Field(None, ge=0)
    inventory_wip: Optional[Decimal] = Field(None, ge=0)
    inventory_raw: Optional[Decimal] = Field(None, ge=0)
    land: Optional[Decimal] = Field(None, ge=0)
    buildings: Optional[Decimal] = Field(None, ge=0)
    machinery_equipment: Optional[Decimal] = Field(None, ge=0)
    vehicles: Optional[Decimal] = Field(None, ge=0)
    it_equipment: Optional[Decimal] = Field(None, ge=0)
    intangibles: Optional[Decimal] = Field(None, ge=0)
    investments: Optional[Decimal] = Field(None, ge=0)
    other_tangible: Optional[Decimal] = Field(None, ge=0)
    retained_earnings: Optional[Decimal] = None  # Z'' X2 input

    capex: Optional[Decimal] = Field(None, ge=0, description="Capital Expenditures")
    nwc_change: Optional[Decimal] = Field(None, description="Change in Net Working Capital")
    operating_cash_flow: Optional[Decimal] = None
    investing_cash_flow: Optional[Decimal] = None
    financing_cash_flow: Optional[Decimal] = None
    free_cash_flow: Optional[Decimal] = Field(
        None, description="Explicit free cash flow to the firm (FCFF) for forecast years"
    )

    is_forecast: bool = Field(False, description="True for user-provided forecast years")


class TaxLatencyInput(BaseModel):
    """Deferred tax asset or liability (belastinglatentie) for equity bridge adjustment."""

    id: str = Field("", max_length=100, description="Stable adjustment decision identifier")
    type: str = Field(
        ...,
        pattern="^(active|passive)$",
        description="'active' (asset, adds to equity) or 'passive' (liability, subtracts)",
    )
    description: str = Field("", max_length=500, description="Description of the tax latency")
    temporary_difference: Decimal = Field(
        ..., ge=0, description="Temporary difference amount in the request currency"
    )
    tax_rate: Decimal = Field(
        Decimal("25"),
        ge=0,
        le=100,
        description="Applicable tax rate as percentage (e.g. 25 for 25%)",
    )
    account_code: Optional[str] = Field(
        None, max_length=50, description="Ledger / MAR account code (optional)"
    )
    status: str = Field("proposed", max_length=32)
    evidence_id: Optional[str] = Field(None, max_length=200)
    reviewed_at: Optional[str] = Field(None, max_length=64)
    rule_version: Optional[str] = Field(None, max_length=100)
    approved_by: Optional[str] = Field(None, max_length=128)
    currency: Optional[str] = Field(None, pattern=r"^[A-Z]{3}$")
    fiscal_year: Optional[int] = Field(None, ge=1900, le=2100)
    effective_date: Optional[str] = Field(None, max_length=32)


class BalanceSheetAdjustmentInput(BaseModel):
    """Itemized balance sheet adjustment for the EV-to-equity bridge."""

    id: str = Field("", max_length=100, description="Unique identifier")
    label: str = Field(..., max_length=200, description="Line item label")
    amount: Decimal = Field(
        ...,
        ge=0,
        description=(
            "Adjustment amount in the request currency "
            "(always positive, sign determined by type)"
        ),
    )
    type: str = Field(
        ...,
        pattern="^(add|subtract)$",
        description="'add' increases equity, 'subtract' decreases equity",
    )
    category: str = Field(
        "other", pattern="^(tax_latency|excess_cash|non_operating|provision|other)$"
    )
    description: Optional[str] = Field(None, max_length=500)
    account_code: Optional[str] = Field(
        None,
        max_length=50,
        description="Ledger / MAR account code linked to this balance sheet adjustment",
    )
    # When category is tax_latency: breakdown for PDF appendix (Venus manual path)
    temporary_difference: Optional[Decimal] = Field(
        None,
        ge=0,
        description=(
            "Bruto meerwaarde / temporary difference base in the request currency "
            "for tax_latency rows"
        ),
    )
    tax_rate: Optional[Decimal] = Field(
        None,
        ge=0,
        le=100,
        description="Latency % (tax rate) for tax_latency rows when itemized for reporting",
    )
    tax_latency_type: Optional[str] = Field(
        None,
        pattern="^(active|passive)$",
        description="Semantic active/passive for tax_latency; if omitted, inferred from add/subtract",
    )
    status: str = Field("proposed", max_length=32)
    evidence_id: Optional[str] = Field(None, max_length=200)
    reviewed_at: Optional[str] = Field(None, max_length=64)
    rule_version: Optional[str] = Field(None, max_length=100)
    approved_by: Optional[str] = Field(None, max_length=128)
    currency: Optional[str] = Field(None, pattern=r"^[A-Z]{3}$")
    fiscal_year: Optional[int] = Field(None, ge=1900, le=2100)
    effective_date: Optional[str] = Field(None, max_length=32)


class ShareholderRosterEntry(BaseModel):
    id: Optional[str] = Field(None, description="Optional stable ID for a shareholder row")
    display_name: str = Field(..., min_length=1, max_length=255)
    ownership_pct: Decimal = Field(..., ge=Decimal("0"), le=Decimal("100"))
    is_working_owner: bool = Field(
        ...,
        description="True when this shareholder is an operational owner-manager",
    )
    role_title: Optional[str] = Field(None, max_length=120)


class OwnershipSummary(BaseModel):
    total_shareholder_count: int = Field(..., ge=0)
    working_owner_count: int = Field(..., ge=0)
    working_ownership_pct: Decimal = Field(..., ge=Decimal("0"), le=Decimal("100"))
    passive_shareholder_count: int = Field(..., ge=0)
    passive_ownership_pct: Decimal = Field(..., ge=Decimal("0"), le=Decimal("100"))


class HoldingConsolidationInput(BaseModel):
    """BET-293 parent/subsidiary consolidation envelope from Titan."""

    parent: JsonObject = Field(
        ...,
        description=(
            "Parent entity financial lines and identifiers. Explicit values may set "
            "value_basis_stage=pre_bridge|post_bridge; canonical valuation_run.valuation_range "
            "is always treated as post_bridge final equity."
        ),
    )
    subsidiaries: List[JsonObject] = Field(
        default_factory=list,
        max_length=50,
        description=(
            "Subsidiary entities with ownership, financial lines and optional "
            "value_basis_stage=pre_bridge|post_bridge. Canonical ValuationRun equity is "
            "post_bridge and its tax/balance adjustments are never replayed."
        ),
    )
    eliminations: Optional[JsonObject] = Field(
        None,
        description="Explicit intercompany eliminations by financial line.",
    )
    intercompany_transactions: Optional[List[JsonObject]] = Field(
        None,
        max_length=500,
        description="Transaction rows; flagged intercompany amounts are eliminated by line.",
    )
    mode: str = Field(
        "pro_rata",
        pattern="^(pro_rata|full)$",
        description="Consolidation method: pro_rata or full.",
    )
    aggregation_basis: str = Field(
        "legal_group",
        pattern="^(legal_group|common_owner_sotp)$",
        description=(
            "Server-selected basis. Legal groups may consolidate. Companies with a "
            "reviewed common owner use sum of the parts only."
        ),
    )
    assembly_provenance: Optional[JsonObject] = Field(
        None,
        description="Titan evidence, report and decision provenance for the assembled request.",
    )
    subsidiary_run_ids: List[str] = Field(
        default_factory=list,
        max_length=50,
        description="Valuation report ids used as subsidiary inputs for this parent report.",
    )
    require_valid: bool = Field(
        True,
        description="Reject invalid holding structures instead of silently clamping ownership issues.",
    )

    @model_validator(mode="after")
    def validate_entity_value_basis_stages(self) -> "HoldingConsolidationInput":
        for index, entity in enumerate((self.parent, *self.subsidiaries)):
            stage = str(entity.get("value_basis_stage") or "").strip().lower()
            if stage and stage not in {"pre_bridge", "post_bridge"}:
                label = "parent" if index == 0 else f"subsidiaries[{index - 1}]"
                raise ValueError(f"{label}.value_basis_stage must be pre_bridge or post_bridge")
        return self
