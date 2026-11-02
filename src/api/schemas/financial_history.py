"""Exact actual-year facts sealed for report projection, never for repricing."""

from collections.abc import Mapping
from datetime import date
from typing import Annotated, Literal, Protocol, cast

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictInt,
    StringConstraints,
    model_validator,
)

from src.api.schemas.stateless_common import YearDataStateless

MoneyText = Annotated[
    str, StringConstraints(pattern=r"^-?[0-9]{1,48}(?:\.[0-9]{1,48})?$", max_length=98)
]
FINANCIAL_FIELDS = (
    "revenue",
    "gross_margin",
    "ebitda",
    "reported_ebitda",
    "normalized_ebitda",
    "cogs",
    "operating_revenue",
    "gross_profit",
    "financial_income",
    "extraordinary_income",
    "extraordinary_items",
    "operating_expenses",
    "ebit",
    "operating_profit",
    "depreciation",
    "depreciation_amortization",
    "amortization",
    "interest_expense",
    "tax_expense",
    "rent_expense",
    "owner_director_compensation",
    "personnel_costs",
    "filed_employee_fte",
    "net_income",
    "total_assets",
    "current_assets",
    "cash",
    "accounts_receivable",
    "accounts_payable",
    "inventory",
    "total_liabilities",
    "current_liabilities",
    "short_term_debt",
    "total_debt",
    "lease_liabilities",
    "total_equity",
    "minority_interest_result_share",
    "fixed_assets",
    "paid_up_capital",
    "capital_subsidies",
    "deferred_tax_liabilities",
    "buildings",
    "machinery_equipment",
    "other_provisions",
    "capex",
    "nwc_change",
    "operating_cash_flow",
    "investing_cash_flow",
    "financing_cash_flow",
    "free_cash_flow",
)
ATTRIBUTE_FIELDS = (
    "revenue_source",
    "ebitda_basis",
    "source_identifier",
    "source_record_id",
    "source_parser_version",
    "source_currency",
    "currency_basis",
)


class FinancialYearSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    year: Annotated[StrictInt, Field(ge=2000, le=2100)]
    period_start: date | None = None
    period_end: date | None = None
    facts: dict[str, MoneyText | None] = Field(
        json_schema_extra={
            "propertyNames": {"enum": list(FINANCIAL_FIELDS)},
            "x-non-negative-fields": [
                key
                for key in FINANCIAL_FIELDS
                if any(
                    getattr(bound, "ge", None) == 0
                    for bound in YearDataStateless.model_fields[key].metadata
                )
            ],
        }
    )
    attributes: dict[str, str | None] = Field(
        default_factory=dict,
        json_schema_extra={
            "propertyNames": {"enum": list(ATTRIBUTE_FIELDS)},
        },
    )
    ebitda_normalized: StrictBool = False
    normalization_metadata: dict[str, object] | None = None

    @model_validator(mode="after")
    def validate_actual_facts(self) -> "FinancialYearSnapshot":
        if set(self.facts) - set(FINANCIAL_FIELDS) or set(self.attributes) - set(ATTRIBUTE_FIELDS):
            raise ValueError("financial history contains an unknown financial field")
        if self.facts.get("revenue") is None or self.facts.get("ebitda") is None:
            raise ValueError("financial history requires revenue and EBITDA")
        if self.period_start and self.period_end and self.period_start > self.period_end:
            raise ValueError("financial history period boundaries are reversed")
        # Reuse the admitted year constraints without changing the exact wire strings.
        self.to_year_data()
        return self

    def to_year_data(self) -> YearDataStateless:
        return YearDataStateless.model_validate(
            {
                "year": self.year,
                "period_start": self.period_start,
                "period_end": self.period_end,
                **self.facts,
                **self.attributes,
                "is_forecast": False,
                "ebitda_normalized": self.ebitda_normalized,
                "ebitda_normalization_metadata": self.normalization_metadata,
            }
        )


class FinancialHistorySnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal["financial-history.v1"] = "financial-history.v1"
    currency: Annotated[str, StringConstraints(pattern=r"^[A-Z]{3}$")]
    current_year: Annotated[StrictInt, Field(ge=2000, le=2100)]
    actual_years: Annotated[list[FinancialYearSnapshot], Field(min_length=1, max_length=101)]

    @model_validator(mode="after")
    def validate_year_membership(self) -> "FinancialHistorySnapshot":
        years = [row.year for row in self.actual_years]
        if len(set(years)) != len(years) or max(years) != self.current_year:
            raise ValueError("financial history has duplicate years or an invalid current year")
        return self


class FinancialHistoryInput(Protocol):
    currency: str
    current_year: YearDataStateless
    historical_years: list[YearDataStateless]


def seal_financial_history(request: FinancialHistoryInput) -> dict[str, object]:
    current = request.current_year
    rows = [current, *request.historical_years]
    actuals = []
    for row in sorted((row for row in rows if not row.is_forecast), key=lambda row: row.year):
        actuals.append(
            {
                "year": row.year,
                "period_start": row.period_start,
                "period_end": row.period_end,
                "facts": {
                    key: format(value, "f") if value is not None else None
                    for key in FINANCIAL_FIELDS
                    for value in [getattr(row, key)]
                },
                "attributes": {key: getattr(row, key) for key in ATTRIBUTE_FIELDS},
                "ebitda_normalized": row.ebitda_normalized,
                "normalization_metadata": row.ebitda_normalization_metadata,
            }
        )
    return cast(
        dict[str, object],
        FinancialHistorySnapshot.model_validate(
            {
                "currency": request.currency,
                "current_year": current.year,
                "actual_years": actuals,
            }
        ).model_dump(mode="json"),
    )


def financial_history_from_lineage(
    lineage: Mapping[str, object],
) -> FinancialHistorySnapshot | None:
    value = lineage.get("financial_history")
    return FinancialHistorySnapshot.model_validate(value) if value is not None else None


def assert_supplied_year_matches(supplied: YearDataStateless, sealed: YearDataStateless) -> None:
    if supplied.year != sealed.year or supplied.is_forecast:
        raise ValueError("report financial history must match sealed actual years")
    fields = {
        *FINANCIAL_FIELDS,
        *ATTRIBUTE_FIELDS,
        "period_start",
        "period_end",
        "ebitda_normalized",
        "ebitda_normalization_metadata",
    }
    for field in supplied.model_fields_set & fields:
        if getattr(supplied, field) != getattr(sealed, field):
            from src.utils.source_policy_monitoring import (
                SourcePolicyIssue,
                record_source_policy_issue,
            )

            record_source_policy_issue(SourcePolicyIssue.REPORT_CALCULATION_MISMATCH)
            raise ValueError(
                f"report financial history {supplied.year}.{field} differs from sealed facts"
            )
