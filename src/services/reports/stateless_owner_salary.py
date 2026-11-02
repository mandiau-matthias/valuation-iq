"""Owner-salary addback extraction for stateless SDE calculations."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

OWNER_COMPENSATION_ADJUSTMENT_KEYS = {
    "salary",
    "owner_salary",
    "owner_comp",
    "owner_compensation",
    "owner_compensation_adjustment",
}
PRICED_NORMALIZATION_STATUSES = {
    "accepted",
    "approved",
    "applied",
    "confirmed",
    "edited",
    "verified",
}


def extract_owner_salary_addback(
    *,
    explicit_owner_salary_addback: float | None,
    normalization_metadata: object,
) -> float | None:
    """Resolve replacement compensation from a governed normalization row.

    The legacy scalar has no evidence or reviewer identity. It remains accepted
    for transport compatibility but is scenario-only and cannot activate SDE.
    """
    del explicit_owner_salary_addback

    for adjustment in _owner_compensation_adjustments(normalization_metadata):
        terms = _owner_compensation_terms(adjustment)
        if terms is not None:
            _, replacement_compensation = terms
            return float(replacement_compensation)

    return None


def build_weighted_sde_basis(earnings_basis: object) -> dict[str, object]:
    """Build SDE from each governed annual row before historical weighting.

    Owner-compensation normalization converts actual pay to market replacement
    pay: ``normalization_delta = actual - replacement``. Normalized EBITDA
    therefore already includes the delta. SDE adds the replacement amount to
    normalized EBITDA, which is exactly equivalent to reported EBITDA plus the
    actual gross compensation. Both amounts must be explicit and reconcile.
    """

    if not isinstance(earnings_basis, dict):
        return _empty_weighted_sde_basis()
    raw_rows = earnings_basis.get("rows")
    if not isinstance(raw_rows, list):
        return _empty_weighted_sde_basis()

    weighted_base = Decimal("0")
    weighted_replacement = Decimal("0")
    weighted_actual = Decimal("0")
    weighted_sde = Decimal("0")
    annual_rows: list[dict[str, object]] = []
    has_governed_compensation = False
    missing_compensation_years: list[int] = []
    for raw_row in raw_rows:
        if not isinstance(raw_row, dict):
            continue
        weight = _decimal_or_zero(raw_row.get("weight"))
        normalized = _decimal_or_zero(raw_row.get("normalized_ebitda"))
        adjustments = raw_row.get("applied_adjustments")
        owner_normalization = Decimal("0")
        actual_compensation = Decimal("0")
        replacement_compensation = Decimal("0")
        evidence_ids: list[str] = []
        if isinstance(adjustments, list):
            for raw_adjustment in adjustments:
                if not isinstance(raw_adjustment, dict):
                    continue
                if not _is_owner_compensation_adjustment(raw_adjustment):
                    continue
                if not _normalization_is_priced(raw_adjustment):
                    continue
                owner_normalization += _decimal_or_zero(raw_adjustment.get("signed_amount"))
                terms = _owner_compensation_terms(raw_adjustment)
                if terms is None:
                    continue
                actual, replacement = terms
                actual_compensation += actual
                replacement_compensation += replacement
                evidence_id = str(raw_adjustment.get("evidence_id") or "").strip()
                if evidence_id:
                    evidence_ids.append(evidence_id)
                has_governed_compensation = True

        base_ebitda = normalized
        annual_sde = base_ebitda + replacement_compensation
        fiscal_year = raw_row.get("fiscal_year")
        if weight > 0 and actual_compensation <= 0:
            try:
                missing_compensation_years.append(int(fiscal_year))
            except (TypeError, ValueError):
                pass
        weighted_base += base_ebitda * weight
        weighted_replacement += replacement_compensation * weight
        weighted_actual += actual_compensation * weight
        weighted_sde += annual_sde * weight
        annual_rows.append(
            {
                "fiscal_year": fiscal_year,
                "weight": weight,
                "normalized_ebitda": normalized,
                "owner_compensation_normalization": owner_normalization,
                "actual_owner_compensation": actual_compensation,
                "replacement_owner_compensation": replacement_compensation,
                "owner_compensation_addback": replacement_compensation,
                "sde_base_ebitda": base_ebitda,
                "annual_sde": annual_sde,
                "weighted_annual_sde": annual_sde * weight,
                "evidence_ids": evidence_ids,
            }
        )

    return {
        "version": "stateless_sde_annual_basis_v2",
        "available": bool(
            annual_rows
            and has_governed_compensation
            and weighted_actual > 0
            and not missing_compensation_years
        ),
        "sde_base_ebitda": weighted_base,
        "actual_owner_compensation": weighted_actual,
        "replacement_owner_compensation": weighted_replacement,
        "owner_compensation_addback": weighted_replacement,
        "weighted_sde": weighted_sde,
        "rows": annual_rows,
        "missing_compensation_years": missing_compensation_years,
        "calculation_sequence": (
            "annual normalized EBITDA + governed replacement compensation, "
            "equivalent to reported EBITDA + actual owner compensation, then "
            "historical weighting"
        ),
    }


def _empty_weighted_sde_basis() -> dict[str, object]:
    return {
        "version": "stateless_sde_annual_basis_v2",
        "available": False,
        "sde_base_ebitda": Decimal("0"),
        "owner_compensation_addback": Decimal("0"),
        "actual_owner_compensation": Decimal("0"),
        "replacement_owner_compensation": Decimal("0"),
        "weighted_sde": Decimal("0"),
        "rows": [],
        "missing_compensation_years": [],
    }


def _decimal_or_zero(value: object) -> Decimal:
    if value is None or value == "":
        return Decimal("0")
    try:
        parsed = value if isinstance(value, Decimal) else Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal("0")
    return parsed if parsed.is_finite() else Decimal("0")


def _owner_compensation_adjustments(normalization_metadata: object) -> list[dict[str, object]]:
    if not isinstance(normalization_metadata, dict):
        return []

    adjustments = normalization_metadata.get("adjustments", [])
    if not isinstance(adjustments, list):
        return []

    return [
        adjustment
        for adjustment in adjustments
        if isinstance(adjustment, dict)
        and _is_owner_compensation_adjustment(adjustment)
        and _normalization_is_priced(adjustment)
    ]


def _normalization_is_priced(adjustment: dict[str, object]) -> bool:
    status = str(adjustment.get("status") or "").strip().lower()
    has_reviewer = bool(
        adjustment.get("reviewed_at")
        or adjustment.get("reviewedAt")
        or adjustment.get("decided_at")
    )
    return bool(
        adjustment.get("applied") is True
        and adjustment.get("source") == "valuation_input_decision.v2"
        and status in PRICED_NORMALIZATION_STATUSES
        and adjustment.get("id")
        and adjustment.get("evidence_id")
        and adjustment.get("rule_version")
        and adjustment.get("decided_by")
        and has_reviewer
        and adjustment.get("currency")
    )


def _is_owner_compensation_adjustment(adjustment: dict[str, object]) -> bool:
    for identifier in (
        adjustment.get("field"),
        adjustment.get("category"),
        adjustment.get("adjustment_type"),
        adjustment.get("label"),
    ):
        normalized = str(identifier or "").strip().lower()
        if normalized in OWNER_COMPENSATION_ADJUSTMENT_KEYS:
            return True
        if normalized.rsplit(".", 1)[-1] in OWNER_COMPENSATION_ADJUSTMENT_KEYS:
            return True
    return False


def _owner_compensation_terms(
    adjustment: dict[str, object],
) -> tuple[Decimal, Decimal] | None:
    """Return (actual, replacement) only when the economic identity reconciles."""

    role = _owner_role(adjustment)
    actual = _non_negative_decimal_or_none(adjustment.get("actual_owner_compensation"))
    replacement = _non_negative_decimal_or_none(adjustment.get("replacement_owner_compensation"))
    signed_amount = _finite_decimal_or_none(adjustment.get("signed_amount"))
    if role is None or actual is None or replacement is None or signed_amount is None:
        return None
    if actual <= 0:
        return None
    if role == "passive" and replacement != 0:
        return None
    if (actual - replacement).quantize(Decimal("0.01")) != signed_amount.quantize(Decimal("0.01")):
        return None
    return actual, replacement


def _owner_role(adjustment: dict[str, object]) -> str | None:
    role = adjustment.get("owner_role")
    if not isinstance(role, str):
        return None
    normalized = role.lower()
    return normalized if normalized in {"working", "passive"} else None


def _finite_decimal_or_none(value: object) -> Decimal | None:
    if value is None:
        return None
    try:
        converted = value if isinstance(value, Decimal) else Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None
    return converted if converted.is_finite() else None


def _non_negative_decimal_or_none(value: object) -> Decimal | None:
    converted = _finite_decimal_or_none(value)
    return converted if converted is not None and converted >= 0 else None


# ---------------------------------------------------------------------------
# Modelled owner compensation (public owner-operated class)
# ---------------------------------------------------------------------------
#
# `build_weighted_sde_basis` above requires governed, POSITIVE, actual owner
# compensation in every weighted year. That gate is correct for anything that
# claims to be filed evidence: an abbreviated filing cannot distinguish an owner
# who takes dividends (EBITDA is pre-compensation, so EBITDA *is* SDE) from one
# who bills a management fee above the gross-margin line (EBITDA is already
# post-compensation). Nothing below weakens it.
#
# This is the separate, explicitly MODELLED basis for the owner-operated public
# class. It never claims to be filed. Every consumer sees
# `owner_compensation_source = "modelled_market_rate"` and
# `disclosure_required = True`, and the surface that publishes it must say the
# owner's pay is assumed rather than reported.

MODELLED_SDE_BASIS_VERSION = "stateless_sde_modelled_owner_compensation_v1"

# Share of pre-compensation earnings a working owner is modelled to take. 40%
# reconciles with the platform's own SDE multiples: at BIITS's FY2025 EBITDA it
# returns EUR 69,746, and the consulting SDE multiple of 1.8x implies EUR ~70,000
# for the SDE and EV/EBITDA legs to agree. The band keeps the model honest at
# both ends - below the floor nobody could be hired to do the job, and above the
# cap the figure stops being a market rate for an owner-operated micro company.
MODELLED_OWNER_COMPENSATION_SHARE = Decimal("0.40")
MODELLED_OWNER_COMPENSATION_FLOOR = Decimal("45000")
MODELLED_OWNER_COMPENSATION_CAP = Decimal("120000")

# A filing whose gross margin is almost entirely EBITDA carries no payroll below
# the margin line, so no owner salary was expensed. That is the only shape this
# model is allowed to price.
OWNER_OPERATED_BELOW_MARGIN_COST_RATIO = Decimal("0.05")


def modelled_owner_compensation(pre_compensation_earnings: Decimal) -> Decimal:
    """Market-rate replacement pay for a working owner. Modelled, never filed."""
    modelled = pre_compensation_earnings * MODELLED_OWNER_COMPENSATION_SHARE
    return min(
        MODELLED_OWNER_COMPENSATION_CAP,
        max(MODELLED_OWNER_COMPENSATION_FLOOR, modelled),
    )


def is_owner_operated_filing(*, gross_margin: Decimal, ebitda: Decimal) -> bool:
    """True when the filing evidences no payroll beneath the gross-margin line."""
    if gross_margin <= 0 or ebitda <= 0 or ebitda > gross_margin:
        return False
    below_margin_cost = gross_margin - ebitda
    return below_margin_cost <= gross_margin * OWNER_OPERATED_BELOW_MARGIN_COST_RATIO


def public_owner_operated_classification(request: object) -> str:
    """Classify the company from every filed actual available to the parent run.

    A valuation timeline changes only the financial measurement year; it must
    not reclassify the same company as owner-operated merely because later
    filed evidence is removed from a historical subrequest.  The parent binds
    this classification before recursive checkpoint calculation.
    """

    years = [
        year
        for year in [
            getattr(request, "current_year", None),
            *(getattr(request, "historical_years", None) or []),
        ]
        if year is not None and not getattr(year, "is_forecast", False)
    ]
    if not years:
        return "not_owner_operated"
    for year in years:
        gross_margin = _modelled_decimal(getattr(year, "gross_margin", None))
        ebitda = _modelled_decimal(getattr(year, "ebitda", None))
        if (
            gross_margin is None
            or ebitda is None
            or not is_owner_operated_filing(gross_margin=gross_margin, ebitda=ebitda)
        ):
            return "not_owner_operated"
    return "owner_operated"


def build_modelled_sde_basis(rows: object) -> dict[str, object]:
    """SDE basis for an owner-operated company, on modelled replacement pay.

    `rows` carries one entry per fiscal year with `gross_margin`, `ebitda` and
    `weight`. Every year must independently look owner-operated; a single year
    with real payroll means the company is not in this class and the basis is
    refused rather than averaged into looking like one.
    """

    if not isinstance(rows, list) or not rows:
        return _unavailable_modelled_sde_basis("no_annual_rows")

    annual_rows: list[dict[str, object]] = []
    weighted_base = Decimal("0")
    weighted_replacement = Decimal("0")
    weighted_sde = Decimal("0")
    total_weight = Decimal("0")

    for raw_row in rows:
        if not isinstance(raw_row, dict):
            return _unavailable_modelled_sde_basis("malformed_annual_row")
        gross_margin = _modelled_decimal(raw_row.get("gross_margin"))
        ebitda = _modelled_decimal(raw_row.get("ebitda"))
        weight = _modelled_decimal(raw_row.get("weight")) or Decimal("0")
        if gross_margin is None or ebitda is None:
            return _unavailable_modelled_sde_basis("incomplete_annual_row")
        if not is_owner_operated_filing(gross_margin=gross_margin, ebitda=ebitda):
            return _unavailable_modelled_sde_basis("payroll_present_not_owner_operated")

        replacement = modelled_owner_compensation(ebitda)
        # SDE is earnings BEFORE owner pay. Nothing was expensed, so the filed
        # EBITDA already is SDE; normalized EBITDA is what remains after the
        # modelled replacement pay. The identity below is the same one the
        # governed basis satisfies: normalized + replacement == SDE.
        sde = ebitda
        normalized = sde - replacement
        annual_rows.append(
            {
                "fiscal_year": raw_row.get("fiscal_year"),
                "weight": weight,
                "gross_margin": gross_margin,
                "reported_ebitda": ebitda,
                "normalized_ebitda": normalized,
                "actual_owner_compensation": Decimal("0"),
                "replacement_owner_compensation": replacement,
                "owner_compensation_addback": replacement,
                "sde_base_ebitda": normalized,
                "annual_sde": sde,
                "owner_compensation_source": "modelled_market_rate",
            }
        )
        weighted_base += normalized * weight
        weighted_replacement += replacement * weight
        weighted_sde += sde * weight
        total_weight += weight

    if total_weight <= 0:
        return _unavailable_modelled_sde_basis("no_weighted_years")

    return {
        "version": MODELLED_SDE_BASIS_VERSION,
        "available": True,
        "owner_compensation_source": "modelled_market_rate",
        "disclosure_required": True,
        "model": {
            "share_of_pre_compensation_earnings": MODELLED_OWNER_COMPENSATION_SHARE,
            "floor": MODELLED_OWNER_COMPENSATION_FLOOR,
            "cap": MODELLED_OWNER_COMPENSATION_CAP,
        },
        "sde_base_ebitda": weighted_base,
        "actual_owner_compensation": Decimal("0"),
        "replacement_owner_compensation": weighted_replacement,
        "owner_compensation_addback": weighted_replacement,
        "weighted_sde": weighted_sde,
        "rows": annual_rows,
        "missing_compensation_years": [],
        "calculation_sequence": (
            "filed EBITDA taken as SDE because no owner pay was expensed, less "
            "modelled market-rate replacement pay, then historical weighting"
        ),
    }


def _unavailable_modelled_sde_basis(reason: str) -> dict[str, object]:
    return {
        "version": MODELLED_SDE_BASIS_VERSION,
        "available": False,
        "unavailable_reason": reason,
        "owner_compensation_source": "modelled_market_rate",
        "disclosure_required": True,
        "sde_base_ebitda": Decimal("0"),
        "owner_compensation_addback": Decimal("0"),
        "actual_owner_compensation": Decimal("0"),
        "replacement_owner_compensation": Decimal("0"),
        "weighted_sde": Decimal("0"),
        "rows": [],
        "missing_compensation_years": [],
    }


def _modelled_decimal(value: object) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def apply_modelled_owner_normalization(
    request: object, earnings_basis: dict[str, object]
) -> dict[str, object]:
    """Charge a working owner market-rate pay when the filing expenses none.

    A public run for the owner-operated class prices earnings that pay nobody
    for the work. Normalizing that is the whole point: a buyer has to replace
    the owner, so the market rate for the role is deducted before any multiple
    is applied. The rate is MODELLED, never filed, and the result says so.

    This deliberately does not go through the governed owner-compensation
    adjustment contract. That contract requires positive ACTUAL pay and stamps
    trial-balance provenance, and a modelled figure must never be recorded as
    reviewed evidence. Here it only moves normalized EBITDA, which is what a
    valuation should be priced on either way.
    """

    rows = earnings_basis.get("rows")
    if not isinstance(rows, list) or not rows:
        return earnings_basis

    # Gross margin lives on the request years, not on the earnings-basis rows.
    years = [
        year
        for year in [getattr(request, "current_year", None), *(getattr(request, "historical_years", None) or [])]
        if year is not None and not getattr(year, "is_forecast", False)
    ]
    gross_margin_by_year = {
        getattr(year, "year", None): _modelled_decimal(getattr(year, "gross_margin", None))
        for year in years
    }
    # Judge owner-operated status on EVERY filed year, not only the years the
    # earnings basis happened to select. Devso shed 2.3 FTE and looks
    # owner-operated in 2025 alone; weighting can narrow the basis to that year
    # and would then charge owner pay to a company that plainly had staff.
    if public_owner_operated_classification(request) != "owner_operated":
        return earnings_basis

    normalized_rows: list[dict[str, object]] = []
    weighted_normalized = Decimal("0")
    weighted_replacement = Decimal("0")
    for raw_row in rows:
        if not isinstance(raw_row, dict):
            return earnings_basis
        reported = _modelled_decimal(raw_row.get("reported_ebitda"))
        normalized = _modelled_decimal(raw_row.get("normalized_ebitda"))
        gross_margin = gross_margin_by_year.get(raw_row.get("fiscal_year")) or gross_margin_by_year.get(raw_row.get("year"))
        weight = _modelled_decimal(raw_row.get("weight")) or Decimal("0")
        if reported is None or normalized is None or gross_margin is None:
            return earnings_basis
        if not is_owner_operated_filing(gross_margin=gross_margin, ebitda=reported):
            return earnings_basis
        replacement = modelled_owner_compensation(reported)
        row = dict(raw_row)
        row["normalized_ebitda"] = normalized - replacement
        row["modelled_owner_compensation"] = replacement
        row["owner_compensation_source"] = "modelled_market_rate"
        normalized_rows.append(row)
        weighted_normalized += (normalized - replacement) * weight
        weighted_replacement += replacement * weight

    current_year = getattr(request, "current_year", None)
    current_reported = _modelled_decimal(getattr(current_year, "ebitda", None)) or Decimal("0")
    current_replacement = modelled_owner_compensation(current_reported)
    current_normalized = (
        _modelled_decimal(earnings_basis.get("current_normalized_ebitda")) or Decimal("0")
    ) - current_replacement

    payload = dict(earnings_basis)
    payload["rows"] = normalized_rows
    payload["normalized_ebitda"] = weighted_normalized
    payload["current_normalized_ebitda"] = current_normalized
    payload["total_adjustments"] = weighted_normalized - (
        _modelled_decimal(earnings_basis.get("reported_ebitda")) or Decimal("0")
    )
    payload["owner_compensation_source"] = "modelled_market_rate"
    payload["modelled_owner_compensation"] = weighted_replacement
    payload["disclosure_required"] = True
    return payload
