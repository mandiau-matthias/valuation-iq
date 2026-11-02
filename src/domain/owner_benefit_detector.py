"""
Owner Pension and Personal Benefit Detector — IPT/VAPZ Normalization

Detects and normalizes owner-manager pension contributions, personal insurance,
company car private use, and other personal benefits running through the company
P&L. Second-most-common normalization category after direct owner compensation.

Categories detected:
1. IPT (Individuele Pensioentoezegging) — employer pension commitment
2. VAPZ (Vrij Aanvullend Pensioen Zelfstandigen) — self-employed supplementary pension
3. Groepsverzekering / group insurance — hospitalisatie (DKV) + life cover
4. Company car private use — vehicle lease with personal use component
5. Home office — partial domestic costs charged to the company
6. Personal membership fees — clubs, associations beyond business purpose

Belgian regulatory context:
- IPT: deductible up to the 80% rule (RIB/règle des 80%). Typical: €15,000–€40,000/yr
- VAPZ: statutory ceiling €3,987.58/yr (2025, inflation-indexed)
- Hospitalisatie (DKV): €1,200–€3,500/yr per insured person
- Company car BIK: 30–85% personal depending on vehicle type and commute distance
- Home office: 20–30% of utility/rent typically personal

Dutch equivalents (post-2017 pensioen-eigen-beheer abolition):
- Lijfrentepremie (Box 1 personal, occasionally mixed): flag only
- Arbeidsongeschiktheidsverzekering (AOV): legitimate business cost — do not flag
- Bedrijfswagen prive-gebruik: 22% fiscal add-back on catalogue value

All findings carry a suggested advisor question and a proposed EBITDA add-back.
The advisor confirms and includes in the normalization schedule — this module
never auto-applies without confirmation.

Academic basis:
- CBN/CNC advies 2019/7: IPT en VAPZ in de jaarrekening van de vennootschap
- KBO/FOD Financiën (2025): Maximale aftrekbaarheid groepsverzekering
- Deloitte Belgium (2024): "Owner compensation normalization — M&A due diligence"
- IBBA Market Pulse (2024): Benefit normalization in SME transactions
- Pratt & Niculita (2008): "Valuing a Business" — owner benefit add-backs

Belgian MAR codes in scope:
  635x — Werkgeversbijdragen pensioenen (IPT, groepsverzekering)
  641x — VAPZ / zelfstandigenpensioenen
  640x — RSZ-bijdragen (partially: hospitalisatie component)
  622x — Voordelen in natura / bezoldigingen in natura (car, home office)
  6122 — Voertuigkosten / leasing (company car private use)
  615x — Kosten kantoor aan huis
  650x — Contributies / lidmaatschapsbijdragen (personal membership)

Dutch RGS codes in scope:
  4310 — Pensioenlasten werkgever
  4320 — Overige sociale lasten (including ziektekostenverzekering)
  4130 — Wagenpark prive-gebruik
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from src.utils.decimal_helpers import bank_round, from_decimal, to_decimal
from src.utils.logging import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Signal vocabulary
# ---------------------------------------------------------------------------

_IPT_VAPZ_SIGNALS = frozenset(
    [
        "ipt", "individuele pensioentoezegging", "vapz", "vrij aanvullend pensioen",
        "pensioen", "pension", "groepsverzekering", "group insurance",
        "aanvullend pensioen", "retraite complémentaire", "assurance groupe",
        "pensioenopbouw", "pensioenplan", "pensioenreglement",
        "werknemerspensioen", "bedrijfspensioen",
    ]
)

_HOSPITALISATIE_SIGNALS = frozenset(
    [
        "hospitalisatie", "hospitalisation", "ziekenhuisverzekering",
        "dkv", "hospitalisation assurance", "gezondheidsverzekering",
        "health insurance", "hospitaalverzekering", "medische kosten",
        "medicale kosten", "ziekteverzekering", "zorgverzekering",
        "mutualiteit", "mutuele",
    ]
)

_LIFE_INSURANCE_SIGNALS = frozenset(
    [
        "levensverzekering", "assurance vie", "overlijdensverzekering",
        "life insurance", "lijfrente", "tak 21", "tak 23", "branch 21",
        "verzekering zaakvoerder", "kmo verzekering",
    ]
)

_COMPANY_CAR_SIGNALS = frozenset(
    [
        "leasing wagen", "leasing voertuig", "auto", "wagen", "car",
        "fleet", "wagenpark", "mobiliteitsvergoeding", "lease auto",
        "company car", "bedrijfswagen", "voertuigleasing", "car lease",
        "brandstof", "fuel", "tankkaart", "autokosten", "autoversekering",
    ]
)

_HOME_OFFICE_SIGNALS = frozenset(
    [
        "thuiskantoor", "bureau aan huis", "home office", "privégedeelte",
        "gedeeltelijk privé", "kantoor thuis", "kosten thuis",
        "appartement", "woning", "habitation partielle",
    ]
)

_MEMBERSHIP_SIGNALS = frozenset(
    [
        "lidmaatschap", "membership", "contribution", "cotisation",
        "golf", "tennis", "club", "rotary", "lions", "sportclub",
        "abonnement privé", "privéabonnement", "persoonlijk abonnement",
    ]
)

# MAR account code → initial category hint
_MAR_CATEGORY_MAP: dict[str, str] = {
    "635": "pension_insurance",    # Werkgeversbijdragen pensioenen
    "6350": "pension_insurance",
    "6351": "pension_insurance",
    "6352": "hospitalisatie",
    "6353": "life_insurance",
    "641": "vapz_pension",
    "6410": "vapz_pension",
    "640": "pension_insurance",    # RSZ can include hospitalisatie
    "622": "personal_benefit",     # Voordelen in natura
    "6220": "personal_benefit",
    "6221": "company_car",
    "6122": "company_car",         # Voertuigkosten
    "615": "home_office",
    "6150": "home_office",
    "650": "membership",           # Contributies
    "6500": "membership",
    # NL RGS
    "4310": "pension_insurance",
    "4320": "hospitalisatie",
    "4130": "company_car",
}

# Annual amount benchmarks per category (median expected, std) in EUR
_AMOUNT_BENCHMARKS: dict[str, tuple[Decimal, Decimal]] = {
    "pension_insurance":  (Decimal("22000"), Decimal("12000")),  # IPT median
    "vapz_pension":       (Decimal("3988"),  Decimal("1000")),   # VAPZ cap
    "hospitalisatie":     (Decimal("2200"),  Decimal("800")),    # per person
    "life_insurance":     (Decimal("3500"),  Decimal("1500")),
    "company_car":        (Decimal("12000"), Decimal("6000")),   # lease cost
    "home_office":        (Decimal("4000"),  Decimal("2000")),
    "membership":         (Decimal("1500"),  Decimal("1000")),
    "personal_benefit":   (Decimal("5000"),  Decimal("3000")),
}

# Proposed add-back fraction: what portion is typically personal
_PERSONAL_USE_FRACTION: dict[str, Decimal] = {
    "pension_insurance":  Decimal("1.00"),   # full add-back (normalised out)
    "vapz_pension":       Decimal("1.00"),
    "hospitalisatie":     Decimal("1.00"),
    "life_insurance":     Decimal("1.00"),
    "company_car":        Decimal("0.60"),   # 60% personal use (conservative)
    "home_office":        Decimal("0.25"),   # 25% personal component
    "membership":         Decimal("0.80"),   # usually mostly personal
    "personal_benefit":   Decimal("0.70"),
}

_CATEGORY_LABELS: dict[str, str] = {
    "pension_insurance": "IPT / groepsverzekering",
    "vapz_pension":      "VAPZ / zelfstandigenpensioen",
    "hospitalisatie":    "Hospitalisatieverzekering",
    "life_insurance":    "Levensverzekering",
    "company_car":       "Bedrijfswagen privégebruik",
    "home_office":       "Thuiskantoor privégedeelte",
    "membership":        "Persoonlijk lidmaatschap",
    "personal_benefit":  "Voordeel in natura",
}


# ---------------------------------------------------------------------------
# Public data types
# ---------------------------------------------------------------------------


@dataclass
class OwnerBenefitFinding:
    """A single owner benefit finding with normalization proposal."""

    ledger_code: str
    ledger_name: str
    amount: float
    category: str
    category_label: str
    confidence: float
    rationale: str
    proposed_ebitda_adjustment: float
    personal_use_fraction: float
    year: int | None
    suggested_question: str
    audit_sources: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ledger_code": self.ledger_code,
            "ledger_name": self.ledger_name,
            "amount": self.amount,
            "category": self.category,
            "category_label": self.category_label,
            "confidence": self.confidence,
            "rationale": self.rationale,
            "proposed_ebitda_adjustment": self.proposed_ebitda_adjustment,
            "personal_use_fraction": self.personal_use_fraction,
            "year": self.year,
            "suggested_question": self.suggested_question,
            "audit_sources": self.audit_sources,
        }


@dataclass
class OwnerBenefitDetectionResult:
    """Aggregate result of owner benefit scan for one financial year."""

    year: int | None
    findings: list[OwnerBenefitFinding] = field(default_factory=list)
    total_proposed_ebitda_adjustment: float = 0.0
    high_confidence_count: int = 0
    vapz_cap_breach: bool = False
    explanation: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "year": self.year,
            "findings": [f.to_dict() for f in self.findings],
            "total_proposed_ebitda_adjustment": self.total_proposed_ebitda_adjustment,
            "high_confidence_count": self.high_confidence_count,
            "vapz_cap_breach": self.vapz_cap_breach,
            "explanation": self.explanation,
        }


# ---------------------------------------------------------------------------
# Detector
# ---------------------------------------------------------------------------

_VAPZ_ANNUAL_CAP = Decimal("3987.58")  # 2025 statutory ceiling
_HIGH_CONFIDENCE_THRESHOLD = Decimal("0.70")


class OwnerBenefitDetector:
    """
    Scans a trial balance for owner pension contributions and personal benefit
    items, proposing EBITDA normalizations with full audit trail.

    Designed as a propose-only engine: findings surface in the EngineCoPilot
    rail and require explicit advisor acknowledgement before inclusion in the
    normalization schedule.
    """

    def scan(
        self,
        entries: list[dict[str, Any]],
        *,
        year: int | None = None,
        owner_count: int = 1,
        country: str | None = None,
    ) -> OwnerBenefitDetectionResult:
        """
        Scan trial balance for owner benefit items.

        Args:
            entries: Trial balance entries (account_code, description, balance).
            year: Financial year for audit trail.
            owner_count: Number of owner-managers (affects hospitalisatie benchmark).
            country: "BE" or "NL" for jurisdiction-specific benchmarks.

        Returns:
            OwnerBenefitDetectionResult with per-finding proposals.
        """
        country_upper = (country or "BE").strip().upper()
        findings: list[OwnerBenefitFinding] = []

        for entry in entries:
            code = str(entry.get("account_code") or "").strip()
            description = str(entry.get("description") or "").strip()
            amount = abs(to_decimal(entry.get("balance") or 0))

            if amount <= 0:
                continue

            finding = self._evaluate_entry(
                code=code,
                description=description,
                amount=amount,
                year=year,
                owner_count=owner_count,
                country=country_upper,
            )
            if finding is not None:
                findings.append(finding)

        findings.sort(key=lambda f: (-f.confidence, -f.proposed_ebitda_adjustment))

        total_adj = sum(f.proposed_ebitda_adjustment for f in findings)
        high_conf = sum(
            1 for f in findings if f.confidence >= float(_HIGH_CONFIDENCE_THRESHOLD)
        )

        # VAPZ cap breach check
        vapz_total = sum(
            f.amount for f in findings if f.category == "vapz_pension"
        )
        vapz_cap_breach = (
            to_decimal(vapz_total) > _VAPZ_ANNUAL_CAP * to_decimal(owner_count)
        )

        explanation = self._build_explanation(
            findings=findings,
            total_adj=total_adj,
            high_conf=high_conf,
            vapz_cap_breach=vapz_cap_breach,
            owner_count=owner_count,
        )

        return OwnerBenefitDetectionResult(
            year=year,
            findings=findings,
            total_proposed_ebitda_adjustment=round(total_adj, 2),
            high_confidence_count=high_conf,
            vapz_cap_breach=vapz_cap_breach,
            explanation=explanation,
        )

    # ------------------------------------------------------------------

    def _evaluate_entry(
        self,
        *,
        code: str,
        description: str,
        amount: Decimal,
        year: int | None,
        owner_count: int,
        country: str,
    ) -> OwnerBenefitFinding | None:
        category, conf = self._classify(code, description)
        if category is None:
            return None

        category = self._refine_category(category, description)
        personal_fraction = _PERSONAL_USE_FRACTION.get(category, Decimal("1.00"))
        proposed_adj = amount * personal_fraction

        benchmark_median, _ = _AMOUNT_BENCHMARKS.get(
            category, (Decimal("5000"), Decimal("2000"))
        )
        # Hospitalisation benchmark scales with owner count
        if category == "hospitalisatie":
            benchmark_median = benchmark_median * to_decimal(owner_count)

        # Boost confidence when amount is in expected range
        if amount <= benchmark_median * Decimal("2.5"):
            conf = min(Decimal("0.90"), conf + Decimal("0.08"))

        if conf < Decimal("0.40"):
            return None

        label = description or f"MAR {code}"
        cat_label = _CATEGORY_LABELS.get(category, category)
        sources = self._sources_for(category, country)
        rationale = self._rationale(
            label=label,
            amount=amount,
            category=category,
            cat_label=cat_label,
            personal_fraction=personal_fraction,
            proposed_adj=proposed_adj,
            conf=conf,
            country=country,
            benchmark_median=benchmark_median,
        )
        question = self._question(label, category, cat_label, proposed_adj)

        return OwnerBenefitFinding(
            ledger_code=code,
            ledger_name=label,
            amount=float(from_decimal(bank_round(amount))),
            category=category,
            category_label=cat_label,
            confidence=float(from_decimal(bank_round(conf))),
            rationale=rationale,
            proposed_ebitda_adjustment=float(from_decimal(bank_round(proposed_adj))),
            personal_use_fraction=float(from_decimal(bank_round(personal_fraction))),
            year=year,
            suggested_question=question,
            audit_sources=sources,
        )

    def _classify(self, code: str, description: str) -> tuple[str | None, Decimal]:
        """Return (category, base_confidence) or (None, 0)."""
        code_cat = None
        for prefix in (code[:4], code[:3]):
            if prefix in _MAR_CATEGORY_MAP:
                code_cat = _MAR_CATEGORY_MAP[prefix]
                break

        lower = description.lower()
        desc_ipt = any(s in lower for s in _IPT_VAPZ_SIGNALS)
        desc_hosp = any(s in lower for s in _HOSPITALISATIE_SIGNALS)
        desc_life = any(s in lower for s in _LIFE_INSURANCE_SIGNALS)
        desc_car = any(s in lower for s in _COMPANY_CAR_SIGNALS)
        desc_home = any(s in lower for s in _HOME_OFFICE_SIGNALS)
        desc_memb = any(s in lower for s in _MEMBERSHIP_SIGNALS)

        # Code + matching description → high confidence
        if code_cat and (desc_ipt or desc_hosp or desc_life or desc_car or desc_home or desc_memb):
            return code_cat, Decimal("0.78")

        # Code signal alone → medium confidence
        if code_cat:
            return code_cat, Decimal("0.55")

        # Description signal on generic code
        if desc_ipt:
            return "pension_insurance", Decimal("0.65")
        if desc_hosp:
            return "hospitalisatie", Decimal("0.65")
        if desc_life:
            return "life_insurance", Decimal("0.60")
        if desc_car:
            return "company_car", Decimal("0.55")
        if desc_home:
            return "home_office", Decimal("0.50")
        if desc_memb:
            return "membership", Decimal("0.52")

        return None, Decimal("0")

    def _refine_category(self, category: str, description: str) -> str:
        """Refine a broad code category using description signals."""
        lower = description.lower()
        if category in ("pension_insurance", "personal_benefit"):
            if any(s in lower for s in _HOSPITALISATIE_SIGNALS):
                return "hospitalisatie"
            if any(s in lower for s in _LIFE_INSURANCE_SIGNALS):
                return "life_insurance"
            if any(s in lower for s in _IPT_VAPZ_SIGNALS):
                if "vapz" in lower:
                    return "vapz_pension"
                return "pension_insurance"
        if category == "company_car" or any(s in lower for s in _COMPANY_CAR_SIGNALS):
            return "company_car"
        if any(s in lower for s in _HOME_OFFICE_SIGNALS):
            return "home_office"
        if any(s in lower for s in _MEMBERSHIP_SIGNALS):
            return "membership"
        return category

    def _sources_for(self, category: str, country: str) -> list[str]:
        sources = [
            "Pratt & Niculita (2008): Valuing a Business — owner benefit add-backs",
            "IBBA Market Pulse (2024): SME normalization best practices",
        ]
        if country == "BE":
            sources.append("CBN/CNC advies 2019/7: IPT/VAPZ in SME jaarrekening")
            if category in ("pension_insurance", "vapz_pension"):
                sources.append("KBO/FOD Financiën (2025): Maximale aftrekbaarheid — 80% regel")
            if category == "company_car":
                sources.append("FOD Financiën: Voordeel alle aard bedrijfswagen (2025)")
        elif country == "NL":
            if category in ("pension_insurance", "vapz_pension"):
                sources.append("Wet LB: Pensioenregeling werkgever (2025)")
            if category == "company_car":
                sources.append("Belastingdienst: Bijtelling privégebruik auto van de zaak 22% (2025)")
        return sources

    def _rationale(
        self,
        *,
        label: str,
        amount: Decimal,
        category: str,
        cat_label: str,
        personal_fraction: Decimal,
        proposed_adj: Decimal,
        conf: Decimal,
        country: str,
        benchmark_median: Decimal,
    ) -> str:
        pct_label = f"{float(personal_fraction):.0%}"
        adj_label = f"€{float(proposed_adj):,.0f}"

        if category == "vapz_pension":
            cap_note = (
                f" VAPZ statutory ceiling {float(_VAPZ_ANNUAL_CAP):,.0f} EUR/yr (2025)."
                if amount > _VAPZ_ANNUAL_CAP
                else ""
            )
            return (
                f"{label} (€{float(amount):,.0f}) is a VAPZ self-employed pension contribution. "
                f"Full amount normalized out of EBITDA for M&A comparability.{cap_note} "
                f"Confidence {float(conf):.0%}. Per CBN/CNC advies 2019/7."
            )

        if category == "pension_insurance":
            return (
                f"{label} (€{float(amount):,.0f}) is an IPT/groepsverzekering employer contribution. "
                f"Normalized out in full — buyer will re-price or eliminate this benefit post-close. "
                f"Sector typical: €{float(benchmark_median):,.0f}/yr. "
                f"Confidence {float(conf):.0%}. Per 80% rule (FOD Financiën 2025)."
            )

        if category == "hospitalisatie":
            return (
                f"{label} (€{float(amount):,.0f}) is hospitalisatie / health insurance for the owner. "
                f"Normalized out in full — personal benefit not required in a post-sale entity. "
                f"Confidence {float(conf):.0%}."
            )

        if category == "company_car":
            return (
                f"{label} (€{float(amount):,.0f}) is a company car expense. "
                f"Proposed normalization: {pct_label} personal-use fraction = {adj_label} add-back. "
                f"Conservative estimate — confirm actual private use % with advisor. "
                f"Confidence {float(conf):.0%}."
            )

        if category == "home_office":
            return (
                f"{label} (€{float(amount):,.0f}) includes home-office costs. "
                f"Proposed normalization: {pct_label} personal component = {adj_label} add-back. "
                f"Confirm allocation methodology with advisor. "
                f"Confidence {float(conf):.0%}."
            )

        if category == "membership":
            return (
                f"{label} (€{float(amount):,.0f}) appears to be a personal membership or subscription. "
                f"Proposed {pct_label} add-back = {adj_label}. "
                f"Advisor should confirm business purpose. "
                f"Confidence {float(conf):.0%}."
            )

        return (
            f"{label} (€{float(amount):,.0f}) is a potential owner personal benefit ({cat_label}). "
            f"Proposed normalization: {pct_label} = {adj_label}. "
            f"Confidence {float(conf):.0%}."
        )

    def _question(
        self, label: str, category: str, cat_label: str, proposed_adj: Decimal
    ) -> str:
        templates: dict[str, str] = {
            "pension_insurance": (
                f"Is '{label}' an IPT or groepsverzekering paid on behalf of the owner-manager? "
                "If so, confirm the annual premium and whether it will continue post-sale."
            ),
            "vapz_pension": (
                f"Is '{label}' a VAPZ pension contribution for the self-employed owner? "
                "Full amount should be normalized out of EBITDA."
            ),
            "hospitalisatie": (
                f"Is '{label}' hospitalisatie or health insurance for the owner (and family)? "
                "This is a personal benefit that should be normalized out."
            ),
            "life_insurance": (
                f"Is '{label}' a life insurance premium for the owner? "
                "Confirm beneficiary and whether it is a personal or business policy."
            ),
            "company_car": (
                f"Is '{label}' a company car lease that includes personal use by the owner? "
                f"Estimated personal-use add-back: €{float(proposed_adj):,.0f}. "
                "Please confirm the private-use percentage."
            ),
            "home_office": (
                f"Is '{label}' a home-office cost with a personal component? "
                "Confirm the % allocated to personal use."
            ),
            "membership": (
                f"Is '{label}' a personal membership or subscription for the owner? "
                "If so, the business-unrelated portion should be normalized out."
            ),
        }
        return templates.get(
            category,
            f"Is '{label}' a personal benefit for the owner that should be normalized out of EBITDA?",
        )

    def _build_explanation(
        self,
        *,
        findings: list[OwnerBenefitFinding],
        total_adj: float,
        high_conf: int,
        vapz_cap_breach: bool,
        owner_count: int,
    ) -> str:
        if not findings:
            return (
                "No owner pension or personal benefit items detected in this trial balance. "
                "No benefit add-backs required."
            )
        vapz_note = (
            f" Note: detected VAPZ contributions that may exceed the statutory ceiling "
            f"({float(_VAPZ_ANNUAL_CAP):,.0f} EUR/yr × {owner_count} owner(s))."
            if vapz_cap_breach
            else ""
        )
        return (
            f"Detected {len(findings)} owner benefit item(s) with a total proposed "
            f"EBITDA add-back of €{total_adj:,.0f}. "
            f"{high_conf} finding(s) carry high confidence (≥{float(_HIGH_CONFIDENCE_THRESHOLD):.0%}). "
            f"All findings are propose-only — advisor confirmation required before inclusion "
            f"in the normalization schedule.{vapz_note}"
        )


# ---------------------------------------------------------------------------
# Convenience function
# ---------------------------------------------------------------------------


def scan_for_owner_benefits(
    entries: list[dict[str, Any]],
    *,
    year: int | None = None,
    owner_count: int = 1,
    country: str | None = None,
) -> list[dict[str, Any]]:
    """
    Convenience wrapper — returns list of finding dicts.
    Mirrors sde_flag_scanner / related_party_detector output shape.
    """
    detector = OwnerBenefitDetector()
    result = detector.scan(
        entries,
        year=year,
        owner_count=owner_count,
        country=country,
    )
    return [f.to_dict() for f in result.findings]
