"""
Lease Normalizer — IFRS 16 and Belgian/Dutch GAAP Treatment

Identifies operating leases in the P&L and computes the IFRS 16 EBITDA
add-back for lease-heavy businesses (retail, logistics, hospitality).

This resolves the single most common source of buyer/seller disagreement
in lease-heavy SME transactions: depending on whether leases are capitalized
(IFRS 16) or expensed (Belgian/Dutch GAAP for SMEs), EBITDA can differ by
20–40% for a typical retail or logistics business.

Methodology:
1. Identify operating lease lines in the trial balance (MAR 611 / RGS 4120-4129)
2. For each lease line, compute the IFRS 16 EBITDA add-back:
   - Under IFRS 16: rent expense is replaced by depreciation (RoU asset) +
     interest (lease liability). Both sit below EBITDA → EBITDA increases by
     the full rent amount.
   - Under Belgian/Dutch GAAP for SMEs: rent is an operating expense above EBITDA.
   Net EBITDA impact = +rent amount (full add-back to EBITDA)
3. Flag the GAAP regime mismatch and its materiality for the advisor.

EBITDA add-back formula:
    EBITDA_IFRS16 = EBITDA_GAAP + operating_lease_expenses

Use case:
- Retail (huur winkelpand, loyer boutique): typically 8-12% of revenue
- Logistics (warehouse leases): 5-8% of revenue
- Hospitality (restaurant, hotel premises): 10-15% of revenue

Important: this module proposes the add-back and flags it — the advisor
confirms and includes it in the normalization schedule. It does NOT
automatically apply to the valuation without advisor acknowledgement.

Academic basis:
- IASB IFRS 16 (2016, effective 2019): Leases — recognition and measurement
- EY (2023): "IFRS 16 and its impact on business valuations"
- Deloitte (2022): "EBITDA normalization for lease-heavy businesses"
- KPMG (2023): "SME valuation — GAAP vs IFRS EBITDA bridge"
- CBN/CNC advies 2019/4 (BE): Behandeling van operationele leasecontracten

Belgian MAR codes: 611x (huur en huurlasten)
Dutch RGS codes: 4120-4129 (huurkosten bedrijfsruimte), 4130 (operational lease)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from src.utils.decimal_helpers import bank_round, from_decimal, to_decimal
from src.utils.logging import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Account code classification
# ---------------------------------------------------------------------------

# MAR (Belgian plan comptable) codes that represent operating lease / rent
_LEASE_MAR_PREFIXES = frozenset(
    [
        "611",   # Huur en huurlasten (operational lease, premises, equipment)
        "6110",  # Gebouwhuur
        "6111",  # Kleine leasing (short-term)
        "6112",  # Voertuigleasing (vehicle operating lease)
        "6113",  # Materiaalleasing (equipment operating lease)
        "6114",  # IT-leasing
    ]
)

# NL RGS codes for huur / operational lease
_LEASE_RGS_PREFIXES = frozenset(
    [
        "4120", "4121", "4122", "4123", "4124",
        "4125", "4126", "4127", "4128", "4129",
        "4130",  # Operational lease (voertuigen/machines)
    ]
)

# Description signals that confirm a line is an operating lease
_LEASE_DESCRIPTION_SIGNALS = frozenset(
    [
        "huur", "huurlasten", "leasing", "lease", "loyer", "location",
        "pacht", "erfpacht", "rent", "huurkost", "bedrijfsruimte",
        "kantoor", "magazijn", "bureau", "winkelpand", "handelspand",
        "operationele lease", "operational lease", "voertuigleasing",
        "wagenparkleasing", "materiaalhuur",
    ]
)

# Signals that suggest a finance lease (capitalized — already below EBITDA)
_FINANCE_LEASE_SIGNALS = frozenset(
    [
        "financiële leasing", "financial lease", "finance lease",
        "173", "1730", "1731",  # MAR balance-sheet finance lease codes
    ]
)

# Sector lease intensity benchmarks (% of revenue)
_LEASE_SECTOR_BENCHMARKS: dict[str, tuple[Decimal, Decimal]] = {
    "retail":        (Decimal("0.090"), Decimal("0.035")),
    "hospitality":   (Decimal("0.120"), Decimal("0.045")),
    "logistics":     (Decimal("0.070"), Decimal("0.030")),
    "manufacturing": (Decimal("0.035"), Decimal("0.020")),
    "services":      (Decimal("0.050"), Decimal("0.025")),
    "other":         (Decimal("0.055"), Decimal("0.025")),
}


def _sector_key(industry: str | None) -> str:
    raw = (industry or "").lower().strip()
    if "retail" in raw or "winkel" in raw or "shop" in raw:
        return "retail"
    if "hotel" in raw or "horeca" in raw or "restaurant" in raw or "hospitality" in raw:
        return "hospitality"
    if "logistic" in raw or "transport" in raw or "vervoer" in raw or "warehouse" in raw:
        return "logistics"
    if "manufact" in raw or "industri" in raw or "productie" in raw:
        return "manufacturing"
    if "service" in raw or "consult" in raw or "advies" in raw:
        return "services"
    return "other"


def _is_lease_code(code: str) -> bool:
    for prefix in _LEASE_MAR_PREFIXES | _LEASE_RGS_PREFIXES:
        if code.startswith(prefix):
            return True
    return False


def _is_finance_lease_description(description: str) -> bool:
    lower = description.lower()
    return any(s in lower for s in _FINANCE_LEASE_SIGNALS)


def _is_operating_lease_description(description: str) -> bool:
    lower = description.lower()
    return any(s in lower for s in _LEASE_DESCRIPTION_SIGNALS)


# ---------------------------------------------------------------------------
# Public data types
# ---------------------------------------------------------------------------


@dataclass
class LeaseLine:
    """A single operating lease line identified in the trial balance."""

    ledger_code: str
    ledger_name: str
    annual_amount: float
    ifrs16_ebitda_addback: float
    lease_type_hint: str        # "premises" | "vehicle" | "equipment" | "other"
    gaap_regime: str            # "be_gaap_sme" | "nl_gaap_sme" | "ifrs" | "unknown"
    already_capitalized: bool   # True if this is a finance lease (skip add-back)
    confidence: float
    rationale: str
    year: int | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "ledger_code": self.ledger_code,
            "ledger_name": self.ledger_name,
            "annual_amount": self.annual_amount,
            "ifrs16_ebitda_addback": self.ifrs16_ebitda_addback,
            "lease_type_hint": self.lease_type_hint,
            "gaap_regime": self.gaap_regime,
            "already_capitalized": self.already_capitalized,
            "confidence": self.confidence,
            "rationale": self.rationale,
            "year": self.year,
        }


@dataclass
class LeaseNormalizationResult:
    """Full IFRS 16 normalization result for one financial year."""

    year: int | None
    lease_lines: list[LeaseLine] = field(default_factory=list)
    total_operating_lease_expense: float = 0.0
    total_ifrs16_ebitda_addback: float = 0.0
    reported_ebitda: float | None = None
    ifrs16_adjusted_ebitda: float | None = None
    lease_as_pct_of_revenue: float | None = None
    sector_benchmark_pct: float | None = None
    is_lease_intensive: bool = False
    gaap_regime: str = "unknown"
    gaap_regime_note: str = ""
    explanation: str = ""
    materiality_flag: bool = False
    materiality_note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "year": self.year,
            "lease_lines": [l.to_dict() for l in self.lease_lines],
            "total_operating_lease_expense": self.total_operating_lease_expense,
            "total_ifrs16_ebitda_addback": self.total_ifrs16_ebitda_addback,
            "reported_ebitda": self.reported_ebitda,
            "ifrs16_adjusted_ebitda": self.ifrs16_adjusted_ebitda,
            "lease_as_pct_of_revenue": self.lease_as_pct_of_revenue,
            "sector_benchmark_pct": self.sector_benchmark_pct,
            "is_lease_intensive": self.is_lease_intensive,
            "gaap_regime": self.gaap_regime,
            "gaap_regime_note": self.gaap_regime_note,
            "explanation": self.explanation,
            "materiality_flag": self.materiality_flag,
            "materiality_note": self.materiality_note,
        }


# ---------------------------------------------------------------------------
# Normalizer
# ---------------------------------------------------------------------------


class LeaseNormalizer:
    """
    Identifies operating leases in the P&L and computes the IFRS 16 EBITDA
    add-back for comparability purposes between BE/NL GAAP and IFRS.
    """

    MATERIALITY_THRESHOLD_PCT = Decimal("0.05")

    def normalize(
        self,
        entries: list[dict[str, Any]],
        *,
        revenue: Decimal | int | float | str | None,
        reported_ebitda: Decimal | int | float | str | None = None,
        industry: str | None = None,
        country: str | None = None,
        year: int | None = None,
    ) -> LeaseNormalizationResult:
        """
        Identify operating lease lines and compute the IFRS 16 EBITDA add-back.

        Args:
            entries: Trial balance entries (account_code, description, balance).
            revenue: Annual revenue (for benchmark comparison and materiality check).
            reported_ebitda: If provided, compute IFRS 16-adjusted EBITDA.
            industry: Sector label for benchmark selection.
            country: "BE" or "NL" — determines the GAAP regime note.
            year: Financial year label.

        Returns:
            LeaseNormalizationResult with per-line details and total EBITDA impact.
        """
        revenue_d = to_decimal(revenue or 0)
        reported_ebitda_d = to_decimal(reported_ebitda) if reported_ebitda is not None else None
        sector = _sector_key(industry)
        gaap_regime, gaap_note = self._derive_gaap_regime(country)

        lease_lines: list[LeaseLine] = []

        for entry in entries:
            code = str(entry.get("account_code") or "").strip()
            description = str(entry.get("description") or "").strip()
            amount = abs(to_decimal(entry.get("balance") or 0))

            if amount <= 0:
                continue

            line = self._evaluate_entry(
                code=code,
                description=description,
                amount=amount,
                year=year,
                gaap_regime=gaap_regime,
            )
            if line is not None:
                lease_lines.append(line)

        # Only operating (non-capitalized) leases contribute to EBITDA add-back
        operating_lines = [l for l in lease_lines if not l.already_capitalized]
        total_op_lease = sum(l.annual_amount for l in operating_lines)
        total_addback = sum(l.ifrs16_ebitda_addback for l in operating_lines)

        ifrs16_ebitda: float | None = None
        if reported_ebitda_d is not None:
            ifrs16_ebitda = float(
                from_decimal(bank_round(reported_ebitda_d + to_decimal(total_addback)))
            )

        lease_pct: float | None = None
        is_intensive = False
        if revenue_d > 0 and total_op_lease > 0:
            lease_pct = round(total_op_lease / float(revenue_d) * 100, 2)
            bench = _LEASE_SECTOR_BENCHMARKS.get(sector, _LEASE_SECTOR_BENCHMARKS["other"])
            is_intensive = to_decimal(total_op_lease) / revenue_d > bench[0]

        bench_pct = _LEASE_SECTOR_BENCHMARKS.get(sector, _LEASE_SECTOR_BENCHMARKS["other"])[0]

        # Materiality check
        materiality_flag = False
        materiality_note = ""
        if reported_ebitda_d is not None and reported_ebitda_d != 0 and total_addback > 0:
            impact_pct = abs(to_decimal(total_addback) / reported_ebitda_d)
            if impact_pct >= self.MATERIALITY_THRESHOLD_PCT:
                materiality_flag = True
                materiality_note = (
                    f"IFRS 16 add-back of €{total_addback:,.0f} represents "
                    f"{float(impact_pct):.1%} of reported EBITDA — material adjustment. "
                    "Advisors should disclose both GAAP and IFRS 16 EBITDA in the report."
                )

        explanation = self._build_explanation(
            lease_lines=operating_lines,
            total_addback=total_addback,
            lease_pct=lease_pct,
            bench_pct=float(bench_pct),
            gaap_regime=gaap_regime,
            gaap_note=gaap_note,
            sector=sector,
        )

        return LeaseNormalizationResult(
            year=year,
            lease_lines=lease_lines,
            total_operating_lease_expense=round(total_op_lease, 2),
            total_ifrs16_ebitda_addback=round(total_addback, 2),
            reported_ebitda=float(from_decimal(bank_round(reported_ebitda_d))) if reported_ebitda_d is not None else None,
            ifrs16_adjusted_ebitda=ifrs16_ebitda,
            lease_as_pct_of_revenue=lease_pct,
            sector_benchmark_pct=float(from_decimal(bank_round(bench_pct * Decimal("100")))),
            is_lease_intensive=is_intensive,
            gaap_regime=gaap_regime,
            gaap_regime_note=gaap_note,
            explanation=explanation,
            materiality_flag=materiality_flag,
            materiality_note=materiality_note,
        )

    # ------------------------------------------------------------------

    def _evaluate_entry(
        self,
        *,
        code: str,
        description: str,
        amount: Decimal,
        year: int | None,
        gaap_regime: str,
    ) -> LeaseLine | None:
        is_lease_code = _is_lease_code(code)
        is_lease_desc = _is_operating_lease_description(description)

        if not (is_lease_code or is_lease_desc):
            return None

        already_capitalized = _is_finance_lease_description(description)

        lease_type = self._infer_lease_type(code, description)
        label = description or f"MAR {code}"

        if already_capitalized:
            conf = 0.90
            rationale = (
                f"{label} (€{float(amount):,.0f}) appears to be a finance lease "
                "(already capitalized). No IFRS 16 EBITDA add-back — depreciation and "
                "interest are already below the EBITDA line."
            )
            addback = Decimal("0")
        else:
            conf = 0.85 if (is_lease_code and is_lease_desc) else 0.65
            addback = amount
            rationale = (
                f"{label} (€{float(amount):,.0f}) is an operating lease expense booked "
                f"above EBITDA under {gaap_regime}. "
                f"Under IFRS 16, this converts to depreciation (RoU asset) + interest "
                f"(lease liability), both below EBITDA. "
                f"IFRS 16 EBITDA add-back: €{float(addback):,.0f}. "
                f"Per IASB IFRS 16 (2016) and EY lease valuation guidance (2023)."
            )

        return LeaseLine(
            ledger_code=code,
            ledger_name=label,
            annual_amount=float(from_decimal(bank_round(amount))),
            ifrs16_ebitda_addback=float(from_decimal(bank_round(addback))),
            lease_type_hint=lease_type,
            gaap_regime=gaap_regime,
            already_capitalized=already_capitalized,
            confidence=conf,
            rationale=rationale,
            year=year,
        )

    def _infer_lease_type(self, code: str, description: str) -> str:
        lower = description.lower()
        if any(s in lower for s in ("auto", "wagen", "voertuig", "vehicle", "car", "fleet")):
            return "vehicle"
        if any(s in lower for s in ("machine", "equipment", "materiaal", "toestel")):
            return "equipment"
        if any(s in lower for s in ("kantoor", "bureau", "office", "pand", "winkelpand", "gebouw")):
            return "premises"
        if code.startswith(("6112", "4130")):
            return "vehicle"
        if code.startswith(("6113", "6114")):
            return "equipment"
        if code.startswith(("611", "4120", "4121", "4122", "4123", "4124", "4125")):
            return "premises"
        return "other"

    def _derive_gaap_regime(self, country: str | None) -> tuple[str, str]:
        c = (country or "").strip().upper()
        if c in ("BE", "BEL", "BELGIUM"):
            return (
                "be_gaap_sme",
                "Belgian SMEs apply Belgian GAAP (W.Venn/IFRS optional). "
                "Operating leases are expensed above EBITDA under W.Venn art. III:90. "
                "IFRS 16 applies only if the entity voluntarily adopts IFRS. "
                "Per CBN/CNC advies 2019/4.",
            )
        if c in ("NL", "NLD", "NETHERLANDS"):
            return (
                "nl_gaap_sme",
                "Dutch SMEs apply NL GAAP (RJ/BW2). "
                "Operating leases are expensed above EBITDA under RJ 292. "
                "IFRS 16 applies only to IFRS reporters. "
                "Per RJ 292.101 (2023).",
            )
        return (
            "unknown",
            "GAAP regime not specified. Assuming operating leases are expensed above EBITDA. "
            "Confirm with the advisor whether IFRS 16 has been applied.",
        )

    def _build_explanation(
        self,
        *,
        lease_lines: list[LeaseLine],
        total_addback: float,
        lease_pct: float | None,
        bench_pct: float,
        gaap_regime: str,
        gaap_note: str,
        sector: str,
    ) -> str:
        if not lease_lines:
            return (
                "No operating lease lines detected in this trial balance. "
                "No IFRS 16 EBITDA add-back is required."
            )

        pct_str = f"{lease_pct:.1f}% of revenue" if lease_pct is not None else "amount unknown"
        regime_label = {
            "be_gaap_sme": "Belgian GAAP (SME)",
            "nl_gaap_sme": "Dutch GAAP (NL GAAP)",
            "ifrs": "IFRS",
        }.get(gaap_regime, gaap_regime)

        return (
            f"Detected {len(lease_lines)} operating lease line(s) totalling €{total_addback:,.0f} "
            f"({pct_str}). Sector benchmark for {sector}: ~{bench_pct:.1f}% of revenue. "
            f"Under {regime_label}, these are P&L expenses above EBITDA. "
            f"IFRS 16 add-back would increase EBITDA by €{total_addback:,.0f}. "
            f"This is presented for buyer/seller comparability — advisor must confirm "
            f"inclusion in the final normalization schedule. "
            f"{gaap_note}"
        )


# ---------------------------------------------------------------------------
# Convenience function
# ---------------------------------------------------------------------------


def normalize_leases(
    entries: list[dict[str, Any]],
    *,
    revenue: Decimal | int | float | str | None,
    reported_ebitda: Decimal | int | float | str | None = None,
    industry: str | None = None,
    country: str | None = None,
    year: int | None = None,
) -> dict[str, Any]:
    """
    Convenience wrapper — returns `to_dict()` of the LeaseNormalizationResult.
    """
    normalizer = LeaseNormalizer()
    result = normalizer.normalize(
        entries,
        revenue=revenue,
        reported_ebitda=reported_ebitda,
        industry=industry,
        country=country,
        year=year,
    )
    return result.to_dict()
