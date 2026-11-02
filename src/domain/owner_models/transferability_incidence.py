"""Per-method incidence and narrative cascade for transferability v2."""

from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

from src.domain.owner_models.transferability_buyer_gap import BuyerProfile, TransferabilityGap
from src.domain.owner_models.transferability_decomposition import TransferabilityDecomposition


METHOD_INCIDENCE: dict[str, Decimal] = {
    "ebitda_multiple": Decimal("1.00"),
    "dcf": Decimal("1.00"),
    "sde": Decimal("0.70"),
    "revenue_multiple": Decimal("0.60"),
    "arr_multiple": Decimal("0.50"),
    "adaptive": Decimal("0.85"),
    "adjusted_nav": Decimal("0.00"),
    "fiscal_4x": Decimal("0.00"),
    "startup": Decimal("0.00"),
}


class MethodIncidence(BaseModel):
    """Per-method coefficient plus the resulting effective discount."""

    method: str
    label: str
    coefficient: Decimal = Field(ge=0, le=1)
    applied_pct: Decimal
    rationale: str

    model_config = ConfigDict(use_enum_values=True)


_METHOD_LABELS_EN: dict[str, str] = {
    "ebitda_multiple": "EBITDA multiple",
    "dcf": "DCF",
    "sde": "SDE multiple",
    "revenue_multiple": "Revenue multiple",
    "arr_multiple": "ARR multiple",
    "adaptive": "Adaptive (blended)",
    "adjusted_nav": "Adjusted NAV",
    "fiscal_4x": "Fiscal 4×",
    "startup": "Startup / VC",
}

_METHOD_RATIONALE_EN: dict[str, str] = {
    "ebitda_multiple": "Comps are managed businesses; full owner-transition discount applies.",
    "dcf": "Cash-flow projections assume continuity; full discount applies.",
    "sde": "SDE already captures owner comp; only the residual transferability haircut on the multiple applies (~0.7×).",
    "revenue_multiple": "Revenue multiples lean on customer stickiness; partial discount (~0.6×).",
    "arr_multiple": "ARR multiples already discount owner-led customer-success; partial (~0.5×).",
    "adaptive": "Adaptive blends multiple lenses; near-full discount (~0.85×).",
    "adjusted_nav": "NAV transfers with the assets; owner-dependency does not apply.",
    "fiscal_4x": "Fiscal 4× is a regulatory floor; owner-dependency does not adjust it.",
    "startup": "Startup valuation is forward-looking on team / market; owner-dep adjustment is captured elsewhere.",
}


def method_incidence_table(headline_adjustment_pct: Decimal) -> List[MethodIncidence]:
    """Return the full nine-method incidence table for a headline adjustment."""
    rows: List[MethodIncidence] = []
    for method, coeff in METHOD_INCIDENCE.items():
        applied = (Decimal(str(headline_adjustment_pct)) * coeff).quantize(Decimal("0.0001"))
        rows.append(
            MethodIncidence(
                method=method,
                label=_METHOD_LABELS_EN[method],
                coefficient=coeff,
                applied_pct=applied,
                rationale=_METHOD_RATIONALE_EN[method],
            )
        )
    return rows


def blended_incidence(
    headline_adjustment_pct: Decimal,
    eligible_methods: Optional[List[str]] = None,
) -> Decimal:
    """Average effective discount across a subset of methods."""
    if eligible_methods is None:
        eligible_methods = [m for m, c in METHOD_INCIDENCE.items() if c > 0]
    coeffs = [METHOD_INCIDENCE[m] for m in eligible_methods if m in METHOD_INCIDENCE]
    coeffs = [c for c in coeffs if c > 0]
    if not coeffs:
        return Decimal("0")
    avg = sum(coeffs, Decimal("0")) / Decimal(len(coeffs))
    return (Decimal(str(headline_adjustment_pct)) * avg).quantize(Decimal("0.0001"))


class CascadeLineData(BaseModel):
    """Structured data for one line of the narrative cascade."""

    key: str
    fields: dict[str, object]

    model_config = ConfigDict(use_enum_values=True)


def build_cascade_data(
    decomposition: TransferabilityDecomposition,
    buyer_profile: BuyerProfile,
    gap: TransferabilityGap,
    headline_adjustment_pct: Decimal,
    raw_engine_adjustment_pct: Optional[Decimal],
    eligible_methods: Optional[List[str]] = None,
) -> List[CascadeLineData]:
    """Structured cascade data for locale-aware renderers."""
    weakest_key_lower = (
        decomposition.weakest_key.lower().replace("_", " ")
        if decomposition.weakest_key
        else "transferability"
    )
    weakest_score = decomposition.weakest_score or Decimal("50")
    blended_pct = blended_incidence(headline_adjustment_pct, eligible_methods)

    return [
        CascadeLineData(
            key="owner",
            fields={
                "owner_hours": gap.owner_hours_per_week or 60,
                "weakest_label_lower": weakest_key_lower,
                "weakest_score": str(weakest_score),
            },
        ),
        CascadeLineData(
            key="buyer",
            fields={
                "buyer_archetype": str(buyer_profile.archetype).replace("_", " "),
                "buyer_hours": buyer_profile.expected_hours_per_week,
                "buyer_skill": buyer_profile.expected_skill_match,
            },
        ),
        CascadeLineData(
            key="gap",
            fields={
                "severity": str(gap.severity),
                "hours_gap": gap.hours_gap,
                "skill_gap": int(gap.skill_gap),
                "raw_pct": _format_pct(raw_engine_adjustment_pct or Decimal("0")),
            },
        ),
        CascadeLineData(
            key="applied",
            fields={
                "headline_pct": _format_pct(headline_adjustment_pct),
                "blended_pct": _format_pct(blended_pct),
            },
        ),
    ]


def build_narrative_cascade(
    decomposition: TransferabilityDecomposition,
    buyer_profile: BuyerProfile,
    gap: TransferabilityGap,
    headline_adjustment_pct: Decimal,
    raw_engine_adjustment_pct: Optional[Decimal],
    eligible_methods: Optional[List[str]] = None,
) -> List[str]:
    """Build the four-line advisor-readable story rendered in the report."""
    weakest_label = (
        next(
            (sf.label for sf in decomposition.sub_factors if sf.key == decomposition.weakest_key),
            None,
        )
        if decomposition.weakest_key
        else None
    )
    blended_pct = blended_incidence(headline_adjustment_pct, eligible_methods)

    lines: List[str] = []
    lines.append(
        f"Owner profile: ~{gap.owner_hours_per_week or 60} hrs/week, "
        f"weakest sub-factor is {(weakest_label or 'transferability').lower()} "
        f"(score {decomposition.weakest_score or 50}/100)."
    )
    lines.append(
        f"Likely buyer ({buyer_profile.archetype.replace('_', ' ')}): "
        f"~{buyer_profile.expected_hours_per_week} hrs/week, "
        f"sector skill match {buyer_profile.expected_skill_match}/100."
    )
    lines.append(
        f"Transferability gap is {gap.severity}: "
        f"{gap.hours_gap} hrs/week + {int(gap.skill_gap)}/100 skill. "
        f"Engine raw discount {_format_pct(raw_engine_adjustment_pct or Decimal('0'))}."
    )
    lines.append(
        f"Headline applied {_format_pct(headline_adjustment_pct)}, "
        f"blended across eligible methods at {_format_pct(blended_pct)} effective."
    )

    return lines


def _format_pct(value: Decimal) -> str:
    """Format a decimal percent as a signed one-decimal percentage."""
    pct = float(Decimal(str(value)) * Decimal("100"))
    return f"{pct:+.1f}%"
