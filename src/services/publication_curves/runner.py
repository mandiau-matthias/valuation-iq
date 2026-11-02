"""Pure deterministic ValuationIQ runner for Workstream D v9 curves."""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from datetime import date, datetime
from decimal import ROUND_HALF_EVEN, Decimal
from typing import Any, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from src.config.country_packs import COUNTRY_PACK_SCHEMA_VERSION, country_pack

from .contracts import (
    SHA256_PATTERN,
    BenchmarkContractV2,
    BroadMedianPriorContractV1,
    ConfidenceLevel,
    CurveCompanyInputV1,
    MappingStatus,
    MAX_PUBLIC_CURVE_PERIODS,
    ModelPriorContractV1,
    MultipleBandV1,
    MultipleContractV9,
    MultipleMetric,
    MultipleSourceKind,
    RevenueSourceKind,
    ValuationGrade,
    ValueBasis,
)

MODEL_VERSION = "valuationiq_public_curve_v9"
CURRENT_MODEL_HISTORICAL_LABEL = (
    "Current-model implied valuation applied to historical official financials."
)
PUBLICATION_GRADE_PERIOD_FLOORS = {
    "T2-E": 0,
    "T2-B": 2,
    "T2-M": 2,
    "T3-M": 3,
    "T3-O": 2,
}
_RICH_MODELED_SCOPE_PATTERN = re.compile(
    r"^(?:global|regional):[a-z0-9][a-z0-9._+-]{0,31}:"
    r"(?:business-type:[a-z0-9][a-z0-9._+-]{0,119}|broad)$"
)
_RICH_OBSERVED_SCOPE_PATTERN = re.compile(
    r"^country:[A-Z]{2}:business-type:[a-z0-9][a-z0-9._+-]{0,119}$"
)


def _canonical_json(value: object) -> bytes:
    def default(item: object) -> object:
        if isinstance(item, Decimal):
            return format(item, "f")
        if isinstance(item, (date, datetime)):
            return item.isoformat()
        raise TypeError(f"unsupported canonical JSON value: {type(item).__name__}")

    return json.dumps(
        value,
        default=default,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_json(value)).hexdigest()


def _money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN)


class _FrozenOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class EligibleMethodV1(_FrozenOutput):
    method: MultipleMetric
    metric_value: Decimal
    metric_evidence_basis: str
    output_basis: ValueBasis
    low: Decimal
    median: Decimal
    high: Decimal
    weight: Decimal = Field(gt=0, le=1)
    contract_id: str
    source_kind: MultipleSourceKind
    multiple_low: Decimal
    multiple_median: Decimal
    multiple_high: Decimal
    enterprise_to_equity_bridge: Decimal | None
    business_fit: Decimal = Field(gt=0, le=1)
    evidence_quality: Decimal = Field(gt=0, le=1)
    model_quality: Decimal = Field(gt=0, le=1)
    dispersion_quality: Decimal = Field(gt=0, le=1)

    @model_validator(mode="after")
    def validate_value_range(self) -> "EligibleMethodV1":
        if not self.low <= self.median <= self.high:
            raise ValueError("method value range must satisfy low <= median <= high")
        return self


class CurvePointV1(_FrozenOutput):
    period_end: str
    fiscal_year: int
    source_record_id: str
    source_document_version: str
    source_sha256: str = Field(pattern=SHA256_PATTERN)
    currency: str
    output_basis: ValueBasis
    low: Decimal
    median: Decimal
    high: Decimal
    methods: tuple[EligibleMethodV1, ...] = Field(min_length=1)
    confidence: ConfidenceLevel
    segment_id: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_point(self) -> "CurvePointV1":
        if not self.low <= self.median <= self.high:
            raise ValueError("curve point must satisfy low <= median <= high")
        if sum((item.weight for item in self.methods), Decimal("0")) != Decimal("1"):
            raise ValueError("curve point method weights must sum to exactly 1")
        if any(item.output_basis != self.output_basis for item in self.methods):
            raise ValueError("enterprise and equity values cannot be mixed in a point")
        return self


class ContractFreshnessDecisionV1(_FrozenOutput):
    contract_id: str
    source_kind: MultipleSourceKind
    effective_date: date
    frozen_at: datetime
    age_days: int = Field(ge=0)
    freshness_limit_days: int = Field(gt=0)
    freshness_status: Literal["current"] = "current"
    sample_size: int | None = Field(default=None, ge=1)
    observation_window_start: date | None = None
    observation_window_end: date | None = None


class PublicCurveResultV1(_FrozenOutput):
    schema_version: str = "PublicCurveResultV1"
    company_key: str
    tier: str
    valuation_grade: ValuationGrade
    curve_status: str
    curve_temporality: str
    disclosure_label: str
    mapping_status: str
    mapping_version: str | None
    multiple_scope: str = Field(min_length=1, max_length=160)
    multiple_source_kind: str
    multiple_manifest_sha256: str = Field(pattern=SHA256_PATTERN)
    valuation_as_of: date
    country_pack_schema_version: str
    country_pack_version: str
    contract_freshness: tuple[ContractFreshnessDecisionV1, ...] = Field(min_length=1)
    prior_weight: Decimal = Field(ge=0, le=1)
    official_period_count: int = Field(ge=2, le=MAX_PUBLIC_CURVE_PERIODS)
    resolved_checkpoint_count: int = Field(ge=2, le=MAX_PUBLIC_CURVE_PERIODS)
    method_set: tuple[MultipleMetric, ...] = Field(min_length=1)
    output_basis: str
    input_fingerprint: str = Field(pattern=SHA256_PATTERN)
    model_version: str
    result_sha256: str = Field(pattern=SHA256_PATTERN)
    calculation_idempotency_key: str
    import_idempotency_key: str
    material_content_hash: str = Field(pattern=SHA256_PATTERN)
    index_decision: str
    rollout_state: str
    reason_codes: tuple[str, ...]
    points: tuple[CurvePointV1, ...] = Field(
        min_length=2,
        max_length=MAX_PUBLIC_CURVE_PERIODS,
    )

    @field_validator("tier")
    @classmethod
    def require_tier(cls, value: str) -> str:
        if value not in {"T2", "T3"}:
            raise ValueError("public curve tier must be T2 or T3")
        return value

    @field_validator("curve_status")
    @classmethod
    def require_available(cls, value: str) -> str:
        if value != "available":
            raise ValueError("curve-backed public result must be available")
        return value

    @field_validator("mapping_status")
    @classmethod
    def require_public_mapping_status(cls, value: str) -> str:
        if value not in {"reviewed", "unavailable"}:
            raise ValueError("mapping_status must be reviewed or unavailable")
        return value

    @field_validator("output_basis")
    @classmethod
    def require_public_output_basis(cls, value: str) -> str:
        if value not in {"enterprise_value", "equity_value"}:
            raise ValueError("output_basis must use the shared public v9 vocabulary")
        return value

    @field_validator("multiple_source_kind")
    @classmethod
    def require_public_source_kind(cls, value: str) -> str:
        allowed = {"MODELED_PRIOR", "MODELED_BROAD_PRIOR", "OBSERVED_CLOSED_DEALS"}
        if value not in allowed:
            raise ValueError("multiple_source_kind must use the shared public v9 vocabulary")
        return value

    @model_validator(mode="after")
    def validate_public_grade_contract(self) -> "PublicCurveResultV1":
        expected_tier = (
            "T3" if self.valuation_grade in {ValuationGrade.T3_M, ValuationGrade.T3_O} else "T2"
        )
        if self.tier != expected_tier:
            raise ValueError("tier must match valuation_grade")
        if self.valuation_grade == ValuationGrade.T3_O:
            if self.multiple_source_kind != "OBSERVED_CLOSED_DEALS":
                raise ValueError("T3-O requires an observed-market contract")
            if self.prior_weight != 0:
                raise ValueError("T3-O requires prior_weight=0")
        elif self.multiple_source_kind == "OBSERVED_CLOSED_DEALS":
            raise ValueError("observed-market contracts must emit T3-O")
        elif self.prior_weight <= 0:
            raise ValueError("modeled curves require a positive prior weight")
        if self.valuation_grade == ValuationGrade.T2_B:
            if self.mapping_status != "unavailable":
                raise ValueError("T2-B requires unavailable exact mapping")
            if self.multiple_source_kind != "MODELED_BROAD_PRIOR":
                raise ValueError("T2-B requires a governed broad prior")
        if (
            self.valuation_grade
            in {
                ValuationGrade.T2_M,
                ValuationGrade.T3_M,
                ValuationGrade.T3_O,
            }
            and self.mapping_status != "reviewed"
        ):
            raise ValueError("mapped and observed grades require reviewed mapping")
        required_periods = PUBLICATION_GRADE_PERIOD_FLOORS[self.valuation_grade.value]
        distinct_periods = {point.period_end for point in self.points}
        if (
            self.official_period_count < required_periods
            or self.resolved_checkpoint_count < required_periods
            or len(distinct_periods) < required_periods
        ):
            raise ValueError(
                f"{self.valuation_grade.value} requires at least {required_periods} "
                "distinct official resolved periods"
            )
        return self


class PublicCurveBlockedV1(_FrozenOutput):
    schema_version: str = "PublicCurveBlockedV1"
    company_key: str
    curve_status: str = "blocked"
    input_fingerprint: str = Field(pattern=SHA256_PATTERN)
    model_version: str = MODEL_VERSION
    multiple_manifest_sha256: str = Field(pattern=SHA256_PATTERN)
    valuation_as_of: date
    country_pack_version: str | None = None
    official_period_count: int = Field(ge=0, le=MAX_PUBLIC_CURVE_PERIODS)
    resolved_checkpoint_count: int = Field(ge=0, le=MAX_PUBLIC_CURVE_PERIODS)
    reason_codes: tuple[str, ...] = Field(min_length=1)


_PUBLIC_SOURCE_KIND = {
    MultipleSourceKind.MODELED_PRIOR: "MODELED_PRIOR",
    MultipleSourceKind.MODELED_BROAD_PRIOR: "MODELED_BROAD_PRIOR",
    MultipleSourceKind.OBSERVED_MARKET: "OBSERVED_CLOSED_DEALS",
}


def _canonical_decimal(value: Decimal) -> str:
    """Return Delphi-compatible, exponent-free canonical decimal text."""

    if not value.is_finite():
        raise ValueError("public decimal must be finite")
    normalized = format(value.normalize(), "f")
    return "0" if value == 0 else normalized


def _public_sha256(value: str) -> str:
    """Return the sha256-prefixed digest required by Delphi and Mercury."""

    if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        raise ValueError("public SHA-256 digest must be lowercase hexadecimal")
    return f"sha256:{value}"


def _public_multiple_scope(result: PublicCurveResultV1) -> str:
    """Return the canonical self-describing Delphi v9 multiple scope."""

    expected = (
        _RICH_OBSERVED_SCOPE_PATTERN
        if result.multiple_source_kind == "OBSERVED_CLOSED_DEALS"
        else _RICH_MODELED_SCOPE_PATTERN
    )
    if expected.fullmatch(result.multiple_scope) is None:
        raise ValueError("multiple_scope is not canonical rich v9 material")
    return result.multiple_scope


def _multiple_scope(contract: MultipleContractV9) -> str:
    """Seal geography and population identity without relying on side fields."""

    if isinstance(contract, BenchmarkContractV2):
        scope = (
            f"country:{contract.country_code}:business-type:" f"{contract.business_type_id.lower()}"
        )
        pattern = _RICH_OBSERVED_SCOPE_PATTERN
    elif isinstance(contract, ModelPriorContractV1):
        scope = (
            f"{contract.geography_scope.value.lower()}:"
            f"{contract.geography_code.lower()}:business-type:"
            f"{contract.business_type_id.lower()}"
        )
        pattern = _RICH_MODELED_SCOPE_PATTERN
    else:
        scope = (
            f"{contract.geography_scope.value.lower()}:" f"{contract.geography_code.lower()}:broad"
        )
        pattern = _RICH_MODELED_SCOPE_PATTERN
    if len(scope) > 160 or pattern.fullmatch(scope) is None:
        raise ValueError("multiple contract cannot form a canonical rich v9 scope")
    return scope


_PUBLIC_BAND_MINIMUM_HALF_WIDTH = Decimal("0.30")


def _public_band_bounds(point: CurvePointV1) -> tuple[Decimal, Decimal]:
    """Apply the public evidence floor without mutating the raw calculation."""

    floor_amount = point.median * _PUBLIC_BAND_MINIMUM_HALF_WIDTH
    return min(point.low, point.median - floor_amount), max(point.high, point.median + floor_amount)


def to_public_seal_v9(result: PublicCurveResultV1) -> dict[str, object]:
    """Translate internal calculation enums to the Delphi/edge v9 seal.

    This is the only casing/source-name compatibility boundary.  It prevents
    independent importers from inventing subtly different translations while
    leaving the immutable ValuationIQ calculation result intact.

    The upstream regrader remains responsible for binding each point to the
    complete OfficialFinancialPeriodV2 key and `official_period_sha256`.
    `source_sha256` here is the immutable source-document digest, not a digest
    of the complete normalized official-period record.
    """
    return {
        "public_graph_grade": result.valuation_grade.value,
        # Two-release compatibility aliases. New consumers must use the
        # explicit grade above; generic `tier` is otherwise ambiguous. The
        # compatibility tier is a curve tier, never company-graph maturity.
        "tier": result.tier,
        "valuation_grade": result.valuation_grade.value,
        "curve_status": result.curve_status,
        "curve_temporality": result.curve_temporality,
        "mapping_status": result.mapping_status,
        "mapping_version": result.mapping_version,
        "multiple_scope": _public_multiple_scope(result),
        "multiple_source_kind": result.multiple_source_kind,
        "multiple_manifest_sha256": _public_sha256(result.multiple_manifest_sha256),
        "valuation_as_of": result.valuation_as_of.isoformat(),
        "country_pack_schema_version": result.country_pack_schema_version,
        "country_pack_version": result.country_pack_version,
        "contract_freshness": [item.model_dump(mode="json") for item in result.contract_freshness],
        "prior_weight": _canonical_decimal(result.prior_weight),
        "official_period_count": result.official_period_count,
        "resolved_checkpoint_count": result.resolved_checkpoint_count,
        "method_set": [method.value for method in result.method_set],
        "output_basis": result.output_basis,
        "input_fingerprint": _public_sha256(result.input_fingerprint),
        "material_content_hash": _public_sha256(result.material_content_hash),
        "index_decision": result.index_decision,
        "rollout_state": result.rollout_state,
        "reason_codes": sorted(set(result.reason_codes)),
        "result_sha256": _public_sha256(result.result_sha256),
        "calculation_idempotency_key": result.calculation_idempotency_key,
        "import_idempotency_key": result.import_idempotency_key,
        "display_policy": "band_only",
        "minimum_published_half_width": _canonical_decimal(_PUBLIC_BAND_MINIMUM_HALF_WIDTH),
        "points": [
            {
                "period_end": point.period_end,
                "fiscal_year": point.fiscal_year,
                "source_record_id": point.source_record_id,
                "source_document_version": point.source_document_version,
                "source_document_sha256": _public_sha256(point.source_sha256),
                "currency": point.currency,
                "output_basis": point.output_basis.value.lower(),
                "low": _canonical_decimal(_public_band_bounds(point)[0]),
                "median": _canonical_decimal(point.median),
                "high": _canonical_decimal(_public_band_bounds(point)[1]),
                "raw_low": _canonical_decimal(point.low),
                "raw_high": _canonical_decimal(point.high),
                "median_display_allowed": False,
                "method_set": [method.method.value for method in point.methods],
                "confidence": point.confidence.value.lower(),
                "segment_id": point.segment_id,
            }
            for point in result.points
        ],
    }


def _contract_band(contract: MultipleContractV9) -> MultipleBandV1:
    return contract.band


def _source_kind(contract: MultipleContractV9) -> MultipleSourceKind:
    return contract.source_kind


def _method_output_basis(method: MultipleMetric, period: Any) -> ValueBasis:
    if method == MultipleMetric.PE:
        return ValueBasis.EQUITY_VALUE
    has_bridge = all(
        getattr(period, name) is not None
        for name in ("interest_bearing_debt", "lease_liabilities", "cash")
    )
    return ValueBasis.EQUITY_VALUE if has_bridge else ValueBasis.ENTERPRISE_VALUE


def _metric_value(
    method: MultipleMetric,
    period: Any,
    *,
    revenue_multiple_reviewed: bool,
) -> tuple[Decimal | None, str]:
    if method == MultipleMetric.EV_EBITDA:
        if period.reported_ebitda is not None:
            return period.reported_ebitda, "reported_ebitda"
        if period.ebit is not None and period.depreciation_amortization is not None:
            return (
                period.ebit + period.depreciation_amortization,
                "disclosed_ebit_plus_disclosed_depreciation_amortization",
            )
        return None, "missing_reported_ebitda_or_disclosed_ebit_da"
    if method == MultipleMetric.EV_EBIT:
        return period.ebit, "reported_ebit"
    if method == MultipleMetric.PE:
        return period.net_income, "reported_net_income"
    if method == MultipleMetric.EV_REVENUE:
        if not revenue_multiple_reviewed:
            return None, "revenue_method_not_reviewed_for_archetype"
        if period.revenue_source != RevenueSourceKind.TURNOVER:
            return None, "turnover_not_genuine_or_not_disclosed"
        return period.revenue, "reported_turnover"


def _bridge(period: Any, output_basis: ValueBasis) -> Decimal | None:
    if output_basis != ValueBasis.EQUITY_VALUE:
        return None
    if not all(
        getattr(period, name) is not None
        for name in ("interest_bearing_debt", "lease_liabilities", "cash")
    ):
        return None
    debt = cast(Decimal, period.interest_bearing_debt)
    leases = cast(Decimal, period.lease_liabilities)
    cash = cast(Decimal, period.cash)
    return debt + leases - cash


def _value_range(
    metric_value: Decimal,
    band: MultipleBandV1,
    output_basis: ValueBasis,
    bridge: Decimal | None,
) -> tuple[Decimal, Decimal, Decimal] | None:
    adjustment = bridge if output_basis == ValueBasis.EQUITY_VALUE and bridge is not None else 0
    values = tuple(
        _money(metric_value * multiple - adjustment) for multiple in band.model_dump().values()
    )
    low, median, high = values
    if low <= 0 or median <= 0 or high <= 0 or not low <= median <= high:
        return None
    return low, median, high


def _evidence_quality(evidence_basis: str, period: Any) -> Decimal:
    score = Decimal("1")
    if "plus_disclosed" in evidence_basis:
        score -= Decimal("0.15")
    if period.material_fact_count < 6:
        score -= Decimal("0.15")
    return max(Decimal("0.1"), score)


def _dispersion_quality(band: MultipleBandV1) -> Decimal:
    spread = (band.high - band.low) / band.median
    return max(Decimal("0.1"), Decimal("1") / (Decimal("1") + spread))


def _confidence_score(level: ConfidenceLevel) -> Decimal:
    return {
        ConfidenceLevel.LOW: Decimal("0.4"),
        ConfidenceLevel.MEDIUM: Decimal("0.7"),
        ConfidenceLevel.HIGH: Decimal("1"),
    }[level]


def _build_period_methods(
    company: CurveCompanyInputV1,
    period: Any,
    contracts: tuple[MultipleContractV9, ...],
) -> tuple[list[EligibleMethodV1], list[str]]:
    staged: list[
        tuple[
            MultipleContractV9,
            Decimal,
            str,
            ValueBasis,
            tuple[Decimal, Decimal, Decimal],
            Decimal | None,
            Decimal,
            Decimal,
            Decimal,
            Decimal,
        ]
    ] = []
    reasons: list[str] = []
    for contract in sorted(contracts, key=lambda item: (item.metric.value, item.contract_id)):
        metric_value, evidence_basis = _metric_value(
            contract.metric,
            period,
            revenue_multiple_reviewed=company.revenue_multiple_reviewed,
        )
        if metric_value is None:
            reasons.append(f"{contract.metric.value}:{evidence_basis}")
            continue
        if metric_value <= 0:
            reasons.append(f"{contract.metric.value}:non_positive_fact")
            continue
        output_basis = _method_output_basis(contract.metric, period)
        bridge = _bridge(period, output_basis)
        band = _contract_band(contract)
        value_range = _value_range(metric_value, band, output_basis, bridge)
        if value_range is None:
            reasons.append(f"{contract.metric.value}:non_positive_value_range")
            continue
        business_fit = company.method_business_fit.get(contract.metric, Decimal("0.5"))
        evidence_quality = _evidence_quality(evidence_basis, period)
        model_quality = _confidence_score(company.model_confidence) * contract.confidence
        dispersion_quality = _dispersion_quality(band)
        raw_weight = business_fit * evidence_quality * model_quality * dispersion_quality
        staged.append(
            (
                contract,
                metric_value,
                evidence_basis,
                output_basis,
                value_range,
                bridge,
                business_fit,
                evidence_quality,
                model_quality,
                dispersion_quality,
            )
        )

    # Enterprise and equity outputs can never be blended. Prefer the basis with
    # most eligible methods; ties prefer equity because it is directly useful
    # to a company owner. This selection is independent of output magnitude.
    by_basis: dict[ValueBasis, list[Any]] = defaultdict(list)
    for item in staged:
        by_basis[item[3]].append(item)
    if not by_basis:
        return [], reasons
    basis = max(
        by_basis,
        key=lambda value: (len(by_basis[value]), value == ValueBasis.EQUITY_VALUE),
    )
    selected = by_basis[basis]
    raw_weights = [item[6] * item[7] * item[8] * item[9] for item in selected]
    total_weight = sum(raw_weights, Decimal("0"))
    methods: list[EligibleMethodV1] = []
    for item, raw_weight in zip(selected, raw_weights):
        (
            contract,
            metric_value,
            evidence_basis,
            output_basis,
            values,
            bridge,
            fit,
            evidence,
            model,
            dispersion,
        ) = item
        band = _contract_band(contract)
        weight = Decimal("1") if len(selected) == 1 else raw_weight / total_weight
        methods.append(
            EligibleMethodV1(
                method=contract.metric,
                metric_value=metric_value,
                metric_evidence_basis=evidence_basis,
                output_basis=output_basis,
                low=values[0],
                median=values[1],
                high=values[2],
                weight=weight,
                contract_id=contract.contract_id,
                source_kind=contract.source_kind,
                multiple_low=band.low,
                multiple_median=band.median,
                multiple_high=band.high,
                enterprise_to_equity_bridge=bridge,
                business_fit=fit,
                evidence_quality=evidence,
                model_quality=model,
                dispersion_quality=dispersion,
            )
        )
    return methods, reasons


def _point(period: Any, methods: list[EligibleMethodV1], segment_id: str) -> CurvePointV1:
    low = _money(sum((method.low * method.weight for method in methods), Decimal("0")))
    median = _money(sum((method.median * method.weight for method in methods), Decimal("0")))
    high = _money(sum((method.high * method.weight for method in methods), Decimal("0")))
    weakest = min(
        (
            min(method.evidence_quality, method.model_quality, method.dispersion_quality)
            for method in methods
        ),
        default=Decimal("0"),
    )
    confidence = (
        ConfidenceLevel.HIGH
        if weakest >= Decimal("0.8")
        else ConfidenceLevel.MEDIUM if weakest >= Decimal("0.55") else ConfidenceLevel.LOW
    )
    return CurvePointV1(
        period_end=period.period_end.isoformat(),
        fiscal_year=period.fiscal_year,
        source_record_id=period.source_record_id,
        source_document_version=period.source_document_version,
        source_sha256=period.source_sha256,
        currency=period.currency,
        output_basis=methods[0].output_basis,
        low=low,
        median=median,
        high=high,
        methods=tuple(methods),
        confidence=confidence,
        segment_id=segment_id,
    )


def _segments(points: list[CurvePointV1]) -> list[CurvePointV1]:
    result: list[CurvePointV1] = []
    previous_signature: tuple[ValueBasis, tuple[MultipleMetric, ...]] | None = None
    segment_number = 0
    for point in points:
        signature = (point.output_basis, tuple(item.method for item in point.methods))
        if signature != previous_signature:
            segment_number += 1
            previous_signature = signature
        result.append(point.model_copy(update={"segment_id": f"segment-{segment_number}"}))
    return result


def _common_t3_base_reasons(
    company: CurveCompanyInputV1,
    points: list[CurvePointV1],
    *,
    minimum_resolved_periods: int = 3,
) -> list[str]:
    reasons: list[str] = []
    distinct_resolved_periods = {point.period_end for point in points}
    if len(distinct_resolved_periods) < minimum_resolved_periods:
        reasons.append(
            "t3_requires_three_resolved_official_periods"
            if minimum_resolved_periods == 3
            else "fewer_than_two_resolved_official_checkpoints"
        )

    period_by_source = {period.source_record_id: period for period in company.periods}
    resolved_periods = [
        period_by_source[point.source_record_id]
        for point in points
        if point.source_record_id in period_by_source
    ]
    if any(period.material_fact_count < 6 for period in resolved_periods):
        reasons.append("t3_requires_six_material_facts_per_resolved_period")
    latest = max(resolved_periods, key=lambda item: item.period_end, default=None)
    if latest is None or latest.filed_at < company.freshness_cutoff:
        reasons.append("t3_latest_filing_is_stale")

    stable_signature = {
        (point.output_basis, tuple(item.method for item in point.methods)) for point in points
    }
    if len(stable_signature) != 1:
        reasons.append("t3_method_or_value_basis_is_not_continuous")
    if len({period.statement_scope for period in resolved_periods}) != 1:
        reasons.append("t3_financial_statement_scope_is_not_continuous")
    if len({period.currency for period in resolved_periods}) != 1:
        reasons.append("t3_currency_is_not_continuous")
    if company.input_confidence != ConfidenceLevel.HIGH:
        reasons.append("t3_requires_high_input_confidence")
    if company.blocking_value_contradictions:
        reasons.append("t3_has_blocking_value_contradiction")
    return reasons


def _grade(
    company: CurveCompanyInputV1,
    contract: MultipleContractV9,
    points: list[CurvePointV1],
) -> ValuationGrade:
    if isinstance(contract, BenchmarkContractV2):
        if company.mapping_status != MappingStatus.REVIEWED:
            raise ValueError("T3-O requires reviewed NACE to business-type mapping")
        if _common_t3_base_reasons(company, points, minimum_resolved_periods=2):
            raise ValueError("T3-O requires the common T3 evidence base")
        return ValuationGrade.T3_O
    mapped = isinstance(contract, ModelPriorContractV1)
    if (
        mapped
        and not _common_t3_base_reasons(company, points)
        and company.model_confidence == ConfidenceLevel.HIGH
    ):
        return ValuationGrade.T3_M
    return ValuationGrade.T2_M if mapped else ValuationGrade.T2_B


def _validate_contract_company(
    company: CurveCompanyInputV1,
    contract: MultipleContractV9,
) -> list[str]:
    reasons: list[str] = []
    if isinstance(contract, BroadMedianPriorContractV1):
        if company.mapping_status != MappingStatus.UNAVAILABLE:
            reasons.append("broad_prior_requires_unavailable_exact_mapping")
    else:
        if company.mapping_status != MappingStatus.REVIEWED:
            reasons.append("mapped_or_observed_contract_requires_reviewed_mapping")
        if company.business_type_id != contract.business_type_id:
            reasons.append("business_type_contract_mismatch")
        if company.mapping_version != contract.mapping_version:
            reasons.append("mapping_version_contract_mismatch")
    if isinstance(contract, BenchmarkContractV2) and company.country_code != contract.country_code:
        reasons.append("observed_contract_country_mismatch")
    return reasons


def _contract_time_reasons(
    *,
    company: CurveCompanyInputV1,
    contracts: tuple[MultipleContractV9, ...],
    valuation_as_of: date,
) -> tuple[list[str], str | None, int | None]:
    pack = country_pack(company.country_code)
    if pack is None:
        return ["unsupported_country_pack"], None, None
    reasons: list[str] = []
    if valuation_as_of < pack.effective_from or (
        pack.effective_to is not None and valuation_as_of > pack.effective_to
    ):
        reasons.append("country_pack_not_effective_at_valuation_date")
    if company.currency != pack.currency:
        reasons.append("country_pack_currency_requires_governed_fx")
    for contract in contracts:
        if contract.frozen_at.date() > contract.effective_date:
            reasons.append("contract_frozen_after_effective_date")
        if contract.frozen_at.date() > valuation_as_of:
            reasons.append("contract_frozen_after_valuation_date")
        if contract.effective_date > valuation_as_of:
            reasons.append("contract_effective_date_is_future")
        elif (valuation_as_of - contract.effective_date).days > pack.benchmark_freshness_days:
            reasons.append("contract_effective_date_is_stale")
        if isinstance(contract, BenchmarkContractV2):
            if contract.observation_window_end > valuation_as_of:
                reasons.append("observed_benchmark_window_is_future")
            elif (
                valuation_as_of - contract.observation_window_end
            ).days > pack.benchmark_freshness_days:
                reasons.append("observed_benchmark_window_is_stale")
    return reasons, pack.pack_version, pack.benchmark_freshness_days


def _contract_freshness_decisions(
    contracts: tuple[MultipleContractV9, ...],
    *,
    valuation_as_of: date,
    freshness_limit_days: int,
) -> tuple[ContractFreshnessDecisionV1, ...]:
    return tuple(
        ContractFreshnessDecisionV1(
            contract_id=contract.contract_id,
            source_kind=contract.source_kind,
            effective_date=contract.effective_date,
            frozen_at=contract.frozen_at,
            age_days=(valuation_as_of - contract.effective_date).days,
            freshness_limit_days=freshness_limit_days,
            sample_size=(
                len(contract.observations) if isinstance(contract, BenchmarkContractV2) else None
            ),
            observation_window_start=(
                contract.observation_window_start
                if isinstance(contract, BenchmarkContractV2)
                else None
            ),
            observation_window_end=(
                contract.observation_window_end
                if isinstance(contract, BenchmarkContractV2)
                else None
            ),
        )
        for contract in sorted(contracts, key=lambda item: item.contract_id)
    )


def run_public_curve(
    *,
    campaign_request_id: str,
    company: CurveCompanyInputV1,
    contracts: tuple[MultipleContractV9, ...],
    valuation_as_of: date,
    model_version: str = MODEL_VERSION,
) -> PublicCurveResultV1 | PublicCurveBlockedV1:
    """Run one immutable, source-bound public curve without external requests."""
    if not contracts:
        raise ValueError("at least one frozen multiple contract is required")
    manifest_hashes = {contract.multiple_manifest_sha256 for contract in contracts}
    if len(manifest_hashes) != 1:
        raise ValueError("all company contracts must bind one frozen multiple manifest")
    manifest_sha256 = next(iter(manifest_hashes))
    input_payload = {
        "model_version": model_version,
        "valuation_as_of": valuation_as_of,
        "company": company.model_dump(mode="json"),
        "contracts": [
            contract.model_dump(mode="json")
            for contract in sorted(contracts, key=lambda item: item.contract_id)
        ],
    }
    input_fingerprint = _sha256(input_payload)
    contract_reasons = [
        reason for contract in contracts for reason in _validate_contract_company(company, contract)
    ]
    time_reasons, country_pack_version, freshness_limit_days = _contract_time_reasons(
        company=company,
        contracts=contracts,
        valuation_as_of=valuation_as_of,
    )
    contract_reasons.extend(time_reasons)
    source_kinds = {contract.source_kind for contract in contracts}
    if len(source_kinds) != 1:
        contract_reasons.append("modeled_and_observed_contracts_cannot_be_mixed")
    # Current campaign contract v9 grades one company against one source scope.
    # Multiple metric contracts are permitted only when their grade-driving
    # mapping/source identity is identical.
    anchor = contracts[0]
    if any(type(contract) is not type(anchor) for contract in contracts):
        contract_reasons.append("multiple_contract_kinds_cannot_be_mixed")
    if any(_multiple_scope(contract) != _multiple_scope(anchor) for contract in contracts):
        contract_reasons.append("contract_multiple_scope_set_mismatch")
    if isinstance(anchor, (ModelPriorContractV1, BenchmarkContractV2)) and any(
        getattr(contract, "business_type_id", None) != anchor.business_type_id
        for contract in contracts
    ):
        contract_reasons.append("contract_business_type_set_mismatch")
    if company.blocking_value_contradictions:
        contract_reasons.append("blocking_value_contradiction")

    period_points: list[CurvePointV1] = []
    method_reasons: list[str] = []
    for period in sorted(
        company.periods, key=lambda item: (item.period_end, item.source_record_id)
    ):
        methods, reasons = _build_period_methods(company, period, contracts)
        method_reasons.extend(f"{period.period_end.isoformat()}:{reason}" for reason in reasons)
        if methods:
            period_points.append(_point(period, methods, "pending"))
    period_points = _segments(period_points)

    segment_checkpoint_counts = Counter(point.segment_id for point in period_points)
    if any(count < 2 for count in segment_checkpoint_counts.values()):
        contract_reasons.append("method_segment_has_fewer_than_two_checkpoints")

    method_checkpoint_counts: dict[tuple[ValueBasis, MultipleMetric], int] = defaultdict(int)
    for point in period_points:
        for method in point.methods:
            method_checkpoint_counts[(point.output_basis, method.method)] += 1
    if len(period_points) < 2:
        contract_reasons.append("fewer_than_two_resolved_official_checkpoints")
    if not any(count >= 2 for count in method_checkpoint_counts.values()):
        contract_reasons.append("no_method_resolves_consistently_for_two_periods")
    if len({point.output_basis for point in period_points}) > 1:
        contract_reasons.append("enterprise_and_equity_basis_changes_across_curve")
    if isinstance(anchor, BenchmarkContractV2):
        contract_reasons.extend(
            _common_t3_base_reasons(
                company,
                period_points,
                minimum_resolved_periods=2,
            )
        )
    if contract_reasons:
        return PublicCurveBlockedV1(
            company_key=company.company_key,
            input_fingerprint=input_fingerprint,
            multiple_manifest_sha256=manifest_sha256,
            valuation_as_of=valuation_as_of,
            country_pack_version=country_pack_version,
            official_period_count=len(company.periods),
            resolved_checkpoint_count=len(period_points),
            reason_codes=tuple(dict.fromkeys([*contract_reasons, *method_reasons])),
        )

    grade = _grade(company, anchor, period_points)
    if country_pack_version is None or freshness_limit_days is None:
        raise ValueError("available public curves require an effective country pack")
    contract_freshness = _contract_freshness_decisions(
        contracts,
        valuation_as_of=valuation_as_of,
        freshness_limit_days=freshness_limit_days,
    )
    source_kind = anchor.source_kind
    prior_weight = anchor.prior_weight
    method_set = tuple(
        sorted(
            {method.method for point in period_points for method in point.methods},
            key=lambda value: value.value,
        )
    )
    output_basis = period_points[0].output_basis
    material_content_hash = _sha256(
        {
            "company_key": company.company_key,
            "grade": grade.value,
            "label": CURRENT_MODEL_HISTORICAL_LABEL,
            "points": [point.model_dump(mode="json") for point in period_points],
        }
    )
    result_hash_payload = {
        "schema_version": "PublicCurveResultV1",
        "company_key": company.company_key,
        "tier": "T3" if grade in {ValuationGrade.T3_M, ValuationGrade.T3_O} else "T2",
        "valuation_grade": grade.value,
        "curve_status": "available",
        "curve_temporality": "CURRENT_MODEL_APPLIED_TO_HISTORICAL_OFFICIAL_FINANCIALS",
        "disclosure_label": CURRENT_MODEL_HISTORICAL_LABEL,
        "mapping_status": company.mapping_status.value.lower(),
        "mapping_version": company.mapping_version,
        "multiple_scope": _multiple_scope(anchor),
        "multiple_source_kind": _PUBLIC_SOURCE_KIND[source_kind],
        "multiple_manifest_sha256": manifest_sha256,
        "valuation_as_of": valuation_as_of,
        "country_pack_schema_version": COUNTRY_PACK_SCHEMA_VERSION,
        "country_pack_version": country_pack_version,
        "contract_freshness": [row.model_dump(mode="json") for row in contract_freshness],
        "prior_weight": prior_weight,
        "official_period_count": len(company.periods),
        "resolved_checkpoint_count": len(period_points),
        "method_set": [method.value for method in method_set],
        "output_basis": output_basis.value,
        "input_fingerprint": input_fingerprint,
        "model_version": model_version,
        "material_content_hash": material_content_hash,
        "index_decision": "index",
        "rollout_state": "sealed_dark",
        "reason_codes": (
            ["exact_industry_mapping_unavailable_broad_prior_used"]
            if grade == ValuationGrade.T2_B
            else []
        ),
        "points": [point.model_dump(mode="json") for point in period_points],
    }
    result_sha256 = _sha256(result_hash_payload)
    calculation_idempotency_key = ":".join(
        (company.company_key, model_version, input_fingerprint, manifest_sha256)
    )
    return PublicCurveResultV1(
        company_key=company.company_key,
        tier="T3" if grade in {ValuationGrade.T3_M, ValuationGrade.T3_O} else "T2",
        valuation_grade=grade,
        curve_status="available",
        curve_temporality="CURRENT_MODEL_APPLIED_TO_HISTORICAL_OFFICIAL_FINANCIALS",
        disclosure_label=CURRENT_MODEL_HISTORICAL_LABEL,
        mapping_status=company.mapping_status.value.lower(),
        mapping_version=company.mapping_version,
        multiple_scope=_multiple_scope(anchor),
        multiple_source_kind=_PUBLIC_SOURCE_KIND[source_kind],
        multiple_manifest_sha256=manifest_sha256,
        valuation_as_of=valuation_as_of,
        country_pack_schema_version=COUNTRY_PACK_SCHEMA_VERSION,
        country_pack_version=country_pack_version,
        contract_freshness=contract_freshness,
        prior_weight=prior_weight,
        official_period_count=len(company.periods),
        resolved_checkpoint_count=len(period_points),
        method_set=method_set,
        output_basis=output_basis.value.lower(),
        input_fingerprint=input_fingerprint,
        model_version=model_version,
        result_sha256=result_sha256,
        calculation_idempotency_key=calculation_idempotency_key,
        import_idempotency_key=f"{campaign_request_id}:{result_sha256}",
        material_content_hash=material_content_hash,
        index_decision="index",
        rollout_state="sealed_dark",
        reason_codes=(
            ("exact_industry_mapping_unavailable_broad_prior_used",)
            if grade == ValuationGrade.T2_B
            else ()
        ),
        points=tuple(period_points),
    )


__all__ = [
    "CURRENT_MODEL_HISTORICAL_LABEL",
    "MODEL_VERSION",
    "PUBLICATION_GRADE_PERIOD_FLOORS",
    "CurvePointV1",
    "EligibleMethodV1",
    "PublicCurveBlockedV1",
    "PublicCurveResultV1",
    "run_public_curve",
    "to_public_seal_v9",
]
