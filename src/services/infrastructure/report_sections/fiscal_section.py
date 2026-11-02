"""
Fiscal Reference Section Builder
================================

Computes the Belgian fiscal reference annex (Art. 102, § 4 WIB 92):
    Forfaitaire waarde = Eigen Vermogen + 4 × EBITDA (laatst afgesloten boekjaar)

Single source of truth for the formula. Titan mirrors the field shape in
``computeFiscalReferenceFields`` for Mercury preview parity.

Architecture
------------

Public surface is intentionally narrow:

    build_fiscal_reference_context(...) -> FiscalReferenceContext

Internally the build is decomposed into pure resolver helpers, each with a
single concern. They take what they need, return a frozen dataclass, and
never mutate input. Each branch is independently testable and the top-level
``_build_inner`` reads as a sequence of named steps.

  _resolve_book_equity       → BookEquityResolution     (line item or bridge)
  _resolve_peildatum         → str | None               (DD/MM/YYYY)
  _resolve_ebitda_disclosure → EbitdaDisclosure         (statutaire vs applied)
  _resolve_carve_out         → CarveOutResolution       (real-estate impact)
  _resolve_company_context   → CompanyContextResolution (intern/role/anchors)

Defensibility contract
----------------------

* The headline ``fiscal_reference_value`` is **only** populated when book
  equity comes from a high-confidence source (statutaire balance-sheet
  line or explicit advisor override). Bridge-derived equity (assets minus
  debt) is shown for transparency but does **not** unlock the headline —
  Three Towers Capital regression: a missing or zero balance must not
  surface a misleading 4× EBITDA "FRW €400K" tile.
* Wettelijke formule references EBITDA *van het laatst afgesloten
  boekjaar*. When the upstream pipeline already applied a normalisation
  pass, the page surfaces ``fiscal_reported_ebitda`` and flags the gap so
  the reviewer sees both numbers.
* Peildatum is always 31/12/2025. The last closed financial year selects
  the accounts used by the formula and never changes that reference date.
* When the page is requested but book equity is missing, a structured
  ``fiscal_integrity_warning`` (Pass-8) is emitted so the report-wide
  high-severity callout on Page 1 fires — readers can't miss that the
  headline is partial.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional, TypeAlias, TypedDict

from src.utils.decimal_helpers import safe_decimal_or_zero as _safe_decimal
from src.utils.decimal_helpers import safe_float as _to_float

logger = logging.getLogger(__name__)

JsonMap: TypeAlias = dict[str, object]
JsonRows: TypeAlias = list[JsonMap]

_VALID_COMPANY_ROLES: tuple[str, ...] = ("werkmaatschappij", "holding", "mixed")
_NORMALIZED_GAP_TOLERANCE: Decimal = Decimal("0.5")  # ignore sub-€1 rounding noise
_HEADLINE_ELIGIBLE_SOURCES: tuple[str, ...] = ("balance_sheet", "manual_override")


# ---------------------------------------------------------------------------
# Public typed contract
# ---------------------------------------------------------------------------


class FiscalReferenceContext(TypedDict, total=False):
    """Stable shape returned to Jinja and JSON consumers.

    ``total=False`` because the only field guaranteed when the page is hidden
    is ``show_fiscal_reference: False``. Templates check that flag before
    accessing any other key.
    """

    show_fiscal_reference: bool
    fiscal_ebitda_multiple: float
    fiscal_normalized_ebitda: float
    fiscal_reported_ebitda: Optional[float]
    fiscal_uses_normalized_ebitda: bool
    fiscal_ebitda_component: float
    fiscal_book_equity: Optional[float]
    fiscal_book_equity_source: Optional[str]
    fiscal_book_equity_negative: bool
    fiscal_value_complete: bool
    fiscal_reference_value: Optional[float]
    fiscal_reference_year: Optional[int]
    fiscal_reference_date: Optional[str]
    fiscal_internal_transfer: Optional[bool]
    fiscal_company_role: Optional[str]
    fiscal_legal_anchors_acknowledged: bool
    fiscal_confirmed_anchors: list[str]
    fiscal_real_estate_carve_out_applied: bool
    fiscal_real_estate_book_value: Optional[float]
    fiscal_real_estate_market_rent: Optional[float]
    fiscal_ebitda_source_label: Optional[str]
    fiscal_show_statutory_ebitda_caution: bool
    fiscal_integrity_warnings: JsonRows
    # ---- Advisor-supplied fields (Venus FiscalInputsSection) ----
    # Acquisition value the accountant intends to file. Defaults to the
    # max-of-four-anchors when not explicitly supplied.
    fiscal_acquisition_cost: Optional[float]
    # Proven historical share cost supplied by the adviser. This is separate
    # from the four statutory methods and may only raise the proposed basis.
    fiscal_proven_historical_cost: Optional[float]
    # Statutory methods. Method 1 is the engine formula, methods 2 and 3 are
    # adviser inputs, and method 4 is an independent professional report.
    fiscal_anchor_1_value: Optional[float]  # mirrors fiscal_reference_value
    fiscal_anchor_2_value: Optional[float]  # contractual formula
    fiscal_anchor_3_value: Optional[float]  # 2025 market transaction
    fiscal_anchor_4_value: Optional[float]  # independent valuation report
    # Supported 31/12/2025 value after applying the professional-report
    # substitution rule and selecting the highest remaining method.
    fiscal_max_anchor_value: Optional[float]
    fiscal_max_anchor_label: Optional[str]  # 'anchor_1'..'anchor_4' for highlight
    # Statutair vs genormaliseerd disclosure (advisor-pinned).
    fiscal_ebitda_basis: Optional[str]  # 'statutair' | 'genormaliseerd'


# ---------------------------------------------------------------------------
# Coercion primitives
# ---------------------------------------------------------------------------


def _attr(obj: object, name: str, default: object = None) -> object:
    val = getattr(obj, name, default)
    return default if val is None else val


def _coerce_optional_decimal(value: object) -> Optional[Decimal]:
    if value is None:
        return None
    try:
        return _safe_decimal(value)
    except (TypeError, ValueError, ArithmeticError):
        return None


def _coerce_bool(value: object) -> Optional[bool]:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        v = value.strip().lower()
        if v in ("true", "1", "yes", "y", "intern", "internal"):
            return True
        if v in ("false", "0", "no", "n", "extern", "external"):
            return False
        return None
    if isinstance(value, (int, float)):
        return bool(value)
    return None


def _coerce_role(value: object) -> Optional[str]:
    if not isinstance(value, str):
        return None
    v = value.strip().lower()
    return v if v in _VALID_COMPANY_ROLES else None


def _coerce_str_list(value: object) -> list[str]:
    if not isinstance(value, (list, tuple, set)):
        return []
    return [item.strip() for item in value if isinstance(item, str) and item.strip()]


# ---------------------------------------------------------------------------
# Resolvers (pure, single-concern, dataclass-typed returns)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BookEquityResolution:
    """Outcome of resolving book equity for the FRW formula.

    ``headline_eligible`` flips True only for high-confidence sources
    (statutaire ``balance_sheet`` line item or explicit ``manual_override``).
    The bridge fallback (``assets_minus_debt``) populates ``value`` for
    line-item transparency but leaves ``headline_eligible=False`` so the
    side-by-side headline stays suppressed — see Three Towers regression.
    """

    value: Optional[Decimal]
    source: Optional[str]
    headline_eligible: bool
    is_negative: bool


@dataclass(frozen=True)
class EbitdaDisclosure:
    """The EBITDA used in the formula versus the statutory figure.

    When ``uses_normalized`` is True a disclosure row appears in the report
    so the reviewer sees both numbers — required for Art. 90 WIB 92
    defensibility, since the law expects statutory EBITDA, not management
    normalisations.
    """

    applied: Decimal
    reported: Optional[Decimal]
    uses_normalized: bool


@dataclass(frozen=True)
class CarveOutResolution:
    applied: bool
    book_value: Optional[Decimal]
    market_rent: Optional[Decimal]


@dataclass(frozen=True)
class CompanyContextResolution:
    internal_transfer: Optional[bool]
    company_role: Optional[str]
    anchors_acknowledged: bool
    confirmed_anchors: list[str]
    ebitda_source_label: Optional[str]


def _resolve_book_equity(
    cyd: object,
    metadata: JsonMap,
) -> BookEquityResolution:
    """Resolve book equity in priority order:

      1. ``total_equity`` — balance-sheet line item (high confidence)
      2. ``total_assets - total_debt`` — bridge (transparency only)
      3. ``metadata.fiscal_book_equity`` — advisor override (high confidence)

    Only #1 and #3 unlock the headline FRW value; #2 is shown as a line
    item but does not flip ``fiscal_value_complete``.
    """
    total_equity = _attr(cyd, "total_equity", None)
    if total_equity is not None:
        value = _safe_decimal(total_equity)
        return BookEquityResolution(
            value=value,
            source="balance_sheet",
            headline_eligible=True,
            is_negative=value < Decimal("0"),
        )

    total_assets = _attr(cyd, "total_assets", None)
    total_debt = _attr(cyd, "total_debt", None)
    if total_assets is not None and total_debt is not None:
        value = _safe_decimal(total_assets) - _safe_decimal(total_debt)
        return BookEquityResolution(
            value=value,
            source="assets_minus_debt",
            headline_eligible=False,  # bridge ≠ statutaire confirmation
            is_negative=value < Decimal("0"),
        )

    override = metadata.get("fiscal_book_equity")
    if override is not None:
        coerced = _coerce_optional_decimal(override)
        if coerced is not None:
            return BookEquityResolution(
                value=coerced,
                source="manual_override",
                headline_eligible=True,
                is_negative=coerced < Decimal("0"),
            )

    return BookEquityResolution(
        value=None,
        source=None,
        headline_eligible=False,
        is_negative=False,
    )


def _resolve_peildatum(
    metadata: JsonMap,
    year_value: object,
) -> Optional[str]:
    """Return the fixed historical valuation date for the 2026 regime.

    The financial year selects the accounts used by the formula. It does not
    change the statutory valuation date. Keeping those two dates separate
    prevents a non calendar year end from becoming a false reference date.
    """
    del metadata, year_value
    return "31/12/2025"


def _resolve_ebitda_disclosure(
    fiscal_ebitda: Decimal,
    fiscal_reported_ebitda: Optional[Decimal],
) -> EbitdaDisclosure:
    """Compare the EBITDA actually used against the statutaire figure.

    A gap is detected only when both values are present and differ by more
    than ``_NORMALIZED_GAP_TOLERANCE`` — guards against sub-cent rounding
    flapping the disclosure row.
    """
    applied = _safe_decimal(fiscal_ebitda)
    reported = _coerce_optional_decimal(fiscal_reported_ebitda)
    uses_normalized = (
        reported is not None and (reported - applied).copy_abs() > _NORMALIZED_GAP_TOLERANCE
    )
    return EbitdaDisclosure(applied=applied, reported=reported, uses_normalized=uses_normalized)


def _resolve_carve_out(metadata: JsonMap) -> CarveOutResolution:
    """Real-estate carve-out state for the fiscal annex disclosure.

    The aggregator pre-fills these keys when ``request.exclude_real_estate``
    is True; the resolver also catches stand-alone book-value or rent values
    set directly in metadata so the impact is surfaced in either case.
    """
    flag = bool(_coerce_bool(metadata.get("real_estate_carve_out_applied")) or False)
    book_value = _coerce_optional_decimal(metadata.get("real_estate_book_value"))
    market_rent = _coerce_optional_decimal(metadata.get("real_estate_market_rent"))
    if not flag and (book_value or market_rent):
        flag = True
    return CarveOutResolution(applied=flag, book_value=book_value, market_rent=market_rent)


def _resolve_company_context(metadata: JsonMap) -> CompanyContextResolution:
    """Transfer, company role, method review and EBITDA source."""
    ebitda_source_label = metadata.get("fiscal_ebitda_source")
    if not isinstance(ebitda_source_label, str) or not ebitda_source_label.strip():
        ebitda_source_label = None
    return CompanyContextResolution(
        internal_transfer=_coerce_bool(metadata.get("fiscal_internal_transfer")),
        company_role=_coerce_role(metadata.get("fiscal_company_role")),
        anchors_acknowledged=bool(
            _coerce_bool(metadata.get("fiscal_legal_anchors_acknowledged")) or False
        ),
        confirmed_anchors=_coerce_str_list(metadata.get("fiscal_confirmed_anchors")),
        ebitda_source_label=ebitda_source_label,
    )


def _build_integrity_warnings(*, value_complete: bool) -> JsonRows:
    """Pass-8 disclosure rollup. When the fiscal page is requested but book
    equity is missing, emit a structured warning that the aggregator merges
    into the report-wide high-severity callout list. Without this the page
    renders with an "(excl. eigen vermogen)" suffix only, which readers can
    miss — the integrity warning forces the Page-1 banner to fire.
    """
    if value_complete:
        return []
    # Local import to avoid a hard cycle if report_integrity ever depends on
    # report_sections in the future.
    from src.domain.report_integrity import build_book_equity_unavailable_warning

    return [build_book_equity_unavailable_warning()]


# ---------------------------------------------------------------------------
# Public builder
# ---------------------------------------------------------------------------


def build_fiscal_reference_context(
    *,
    show_fiscal_reference: bool,
    country_code: str,
    fiscal_ebitda: Decimal,
    closed_fiscal_year_data: object,
    metadata: Optional[JsonMap],
    fiscal_reported_ebitda: Optional[Decimal] = None,
) -> FiscalReferenceContext:
    """Build fiscal reference context for the Belgian fiscal annex page.

    Args:
        show_fiscal_reference: Whether the accountant opted in.
        country_code: ISO-3166 alpha-2 (must be ``"BE"``).
        fiscal_ebitda: EBITDA used in the formule (typically the closed-year
            value resolved by ``_get_fiscal_ebitda``).
        closed_fiscal_year_data: Latest closed-year object (balance + year).
        metadata: Request metadata; may contain:
          - ``fiscal_book_equity``: explicit override when balance is empty
          - ``fiscal_internal_transfer``: bool, drives 33% messaging
          - ``fiscal_company_role``: 'werkmaatschappij' | 'holding' | 'mixed'
          - ``fiscal_legal_anchors_acknowledged``: bool, method-review check
          - ``fiscal_confirmed_anchors``: list[str], optional anchor names
          - ``real_estate_carve_out_applied`` / ``_book_value`` / ``_market_rent``
          - ``fiscal_ebitda_source``: provenance label
        fiscal_reported_ebitda: Statutaire EBITDA when the upstream pipeline
            already applied normalisation; surfaces the gap on the page.
    """
    if not show_fiscal_reference or country_code != "BE" or closed_fiscal_year_data is None:
        return {"show_fiscal_reference": False}

    try:
        return _build_inner(
            fiscal_ebitda,
            closed_fiscal_year_data,
            metadata,
            fiscal_reported_ebitda,
        )
    except (TypeError, ValueError, ArithmeticError, AttributeError) as exc:
        logger.warning("Fiscal reference computation failed: %s", exc)
        return {"show_fiscal_reference": False}


def _build_inner(
    fiscal_ebitda: Decimal,
    cyd: object,
    metadata: Optional[JsonMap],
    fiscal_reported_ebitda: Optional[Decimal],
) -> FiscalReferenceContext:
    meta = metadata if isinstance(metadata, dict) else {}
    fiscal_multiple = Decimal("4.0")

    ebitda = _resolve_ebitda_disclosure(fiscal_ebitda, fiscal_reported_ebitda)
    ebitda_component = ebitda.applied * fiscal_multiple

    closed_year_attr = _attr(cyd, "year", None)
    closed_year = closed_year_attr if isinstance(closed_year_attr, int) else None
    peildatum = _resolve_peildatum(meta, closed_year)

    carve_out = _resolve_carve_out(meta)
    company = _resolve_company_context(meta)

    # Auto derive the EBITDA basis from the disclosed source. An explicit
    # internal setting may label the basis, but it cannot make missing or
    # normalized statutory evidence complete.
    ebitda_basis_raw = meta.get("fiscal_ebitda_basis")
    if isinstance(ebitda_basis_raw, str) and ebitda_basis_raw in (
        "statutair",
        "genormaliseerd",
    ):
        ebitda_basis: Optional[str] = ebitda_basis_raw
    else:
        ebitda_basis = (
            "genormaliseerd"
            if (
                ebitda.uses_normalized
                or ebitda.reported is None
                or company.ebitda_source_label is None
            )
            else "statutair"
        )

    statutory_ebitda_confirmed = (
        not ebitda.uses_normalized
        and ebitda.reported is not None
        and ebitda_basis == "statutair"
        and company.ebitda_source_label is not None
    )
    equity = _resolve_book_equity(cyd, meta)
    formula_complete = equity.headline_eligible and statutory_ebitda_confirmed
    fiscal_value: Optional[Decimal] = (
        (equity.value + ebitda_component) if formula_complete and equity.value is not None else None
    )
    integrity_warnings = _build_integrity_warnings(value_complete=equity.headline_eligible)

    # ---- Adviser-supplied statutory methods -------------------------------
    # The law selects the highest of the 2025 transaction, contractual formula
    # and statutory formula. A qualifying professional report replaces the
    # statutory formula; it is not a fourth value added to the same maximum.
    anchor_1: Optional[Decimal] = fiscal_value
    anchor_2 = _coerce_optional_decimal(meta.get("fiscal_anchor_2_value"))
    anchor_3 = _coerce_optional_decimal(meta.get("fiscal_anchor_3_value"))
    anchor_4 = _coerce_optional_decimal(meta.get("fiscal_anchor_4_value"))
    proven_historical_cost = _coerce_optional_decimal(meta.get("fiscal_acquisition_cost"))

    populated_methods: list[tuple[str, Decimal]] = [
        (label, value)
        for label, value in (
            ("anchor_2", anchor_2),
            ("anchor_3", anchor_3),
            ("anchor_4", anchor_4) if anchor_4 is not None else ("anchor_1", anchor_1),
        )
        if value is not None
    ]
    if populated_methods:
        max_label, max_value = max(populated_methods, key=lambda pair: pair[1])
    else:
        max_label, max_value = None, None

    # Historical share cost is separate from the supported statutory methods. It
    # may raise the proposed basis when supported, but a lower manual value
    # must never replace the highest populated statutory method.
    basis_candidates = [value for value in (max_value, proven_historical_cost) if value is not None]
    final_acquisition_cost = max(basis_candidates) if basis_candidates else None

    return {
        "show_fiscal_reference": True,
        "fiscal_ebitda_multiple": _to_float(fiscal_multiple),
        "fiscal_normalized_ebitda": _to_float(ebitda.applied),
        "fiscal_reported_ebitda": (
            _to_float(ebitda.reported) if ebitda.reported is not None else None
        ),
        "fiscal_uses_normalized_ebitda": ebitda.uses_normalized,
        "fiscal_ebitda_component": _to_float(ebitda_component),
        "fiscal_book_equity": _to_float(equity.value) if equity.value is not None else None,
        "fiscal_book_equity_source": equity.source,
        "fiscal_book_equity_negative": equity.is_negative,
        "fiscal_value_complete": formula_complete,
        "fiscal_reference_value": _to_float(fiscal_value) if fiscal_value is not None else None,
        "fiscal_reference_year": closed_year,
        "fiscal_reference_date": peildatum,
        "fiscal_internal_transfer": company.internal_transfer,
        "fiscal_company_role": company.company_role,
        "fiscal_legal_anchors_acknowledged": company.anchors_acknowledged,
        "fiscal_confirmed_anchors": company.confirmed_anchors,
        "fiscal_real_estate_carve_out_applied": carve_out.applied,
        "fiscal_real_estate_book_value": (
            _to_float(carve_out.book_value) if carve_out.book_value is not None else None
        ),
        "fiscal_real_estate_market_rent": (
            _to_float(carve_out.market_rent) if carve_out.market_rent is not None else None
        ),
        "fiscal_ebitda_source_label": company.ebitda_source_label,
        "fiscal_show_statutory_ebitda_caution": (
            ebitda.uses_normalized
            or ebitda.reported is None
            or ebitda_basis != "statutair"
            or company.ebitda_source_label is None
        ),
        "fiscal_integrity_warnings": integrity_warnings,
        # Adviser-supplied method payload and final supported value.
        "fiscal_acquisition_cost": (
            _to_float(final_acquisition_cost) if final_acquisition_cost is not None else None
        ),
        "fiscal_proven_historical_cost": (
            _to_float(proven_historical_cost) if proven_historical_cost is not None else None
        ),
        "fiscal_anchor_1_value": _to_float(anchor_1) if anchor_1 is not None else None,
        "fiscal_anchor_2_value": _to_float(anchor_2) if anchor_2 is not None else None,
        "fiscal_anchor_3_value": _to_float(anchor_3) if anchor_3 is not None else None,
        "fiscal_anchor_4_value": _to_float(anchor_4) if anchor_4 is not None else None,
        "fiscal_max_anchor_value": _to_float(max_value) if max_value is not None else None,
        "fiscal_max_anchor_label": max_label,
        "fiscal_ebitda_basis": ebitda_basis,
    }
