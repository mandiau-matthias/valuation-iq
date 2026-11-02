"""Fail-closed certification evaluation for methods in one sealed run.

The method profile registry describes what a method needs.  It is not itself
proof that a calculation met those requirements.  This module evaluates the
actual run material and emits deterministic, reportable failures.  Unknown or
unverifiable evidence is a failure; registry membership never becomes a
certification shortcut.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Callable

from src.domain.method_certification_profiles import (
    METHOD_CERTIFICATION_PROFILE_VERSION,
    method_certification_profile,
)
from src.domain.method_keys import normalize_method_key

JsonMap = dict[str, object]

_MARKET_METRICS: Mapping[str, tuple[str, ...]] = {
    "ebitda_multiple": ("ev_ebitda", "ev_ebitda_multiple", "ebitda_multiple"),
    "omzet_multiple": ("ev_revenue", "ev_revenue_multiple", "revenue_multiple"),
    "arr_multiple": ("arr", "arr_multiple"),
    "sde_multiple": ("sde", "sde_multiple"),
    "real_estate_yield": ("real_estate_yield", "property_yield", "cap_rate"),
}
_APPROVED_REVIEW_STATES = frozenset(
    {"approved", "published_approved", "approved_manual_expert_selection"}
)


@dataclass(frozen=True)
class MethodCertificationEvaluation:
    method_key: str
    weight: Decimal
    profile_version: str | None
    country_code: str
    eligible: bool
    evidence_checks: Mapping[str, bool]
    invariant_checks: Mapping[str, bool]
    review_checks: Mapping[str, bool]
    failures: tuple[str, ...]

    def as_dict(self) -> JsonMap:
        return {
            "method_key": self.method_key,
            "weight": format(self.weight, "f"),
            "profile_version": self.profile_version,
            "country_code": self.country_code,
            "eligible": self.eligible,
            "evidence_checks": dict(self.evidence_checks),
            "invariant_checks": dict(self.invariant_checks),
            "review_checks": dict(self.review_checks),
            "failures": list(self.failures),
        }


def evaluate_run_method_certification(run: Mapping[str, object]) -> list[JsonMap]:
    """Evaluate every positive-weight run method against its exact profile."""

    country_code = str(run.get("country_code") or "").strip().upper()
    lens_date = _date(run.get("valuation_lens_date"))
    mix, mix_failures = _positive_method_mix(run.get("method_mix"))
    weight_sum = sum((weight for _, weight, _ in mix), Decimal("0"))
    duplicate_keys = _duplicates([key for key, _, _ in mix])

    evaluations: list[MethodCertificationEvaluation] = []
    for method_key, weight, declared_eligible in mix:
        failures: list[str] = list(mix_failures)
        profile = method_certification_profile(method_key)
        if profile is None:
            failures.append("profile_missing")
            evaluations.append(
                _evaluation(
                    method_key=method_key,
                    weight=weight,
                    country_code=country_code,
                    profile_version=None,
                    evidence_checks={},
                    invariant_checks={"eligible_weights_sum_to_one": weight_sum == 1},
                    review_checks={"profile_review_accepted": False},
                    failures=failures,
                )
            )
            continue

        if lens_date is None:
            failures.append("valuation_lens_date_invalid")
        elif not profile.supports(country_code, lens_date):
            failures.append("country_or_effective_date_unsupported")
        if profile.implementation_state != "canonical_runtime":
            failures.append("canonical_runtime_not_implemented")
        if method_key == "dcf" and not _dcf_country_regime_resolved(run):
            failures.append("country_tax_regime_unresolved")
        if not declared_eligible:
            failures.append("positive_weight_method_declared_ineligible")
        if method_key in duplicate_keys:
            failures.append("duplicate_method_mix_key")
        if weight_sum != Decimal("1"):
            failures.append("eligible_weights_do_not_total_exactly_one")

        result = _method_result(run, method_key)
        if result is None:
            failures.append("priced_method_result_missing")
        elif result.get("available") is not True or result.get("value") is None:
            failures.append("priced_method_result_unavailable")

        evidence_checks = {
            evidence: _evidence_check(evidence, method_key, run, result)
            for evidence in profile.required_evidence
        }
        invariant_checks = {
            invariant: _invariant_check(
                invariant,
                method_key,
                run,
                result,
                weight_sum=weight_sum,
            )
            for invariant in profile.required_invariants
        }
        review_checks = {
            "profile_review_accepted": _profile_review_accepted(run),
        }
        failures.extend(
            f"evidence:{name}" for name, passed in evidence_checks.items() if not passed
        )
        failures.extend(
            f"invariant:{name}" for name, passed in invariant_checks.items() if not passed
        )
        failures.extend(f"review:{name}" for name, passed in review_checks.items() if not passed)
        evaluations.append(
            _evaluation(
                method_key=profile.method_key,
                weight=weight,
                country_code=country_code,
                profile_version=METHOD_CERTIFICATION_PROFILE_VERSION,
                evidence_checks=evidence_checks,
                invariant_checks=invariant_checks,
                review_checks=review_checks,
                failures=failures,
            )
        )
    return [evaluation.as_dict() for evaluation in evaluations]


def _evaluation(
    *,
    method_key: str,
    weight: Decimal,
    country_code: str,
    profile_version: str | None,
    evidence_checks: Mapping[str, bool],
    invariant_checks: Mapping[str, bool],
    review_checks: Mapping[str, bool],
    failures: Sequence[str],
) -> MethodCertificationEvaluation:
    unique_failures = tuple(dict.fromkeys(failures))
    return MethodCertificationEvaluation(
        method_key=method_key,
        weight=weight,
        profile_version=profile_version,
        country_code=country_code,
        eligible=not unique_failures,
        evidence_checks=evidence_checks,
        invariant_checks=invariant_checks,
        review_checks=review_checks,
        failures=unique_failures,
    )


def _positive_method_mix(
    value: object,
) -> tuple[list[tuple[str, Decimal, bool]], tuple[str, ...]]:
    if not _sequence(value):
        return [], ("method_mix_missing_or_invalid",)
    rows: list[tuple[str, Decimal, bool]] = []
    failures: list[str] = []
    for raw in value:
        if not isinstance(raw, Mapping):
            failures.append("method_mix_row_invalid")
            continue
        weight = _decimal(raw.get("weight"))
        if weight is None or weight < 0:
            failures.append("method_mix_weight_invalid")
            continue
        if weight == 0:
            continue
        rows.append(
            (
                normalize_method_key(raw.get("method_key")),
                weight,
                raw.get("eligible") is not False,
            )
        )
    if not rows:
        failures.append("positive_weight_method_missing")
    return rows, tuple(dict.fromkeys(failures))


def _duplicates(values: Sequence[str]) -> set[str]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for value in values:
        if value in seen:
            duplicates.add(value)
        seen.add(value)
    return duplicates


def _profile_review_accepted(run: Mapping[str, object]) -> bool:
    review_scope_hash = str(run.get("review_scope_hash") or "").strip().lower()
    if len(review_scope_hash) != 64:
        return False
    for raw in _list(run.get("report_review_decisions")):
        decision = _mapping(raw)
        if not (
            decision.get("schema_version") == "report_review_decision.v1"
            and decision.get("scope") == "valuation_calculation"
            and str(decision.get("decision") or "").lower() == "accepted"
            and str(decision.get("scope_id") or "").strip().lower()
            == review_scope_hash
            and decision.get("decision_id")
            and decision.get("reviewer_id")
            and decision.get("reviewer_role")
            in {"advisor", "senior_advisor", "compliance_reviewer"}
            and decision.get("source_kind")
            in {"advisor_review_record", "compliance_review_record"}
            and decision.get("source_id")
            and _valid_sha256(decision.get("source_hash"))
            and _timezone_aware_datetime(decision.get("decided_at"))
        ):
            continue
        return True
    return False


def _dcf_country_regime_resolved(run: Mapping[str, object]) -> bool:
    country_code = str(run.get("country_code") or "").strip().upper()
    if country_code != "IE":
        return True
    dcf = _mapping(run.get("dcf_results"))
    lineage = _mapping(run.get("calculation_lineage"))
    regime = (
        str(
            dcf.get("irish_tax_regime")
            or dcf.get("country_tax_regime")
            or lineage.get("irish_tax_regime")
            or lineage.get("country_tax_regime")
            or ""
        )
        .strip()
        .lower()
    )
    return regime in {"trading", "non_trading", "pillar_two"}


def _dcf_input_mode(run: Mapping[str, object]) -> str:
    dcf = _mapping(run.get("dcf_results"))
    lineage = _mapping(run.get("calculation_lineage"))
    return str(dcf.get("dcf_input_mode") or lineage.get("dcf_input_mode") or "").strip()


def _method_result(run: Mapping[str, object], method_key: str) -> JsonMap | None:
    results = _mapping(run.get("method_results"))
    candidates = (
        (method_key, "revenue_multiple") if method_key == "omzet_multiple" else (method_key,)
    )
    for key in candidates:
        result = _mapping(results.get(key))
        if result:
            stamped = normalize_method_key(result.get("method_key") or key)
            if stamped == method_key:
                return result
    return None


def _evidence_check(
    evidence: str,
    method_key: str,
    run: Mapping[str, object],
    result: JsonMap | None,
) -> bool:
    check = _EVIDENCE_CHECKS.get(evidence)
    return bool(check and check(method_key, run, result))


def _invariant_check(
    invariant: str,
    method_key: str,
    run: Mapping[str, object],
    result: JsonMap | None,
    *,
    weight_sum: Decimal,
) -> bool:
    if invariant == "eligible_weights_sum_to_one":
        return weight_sum == Decimal("1")
    check = _INVARIANT_CHECKS.get(invariant)
    return bool(check and check(method_key, run, result))


def _benchmark_complete(
    method_key: str, run: Mapping[str, object], _result: JsonMap | None
) -> bool:
    aliases = {alias.lower() for alias in _MARKET_METRICS.get(method_key, ())}
    if not aliases:
        return False
    references = [
        row
        for raw in _list(run.get("benchmark_snapshot_references"))
        if (row := _mapping(raw)) and str(row.get("metric") or "").strip().lower() in aliases
    ]
    if not references:
        return False
    snapshot = _mapping(run.get("benchmark_snapshot"))
    materials = _benchmark_materials(snapshot)
    citations = [_mapping(raw) for raw in _list(run.get("source_citations"))]
    run_country = str(run.get("country_code") or "").strip().upper()
    lens_date = _date(run.get("valuation_lens_date"))
    from src.config.country_packs import country_pack

    pack = country_pack(run_country)
    if lens_date is None or pack is None:
        return False
    for reference in references:
        metric = str(reference.get("metric") or "").strip().lower()
        material = next(
            (
                row
                for row in materials
                if str(row.get("metric_name") or row.get("metric") or "").strip().lower() in aliases
            ),
            {},
        )
        evidence_window = _mapping(reference.get("evidence_window")) or _mapping(
            material.get("evidence_window")
        )
        material_country = (
            str(
                material.get("target_country_code")
                or material.get("country_code")
                or snapshot.get("target_country_code")
                or snapshot.get("country_code")
                or ""
            )
            .strip()
            .upper()
        )
        if not run_country or material_country != run_country:
            return False
        borrowed_country = str(reference.get("borrowed_from_country") or "").strip().upper()
        if borrowed_country and borrowed_country != run_country:
            return False
        sample_size = _integer(material.get("sample_size"))
        if sample_size is None or sample_size <= 0:
            return False
        if not (
            reference.get("benchmark_id")
            and _valid_sha256(reference.get("snapshot_hash"))
            and reference.get("resolution_contract_id")
            and _valid_sha256(reference.get("resolution_contract_hash"))
            and (
                reference.get("dataset_version_id")
                or reference.get("source_dataset_version_id")
            )
        ):
            return False
        if str(reference.get("review_state") or "").strip().lower() not in (
            _APPROVED_REVIEW_STATES
        ):
            return False
        if str(evidence_window.get("freshness") or "").strip().lower() != "current":
            return False
        observed_at = _date(
            evidence_window.get("evidence_as_of")
            or evidence_window.get("observed_at")
            or reference.get("published_at")
        )
        if (
            observed_at is None
            or observed_at > lens_date
            or (lens_date - observed_at).days > pack.benchmark_freshness_days
        ):
            return False
        if not (
            material.get("methodology_version")
            or snapshot.get("methodology_version")
            or snapshot.get("methodology")
        ):
            return False
        matching_citations = [
            citation
            for citation in citations
            if _citation_matches_metric(citation, metric, len(references))
        ]
        if not matching_citations or not any(
            _complete_citation(row) and _citation_on_or_before_lens(row, run)
            for row in matching_citations
        ):
            return False
    return True


def _citation_matches_metric(citation: JsonMap, metric: str, reference_count: int) -> bool:
    use = str(citation.get("use") or "").strip().lower()
    return use == f"priced_benchmark_metric:{metric}" or (
        reference_count == 1 and use == "priced_benchmark_metric"
    )


def _complete_citation(citation: JsonMap) -> bool:
    return bool(
        citation.get("provider")
        and (citation.get("source_id") or citation.get("citation_id"))
        and (citation.get("document_hash") or citation.get("locator") or citation.get("url"))
        and (citation.get("observed_at") or citation.get("published_at"))
    )


def _benchmark_materials(value: object) -> list[JsonMap]:
    snapshot = _mapping(value)
    metrics = _mapping(snapshot.get("metrics"))
    rows = [_mapping(raw) for raw in metrics.values()]
    resolutions = [_mapping(raw) for raw in _list(snapshot.get("resolutions"))]
    return [row for row in (*rows, *resolutions) if row]


def _earnings_basis(run: Mapping[str, object]) -> JsonMap:
    ledger = _mapping(run.get("driver_ledger"))
    layers = _mapping(ledger.get("layers"))
    operating = _mapping(layers.get("operating_normalizations"))
    return _mapping(operating.get("earnings_basis"))


def _normalized_annual_ebitda(
    _method_key: str, run: Mapping[str, object], _result: JsonMap | None
) -> bool:
    basis = _earnings_basis(run)
    rows = [_mapping(raw) for raw in _list(basis.get("rows"))]
    if not rows or _decimal(basis.get("normalized_ebitda")) is None:
        return False
    weights = [_decimal(row.get("weight")) for row in rows]
    if any(weight is None or weight < 0 for weight in weights):
        return False
    if sum((weight or Decimal("0") for weight in weights), Decimal("0")) != Decimal("1"):
        return False
    calculated = Decimal("0")
    for row, weight in zip(rows, weights):
        normalized = _decimal(row.get("normalized_ebitda"))
        weighted = _decimal(row.get("weighted_normalized_ebitda"))
        if normalized is None or weighted is None or weight is None:
            return False
        expected = normalized * weight
        if weighted != expected:
            return False
        calculated += expected
    return calculated == _decimal(basis.get("normalized_ebitda"))


def _priced_accounting_evidence(
    _method_key: str,
    run: Mapping[str, object],
    _result: JsonMap | None,
) -> bool:
    return bool(
        run.get("uploaded_data_snapshot_status") == "priced"
        and (snapshot := _mapping(run.get("uploaded_data_snapshot"))).get("snapshot_hash")
        and snapshot.get("snapshot_id")
        and snapshot.get("source_kind") == "uploaded_accounting_evidence"
    )


def _financial_metric(name: str) -> Callable[[str, Mapping[str, object], JsonMap | None], bool]:
    def check(_method_key: str, run: Mapping[str, object], _result: JsonMap | None) -> bool:
        return _decimal(_mapping(run.get("financial_metrics")).get(name)) is not None

    return check


def _margin_quality(_method_key: str, run: Mapping[str, object], _result: JsonMap | None) -> bool:
    metrics = _mapping(run.get("financial_metrics"))
    revenue = _decimal(metrics.get("revenue"))
    ebitda = _decimal(metrics.get("ebitda"))
    return revenue is not None and revenue > 0 and ebitda is not None


def _result_detail_present(
    *names: str,
) -> Callable[[str, Mapping[str, object], JsonMap | None], bool]:
    def check(_method_key: str, _run: Mapping[str, object], result: JsonMap | None) -> bool:
        details = _mapping((result or {}).get("details"))
        return all(details.get(name) is not None for name in names)

    return check


def _sde_basis(_method_key: str, run: Mapping[str, object], _result: JsonMap | None) -> bool:
    basis = _mapping(_earnings_basis(run).get("sde_basis"))
    required = (
        "weighted_sde",
        "actual_owner_compensation",
        "replacement_owner_compensation",
    )
    return _priced_accounting_evidence("", run, None) and all(
        _decimal(basis.get(name)) is not None for name in required
    )


def _explicit_fcff(_method_key: str, run: Mapping[str, object], _result: JsonMap | None) -> bool:
    dcf = _mapping(run.get("dcf_results"))
    projections = [_decimal(raw) for raw in _list(dcf.get("fcf_projections_5y"))]
    return bool(
        _dcf_input_mode(run) == "fcff_only"
        and projections
        and all(value is not None for value in projections)
    )


def _economic_snapshot(
    _method_key: str, run: Mapping[str, object], _result: JsonMap | None
) -> bool:
    snapshot = _mapping(run.get("economic_snapshot"))
    country_code = str(run.get("country_code") or "").strip().upper()
    lens_date = _date(run.get("valuation_lens_date"))
    from src.config.country_packs import country_pack

    pack = country_pack(country_code)
    if lens_date is None or pack is None:
        return False
    snapshot_country = str(snapshot.get("country_code") or country_code).strip().upper()
    if snapshot_country != country_code:
        return False
    observed_dates = [
        _date(snapshot.get(field))
        for field in (
            "risk_free_rate_observed_at",
            "equity_risk_premium_observed_at",
            "growth_rates_observed_at",
        )
    ]
    return bool(
        run.get("economic_snapshot_status") == "used_for_dcf"
        and snapshot.get("snapshot_id")
        and _valid_sha256(snapshot.get("snapshot_hash"))
        and snapshot.get("snapshot_issuer")
        and snapshot.get("source_references")
        and all(
            observed is not None
            and observed <= lens_date
            and (lens_date - observed).days <= pack.macro_freshness_days
            for observed in observed_dates
        )
    )


def _wacc(_method_key: str, run: Mapping[str, object], result: JsonMap | None) -> bool:
    value = _decimal(_mapping(run.get("dcf_results")).get("wacc"))
    result_value = _decimal((result or {}).get("wacc"))
    return bool(
        value is not None
        and value > 0
        and result_value is not None
        and result_value.quantize(Decimal("0.0001")) == value.quantize(Decimal("0.0001"))
    )


def _terminal_assumption(
    _method_key: str, run: Mapping[str, object], _result: JsonMap | None
) -> bool:
    dcf = _mapping(run.get("dcf_results"))
    wacc = _decimal(dcf.get("wacc"))
    growth = _decimal(dcf.get("terminal_growth_rate"))
    method = str(dcf.get("terminal_value_methodology") or "").strip().lower()
    if wacc is None or growth is None or method not in {"gordon_growth", "exit_multiple"}:
        return False
    if method == "gordon_growth":
        return wacc > growth
    return (_decimal(dcf.get("terminal_exit_multiple")) or Decimal("0")) > 0


def _forecast_review(_method_key: str, run: Mapping[str, object], _result: JsonMap | None) -> bool:
    accepted = _profile_review_accepted(run)
    source_bound = any(
        str((citation := _mapping(raw)).get("use") or "").startswith("forecast_review")
        and _complete_citation(citation)
        and _citation_on_or_before_lens(citation, run)
        for raw in _list(run.get("source_citations"))
    )
    return accepted and source_bound


def _source_use(prefix: str) -> Callable[[str, Mapping[str, object], JsonMap | None], bool]:
    def check(_method_key: str, run: Mapping[str, object], _result: JsonMap | None) -> bool:
        return any(
            str((citation := _mapping(raw)).get("use") or "").startswith(prefix)
            and _complete_citation(citation)
            and _citation_on_or_before_lens(citation, run)
            for raw in _list(run.get("source_citations"))
        )

    return check


def _holding_rows(_method_key: str, _run: Mapping[str, object], result: JsonMap | None) -> bool:
    details = _mapping((result or {}).get("details"))
    rows = [_mapping(raw) for raw in _list(details.get("entity_rows"))]
    return bool(
        rows
        and all(
            row.get("valuation_run_id")
            and row.get("valuation_run_hash")
            and _decimal(row.get("ownership_pct")) is not None
            and row.get("currency")
            for row in rows
        )
    )


def _holding_eliminations(
    _method_key: str, _run: Mapping[str, object], result: JsonMap | None
) -> bool:
    details = _mapping((result or {}).get("details"))
    return all(
        key in details
        for key in (
            "participation_book_value_elimination",
            "other_equity_value_elimination",
            "operating_eliminations",
        )
    )


def _adaptive_children(_method_key: str, run: Mapping[str, object], result: JsonMap | None) -> bool:
    details = _mapping((result or {}).get("details"))
    weighting = _mapping(details.get("adaptive_weighting"))
    children = [_mapping(raw) for raw in _list(weighting.get("positive_weight_children"))]
    if not children:
        return False
    child_keys = [normalize_method_key(child.get("method_key")) for child in children]
    if len(set(child_keys)) != len(child_keys):
        return False
    lens_date = _date(run.get("valuation_lens_date"))
    country_code = str(run.get("country_code") or "").strip().upper()
    if lens_date is None:
        return False
    for child in children:
        child_key = normalize_method_key(child.get("method_key"))
        child_weight = _decimal(child.get("weight"))
        if child_key == "upswitch_adaptive" or child_weight is None or child_weight <= 0:
            return False
        child_profile = method_certification_profile(child_key)
        child_result = _method_result(run, child_key)
        if (
            child_profile is None
            or not child_profile.supports(country_code, lens_date)
            or child_result is None
            or child_result.get("available") is not True
            or child_result.get("value") is None
        ):
            return False
        if any(
            not _evidence_check(item, child_key, run, child_result)
            for item in child_profile.required_evidence
        ):
            return False
        if any(
            not _invariant_check(
                item,
                child_key,
                run,
                child_result,
                weight_sum=Decimal("1"),
            )
            for item in child_profile.required_invariants
            if item != "eligible_weights_sum_to_one"
        ):
            return False
    if sum(
        (_decimal(child.get("weight")) or Decimal("0") for child in children),
        Decimal("0"),
    ) != Decimal("1"):
        return False

    dcf_weight = _decimal(weighting.get("dcf_weight"))
    if dcf_weight is not None:
        disclosed = sum(
            (
                _decimal(child.get("weight")) or Decimal("0")
                for child in children
                if normalize_method_key(child.get("method_key")) == "dcf"
            ),
            Decimal("0"),
        )
        if disclosed != dcf_weight:
            return False
    multiples_weight = _decimal(weighting.get("multiples_weight"))
    if multiples_weight is not None:
        market_weight = sum(
            (
                _decimal(child.get("weight")) or Decimal("0")
                for child in children
                if normalize_method_key(child.get("method_key")) in _MARKET_METRICS
            ),
            Decimal("0"),
        )
        if market_weight != multiples_weight:
            return False
    return True


def _single_ev_equity_bridge(
    _method_key: str, run: Mapping[str, object], result: JsonMap | None
) -> bool:
    if result is None:
        return False
    details = _mapping(result.get("details"))
    enterprise = _first_decimal(result.get("enterprise_value"), details.get("enterprise_value"))
    equity = _first_decimal(result.get("equity_value"), result.get("value"))
    method_bridge = _mapping(details.get("ev_to_equity_bridge"))
    if method_bridge:
        return bool(
            enterprise is not None
            and equity is not None
            and _decimal(method_bridge.get("enterprise_value")) == enterprise
            and _decimal(method_bridge.get("equity_value")) == equity
            and _integer(method_bridge.get("application_count")) == 1
        )

    mix, mix_failures = _positive_method_mix(run.get("method_mix"))
    if mix_failures or len(mix) != 1 or mix[0][0] != _method_key:
        return False
    bridge = _mapping(
        _mapping(
            _mapping(_mapping(run.get("driver_ledger")).get("layers")).get("enterprise_to_equity")
        ).get("bridge")
    )
    return bool(
        enterprise is not None
        and equity is not None
        and bridge.get("applicability") != "not_applicable"
        and _decimal(bridge.get("enterprise_value")) == enterprise
        and _decimal(bridge.get("equity_value")) == equity
    )


def _equity_premise_no_ev(
    _method_key: str, _run: Mapping[str, object], result: JsonMap | None
) -> bool:
    details = _mapping((result or {}).get("details"))
    return bool(
        result is not None
        and result.get("enterprise_value") is None
        and details.get("enterprise_value") is None
        and result.get("value_basis") == "equity_value"
    )


def _range_monotone(result: JsonMap | None) -> bool:
    if result is None:
        return False
    mid = _decimal(result.get("value"))
    low = _decimal(result.get("value_low"))
    high = _decimal(result.get("value_high"))
    if mid is None:
        return False
    return (low is None or low <= mid) and (high is None or mid <= high)


def _normalization_before_weighting(
    _method_key: str, run: Mapping[str, object], _result: JsonMap | None
) -> bool:
    return _normalized_annual_ebitda("", run, None)


def _no_historical_revenue_averaging(
    _method_key: str, run: Mapping[str, object], result: JsonMap | None
) -> bool:
    details = _mapping((result or {}).get("details"))
    return _decimal(details.get("revenue")) == _decimal(
        _mapping(run.get("financial_metrics")).get("revenue")
    )


def _arr_reconciled(_method_key: str, run: Mapping[str, object], result: JsonMap | None) -> bool:
    details = _mapping((result or {}).get("details"))
    arr = _decimal(details.get("arr"))
    revenue = _decimal(_mapping(run.get("financial_metrics")).get("revenue"))
    eligibility = _mapping(details.get("eligibility"))
    return bool(
        arr is not None
        and arr > 0
        and (revenue is None or arr <= revenue)
        and eligibility.get("eligible") is True
    )


def _sde_weighted_once(_method_key: str, run: Mapping[str, object], result: JsonMap | None) -> bool:
    basis = _mapping(_earnings_basis(run).get("sde_basis"))
    details = _mapping((result or {}).get("details"))
    weighted_sde = _decimal(basis.get("weighted_sde"))
    return weighted_sde is not None and weighted_sde == _decimal(details.get("sde"))


def _no_fabricated_owner_comp(
    _method_key: str, run: Mapping[str, object], _result: JsonMap | None
) -> bool:
    return _sde_basis("", run, None)


def _fcff_only(_method_key: str, run: Mapping[str, object], _result: JsonMap | None) -> bool:
    return _explicit_fcff("", run, None)


def _terminal_consistent(
    _method_key: str, run: Mapping[str, object], _result: JsonMap | None
) -> bool:
    return _terminal_assumption("", run, None)


def _measurement_date_basis(
    _method_key: str, run: Mapping[str, object], _result: JsonMap | None
) -> bool:
    source_as_of = _date(run.get("source_as_of"))
    lens_date = _date(run.get("valuation_lens_date"))
    return bool(source_as_of and lens_date and source_as_of <= lens_date)


def _property_income_exactly_once(
    _method_key: str, _run: Mapping[str, object], result: JsonMap | None
) -> bool:
    details = _mapping((result or {}).get("details"))
    noi = _decimal(details.get("net_operating_income"))
    cap_low = _decimal(details.get("cap_rate_low"))
    cap_mid = _decimal(details.get("cap_rate_mid"))
    cap_high = _decimal(details.get("cap_rate_high"))
    ev_low = _decimal(details.get("enterprise_value_low"))
    ev_mid = _decimal(details.get("enterprise_value_mid"))
    ev_high = _decimal(details.get("enterprise_value_high"))
    if (
        noi is None
        or noi <= 0
        or cap_low is None
        or cap_mid is None
        or cap_high is None
        or not Decimal("0") < cap_low <= cap_mid <= cap_high < Decimal("1")
        or not _valid_sha256(details.get("evidence_contract_hash"))
    ):
        return False
    expected = (noi / cap_high, noi / cap_mid, noi / cap_low)
    actual = (ev_low, ev_mid, ev_high)
    return all(
        value is not None and abs(value - target) <= Decimal("0.01")
        for value, target in zip(actual, expected)
    )


def _single_property_debt_bridge(
    _method_key: str, _run: Mapping[str, object], result: JsonMap | None
) -> bool:
    if result is None:
        return False
    details = _mapping(result.get("details"))
    bridge = _mapping(details.get("ev_to_equity_bridge"))
    ev = _decimal(result.get("enterprise_value"))
    equity = _decimal(result.get("equity_value") or result.get("value"))
    debt = _decimal(bridge.get("property_debt"))
    cash = _decimal(bridge.get("unrestricted_cash"))
    nwc = _decimal(bridge.get("normalized_nwc_adjustment"))
    pre_floor = _decimal(bridge.get("full_company_equity_before_nav_floor"))
    post_floor = _decimal(bridge.get("full_company_equity_after_nav_floor"))
    ownership = _decimal(bridge.get("ownership_multiplier"))
    return bool(
        _integer(bridge.get("application_count")) == 1
        and bridge.get("basis")
        == "full_company_enterprise_value_to_full_company_equity_then_ownership"
        and ev is not None
        and equity is not None
        and debt is not None
        and cash is not None
        and nwc is not None
        and pre_floor is not None
        and post_floor is not None
        and ownership is not None
        and Decimal("0") <= ownership <= Decimal("1")
        and abs(pre_floor - (ev - debt + cash + nwc)) <= Decimal("0.01")
        and abs(equity - post_floor * ownership) <= Decimal("0.01")
        and _decimal(bridge.get("enterprise_value")) == ev
        and _decimal(bridge.get("equity_value")) == equity
        and bridge.get("reconciles") is True
    )


def _nav_floor_like_for_like(
    _method_key: str, _run: Mapping[str, object], result: JsonMap | None
) -> bool:
    details = _mapping((result or {}).get("details"))
    bridge = _mapping(details.get("ev_to_equity_bridge"))
    floor = _decimal(bridge.get("governed_nav_equity_floor"))
    pre_floor = _decimal(bridge.get("full_company_equity_before_nav_floor"))
    post_floor = _decimal(bridge.get("full_company_equity_after_nav_floor"))
    if pre_floor is None or post_floor is None:
        return False
    if floor is None:
        return (
            details.get("nav_floor_basis") is None
            and details.get("nav_floor_applied") is False
            and post_floor == pre_floor
        )
    return bool(
        details.get("nav_floor_basis") == "adjusted_equity_value"
        and floor >= 0
        and post_floor == max(pre_floor, floor)
    )


def _holding_no_bridge_replay(
    _method_key: str, _run: Mapping[str, object], result: JsonMap | None
) -> bool:
    details = _mapping((result or {}).get("details"))
    return details.get("calculation_authority") == "valuation_iq" and not details.get(
        "child_bridge_replayed"
    )


def _startup_dilution(_method_key: str, _run: Mapping[str, object], result: JsonMap | None) -> bool:
    details = _mapping((result or {}).get("details"))
    cap_table = _mapping(details.get("cap_table_simulator"))
    return bool(cap_table and cap_table.get("reconciled") is True)


def _fiscal_reference_label(
    method_key: str, run: Mapping[str, object], result: JsonMap | None
) -> bool:
    return bool(
        method_key == "fiscal_4x"
        and str(run.get("country_code") or "").upper() == "BE"
        and _decimal((result or {}).get("multiple_used")) == Decimal("4")
        and "refer" in str((result or {}).get("label") or "").lower()
    )


def _jurisdiction_priority(
    _method_key: str, run: Mapping[str, object], result: JsonMap | None
) -> bool:
    details = _mapping((result or {}).get("details"))
    country = str(run.get("country_code") or "").upper()
    orderly = _mapping(details.get("priority_cascade_orderly"))
    forced = _mapping(details.get("priority_cascade_forced"))
    tax_orderly = _mapping(details.get("tax_leakage_orderly"))
    tax_forced = _mapping(details.get("tax_leakage_forced"))
    return bool(
        country == "BE"
        and orderly.get("jurisdiction") == country
        and forced.get("jurisdiction") == country
        and tax_orderly.get("jurisdiction") == country
        and tax_forced.get("jurisdiction") == country
        and details.get("wind_down_orderly")
        and details.get("wind_down_forced")
    )


_EVIDENCE_CHECKS: Mapping[str, Callable[[str, Mapping[str, object], JsonMap | None], bool]] = {
    "every_positive_weight_child_profile": _adaptive_children,
    "normalized_annual_ebitda": _normalized_annual_ebitda,
    "metric_matched_benchmark_snapshot": _benchmark_complete,
    "ltm_or_ntm_revenue": _financial_metric("revenue"),
    "margin_quality": _margin_quality,
    "arr": _result_detail_present("arr"),
    "retention_and_margin_quality": _result_detail_present("saas_metrics", "eligibility"),
    "annual_owner_compensation": _sde_basis,
    "replacement_compensation": _sde_basis,
    "sde_benchmark_snapshot": _benchmark_complete,
    "explicit_fcff_forecast": _explicit_fcff,
    "economic_snapshot": _economic_snapshot,
    "wacc": _wacc,
    "terminal_assumption": _terminal_assumption,
    "forecast_review": _forecast_review,
    "dated_assets": _priced_accounting_evidence,
    "dated_liabilities": _priced_accounting_evidence,
    "appraisals": _source_use("nav_appraisal"),
    "title": _source_use("nav_title"),
    "tax_effects": _source_use("nav_tax"),
    "property_title_or_appraisal": lambda method_key, run, result: (
        _source_use("priced_property_title")(method_key, run, result)
        or _source_use("priced_property_nav_appraisal")(method_key, run, result)
    ),
    "dated_noi": _source_use("priced_property_noi"),
    "occupancy": _source_use("priced_property_occupancy"),
    "yield_snapshot": _benchmark_complete,
    "property_debt": _source_use("priced_property_debt"),
    "trusted_child_runs": _holding_rows,
    "ownership": _holding_rows,
    "eliminations": _holding_eliminations,
    "entity_tax": _source_use("holding_entity_tax"),
    "source_dated_fx": _source_use("holding_fx"),
    "stage": _result_detail_present("stage"),
    "scenarios": _result_detail_present("method_breakdown"),
    "cap_table": _result_detail_present("cap_table_simulator"),
    "dated_startup_benchmarks": _result_detail_present("regional_reference"),
    "belgian_statutory_inputs": _priced_accounting_evidence,
    "realisation_schedule": _result_detail_present("asset_schedule"),
    "claim_priority": _result_detail_present("priority_cascade_orderly", "priority_cascade_forced"),
    "tax_leakage": _result_detail_present("tax_leakage_orderly", "tax_leakage_forced"),
    "wind_down_costs": _result_detail_present("wind_down_orderly", "wind_down_forced"),
}

_INVARIANT_CHECKS: Mapping[str, Callable[[str, Mapping[str, object], JsonMap | None], bool]] = {
    "no_ineligible_child_method": _adaptive_children,
    "normalization_before_weighting": _normalization_before_weighting,
    "single_ev_equity_bridge": _single_ev_equity_bridge,
    "no_historical_revenue_averaging": _no_historical_revenue_averaging,
    "arr_definition_reconciled": _arr_reconciled,
    "annual_sde_weighted_exactly_once": _sde_weighted_once,
    "no_fabricated_owner_compensation": _no_fabricated_owner_comp,
    "fcff_only": _fcff_only,
    "terminal_policy_consistency": _terminal_consistent,
    "measurement_date_basis": _measurement_date_basis,
    "enterprise_value_not_applicable": _equity_premise_no_ev,
    "market_rent_exactly_once": _property_income_exactly_once,
    "single_property_debt_bridge": _single_property_debt_bridge,
    "nav_floor_like_for_like": _nav_floor_like_for_like,
    "intercompany_elimination": _holding_eliminations,
    "minority_ownership": _holding_rows,
    "no_child_bridge_replay": _holding_no_bridge_replay,
    "dilution_reconciled": _startup_dilution,
    "labelled_reference_not_market_value": _fiscal_reference_label,
    "jurisdiction_priority_applied": _jurisdiction_priority,
}


def certification_evaluator_requirement_gaps() -> dict[str, tuple[str, ...]]:
    """Return any profile requirements with no executable evaluator.

    Certification tests pin this to an empty mapping. Keeping the check in the
    production module prevents a newly added registry string from silently
    becoming a truthy, documentation-only requirement.
    """

    from src.domain.method_certification_profiles import METHOD_CERTIFICATION_PROFILES

    gaps: dict[str, tuple[str, ...]] = {}
    for method_key, profile in METHOD_CERTIFICATION_PROFILES.items():
        missing = tuple(
            [
                *(
                    f"evidence:{key}"
                    for key in profile.required_evidence
                    if key not in _EVIDENCE_CHECKS
                ),
                *(
                    f"invariant:{key}"
                    for key in profile.required_invariants
                    if key != "eligible_weights_sum_to_one" and key not in _INVARIANT_CHECKS
                ),
            ]
        )
        if missing:
            gaps[method_key] = missing
    return gaps


def _mapping(value: object) -> JsonMap:
    if isinstance(value, Mapping):
        return dict(value)
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        dumped = model_dump(mode="json")
        return dict(dumped) if isinstance(dumped, Mapping) else {}
    return {}


def _list(value: object) -> list[object]:
    if _sequence(value):
        return list(value)
    return []


def _sequence(value: object) -> bool:
    return isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray))


def _decimal(value: object) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    return parsed if parsed.is_finite() else None


def _first_decimal(*values: object) -> Decimal | None:
    for value in values:
        parsed = _decimal(value)
        if parsed is not None:
            return parsed
    return None


def _integer(value: object) -> int | None:
    try:
        parsed = int(str(value))
    except (TypeError, ValueError):
        return None
    return parsed


def _date(value: object) -> date | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        return date.fromisoformat(raw[:10])
    except (TypeError, ValueError):
        return None


def _citation_on_or_before_lens(
    citation: Mapping[str, object], run: Mapping[str, object]
) -> bool:
    lens_date = _date(run.get("valuation_lens_date"))
    observed_at = _date(citation.get("observed_at") or citation.get("published_at"))
    return bool(lens_date is not None and observed_at is not None and observed_at <= lens_date)


def _valid_sha256(value: object) -> bool:
    """Accept only a complete lowercase/uppercase SHA-256 hex digest."""

    return bool(re.fullmatch(r"[0-9a-fA-F]{64}", str(value or "")))


def _timezone_aware_datetime(value: object) -> bool:
    """Require an ISO-8601 timestamp with an explicit UTC offset."""

    raw = str(value or "").strip()
    if raw.endswith("Z"):
        raw = f"{raw[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(raw)
    except (TypeError, ValueError):
        return False
    return parsed.tzinfo is not None and parsed.utcoffset() is not None
