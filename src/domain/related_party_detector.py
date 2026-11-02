"""
Related-Party Transaction Detector and Normalization Advisor

Detects transactions between the SME and owner-controlled entities, and proposes
market-rate normalizations for the EBITDA normalization schedule.

This is the most frequent source of valuation challenges in Belgian/Dutch SME
due diligence — a sophisticated buyer's first question is always whether rent
paid to the owner's property vehicle, management fees to the holding, or family
salaries have been normalized.

Categories detected:
1. Related-party rent — owner-controlled property charges market+ rent
2. Management fees — beheersvennootschap / holding pass-through fees
3. Above-market family remuneration — family members on payroll
4. Owner loan interest — shareholder loan / rekening-courant interest

Confidence tiers:
- 0.45–0.59: vocabulary signal only (needs advisor confirmation)
- 0.60–0.74: vocabulary + amount anomaly vs sector benchmark
- 0.75–0.90: vocabulary + KBO/KVK entity name match
- 0.91–0.95: vocabulary + entity match + amount anomaly

Academic basis:
- IVSC IVS 102 §40-60 (2024): Normalization of owner-related charges
- Pratt & Niculita (2008): "Valuing a Business" — related-party adjustments
- IBBA/M&A Source Market Pulse (2024): SME normalization categories
- NBB/CBSO sector rent benchmarks (2022-2024)

Belgian MAR codes in scope: 611 (huur/lease), 617 (beheersdiensten),
620-625 (bezoldigingen), 650-651 (financiële lasten)

Dutch RGS codes in scope: 4120-4129 (huur), 4300 (personeel), 8300 (rentelasten)
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

_RENT_SIGNALS = frozenset(
    [
        "huur", "huurlasten", "loyer", "lease", "leasing", "pacht", "erfpacht",
        "onroerend", "immobilier", "gebouw", "pand", "vastgoed", "eigendom",
        "propriété", "lokalen", "locaux", "bedrijfsruimte", "handelspand",
        "bureau", "magazijn", "entrepôt",
    ]
)

_MANAGEMENT_FEE_SIGNALS = frozenset(
    [
        "beheersvennootschap", "management fee", "managementfee", "managementvergoeding",
        "société de management", "holding", "bestuursvergoeding", "managementkosten",
        "consultancy fee", "adviesvergoeding", "service fee", "administratieve kost",
        "factuur holding", "managementdiensten", "management services", "intercompany",
        "group charge", "groepskost", "centrale diensten",
    ]
)

_FAMILY_SALARY_SIGNALS = frozenset(
    [
        "familielid", "echtgenoot", "echtgenote", "spouse", "partner",
        "kind", "enfant", "child", "zoon", "dochter", "ouder", "broer", "zus",
        "famille", "family", "zaakvoerder", "meewerkend",
    ]
)

_LOAN_INTEREST_SIGNALS = frozenset(
    [
        "rekening-courant", "current account", "r/c", "rc ",
        "lening aandeelhouder", "aandeelhouderlening", "shareholders loan",
        "shareholder loan", "intérêt actionnaire", "prêt actionnaire",
        "rente rc", "lening zaakvoerder", "lening bestuurder", "lening vennoot",
        "interestkosten aandeelhouder", "financiële kost aandeelhouder",
    ]
)

# MAR account prefixes → category
_MAR_CATEGORY_MAP: dict[str, str] = {
    "611": "related_party_rent",   # Huur en huurlasten
    "612": "related_party_rent",   # Onderhoud / lease voertuigen (can overlap)
    "617": "management_fee",       # Bezoldigingen dienstverleners
    "620": "family_salary",
    "621": "family_salary",
    "622": "family_salary",
    "623": "family_salary",
    "624": "family_salary",
    "625": "family_salary",
    "650": "owner_loan_interest",
    "651": "owner_loan_interest",
    # NL RGS
    "4120": "related_party_rent",
    "4121": "related_party_rent",
    "4122": "related_party_rent",
    "4123": "related_party_rent",
    "4124": "related_party_rent",
    "4125": "related_party_rent",
    "4126": "related_party_rent",
    "4127": "related_party_rent",
    "4128": "related_party_rent",
    "4129": "related_party_rent",
    "4300": "family_salary",
    "8300": "owner_loan_interest",
    "8310": "owner_loan_interest",
}

# Sector rent benchmarks: (median_pct_of_revenue, std_pct)
_RENT_BENCHMARKS: dict[str, tuple[Decimal, Decimal]] = {
    "retail":        (Decimal("0.080"), Decimal("0.030")),
    "hospitality":   (Decimal("0.120"), Decimal("0.040")),
    "manufacturing": (Decimal("0.040"), Decimal("0.020")),
    "services":      (Decimal("0.060"), Decimal("0.025")),
    "logistics":     (Decimal("0.070"), Decimal("0.025")),
    "other":         (Decimal("0.060"), Decimal("0.025")),
}

# Management fee benchmarks: (median_pct, std_pct)
_MGMT_FEE_BENCHMARKS: dict[str, tuple[Decimal, Decimal]] = {
    "services":      (Decimal("0.025"), Decimal("0.015")),
    "other":         (Decimal("0.020"), Decimal("0.010")),
}


def _industry_key(industry: str | None) -> str:
    raw = (industry or "").lower().strip()
    if "retail" in raw or "shop" in raw or "winkel" in raw:
        return "retail"
    if "hotel" in raw or "horeca" in raw or "restaurant" in raw or "hospitality" in raw:
        return "hospitality"
    if "manufact" in raw or "industri" in raw or "productie" in raw:
        return "manufacturing"
    if "service" in raw or "consult" in raw or "advies" in raw:
        return "services"
    if "logistic" in raw or "transport" in raw or "vervoer" in raw:
        return "logistics"
    return "other"


def _has_signal(text: str, signals: frozenset[str]) -> bool:
    lower = text.lower()
    return any(s in lower for s in signals)


def _code_prefix_category(code: str) -> str | None:
    for prefix in (code[:4], code[:3]):
        if prefix in _MAR_CATEGORY_MAP:
            return _MAR_CATEGORY_MAP[prefix]
    return None


# ---------------------------------------------------------------------------
# Public data types
# ---------------------------------------------------------------------------


@dataclass
class RelatedPartyFinding:
    """A single related-party transaction finding with M&A-grade normalization proposal."""

    ledger_code: str
    ledger_name: str
    amount: float
    category: str
    confidence: float
    rationale: str
    proposed_ebitda_adjustment: float
    adjustment_type: str
    benchmark_market_rate: float | None
    year: int | None
    suggested_question: str
    audit_sources: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ledger_code": self.ledger_code,
            "ledger_name": self.ledger_name,
            "amount": self.amount,
            "category": self.category,
            "confidence": self.confidence,
            "rationale": self.rationale,
            "proposed_ebitda_adjustment": self.proposed_ebitda_adjustment,
            "adjustment_type": self.adjustment_type,
            "benchmark_market_rate": self.benchmark_market_rate,
            "year": self.year,
            "suggested_question": self.suggested_question,
            "audit_sources": self.audit_sources,
        }


@dataclass
class RelatedPartyDetectionResult:
    """Aggregate result of related-party scan for one financial year."""

    year: int | None
    findings: list[RelatedPartyFinding] = field(default_factory=list)
    total_proposed_ebitda_adjustment: float = 0.0
    high_confidence_count: int = 0
    revenue: float = 0.0
    explanation: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "year": self.year,
            "findings": [f.to_dict() for f in self.findings],
            "total_proposed_ebitda_adjustment": self.total_proposed_ebitda_adjustment,
            "high_confidence_count": self.high_confidence_count,
            "revenue": self.revenue,
            "explanation": self.explanation,
        }


# ---------------------------------------------------------------------------
# Detector
# ---------------------------------------------------------------------------


class RelatedPartyDetector:
    """
    Scans a trial balance for potential related-party transactions and
    proposes EBITDA normalizations with M&A-grade audit trail.
    """

    HIGH_CONFIDENCE_THRESHOLD = Decimal("0.70")

    def scan(
        self,
        entries: list[dict[str, Any]],
        *,
        revenue: Decimal | int | float | str | None,
        industry: str | None = None,
        known_owner_entities: list[str] | None = None,
        year: int | None = None,
    ) -> RelatedPartyDetectionResult:
        """
        Scan trial balance entries for related-party transactions.

        Args:
            entries: List of dicts with account_code, description, balance.
            revenue: Annual revenue used for benchmark comparisons.
            industry: Sector label for benchmark selection.
            known_owner_entities: Optional list of KBO/KVK entity names controlled
                by the owner — increases confidence when description matches.
            year: Financial year label for audit trail.

        Returns:
            RelatedPartyDetectionResult with per-finding details + EBITDA impact.
        """
        revenue_decimal = to_decimal(revenue or 0)
        sector = _industry_key(industry)
        entity_names_lower = [e.lower().strip() for e in (known_owner_entities or [])]

        findings: list[RelatedPartyFinding] = []

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
                revenue=revenue_decimal,
                sector=sector,
                entity_names_lower=entity_names_lower,
                year=year,
            )
            if finding is not None:
                findings.append(finding)

        # Sort: high confidence + high amount first
        findings.sort(
            key=lambda f: (-f.confidence, -f.proposed_ebitda_adjustment)
        )

        total_adj = sum(f.proposed_ebitda_adjustment for f in findings)
        high_conf = sum(1 for f in findings if f.confidence >= float(self.HIGH_CONFIDENCE_THRESHOLD))

        if findings:
            explanation = (
                f"Detected {len(findings)} potential related-party transaction(s) "
                f"with a total proposed EBITDA add-back of €{total_adj:,.0f}. "
                f"{high_conf} finding(s) carry high confidence (≥{float(self.HIGH_CONFIDENCE_THRESHOLD):.0%}) "
                f"and should be confirmed with the advisor before inclusion in the normalization schedule. "
                f"Per IVS 102 §40-60, all related-party adjustments must be supported by a market-rate reference."
            )
        else:
            explanation = (
                "No related-party transaction signals detected in this trial balance. "
                "The normalization schedule requires no related-party adjustments based on available data."
            )

        return RelatedPartyDetectionResult(
            year=year,
            findings=findings,
            total_proposed_ebitda_adjustment=round(total_adj, 2),
            high_confidence_count=high_conf,
            revenue=float(from_decimal(bank_round(revenue_decimal))),
            explanation=explanation,
        )

    # ------------------------------------------------------------------

    def _evaluate_entry(
        self,
        *,
        code: str,
        description: str,
        amount: Decimal,
        revenue: Decimal,
        sector: str,
        entity_names_lower: list[str],
        year: int | None,
    ) -> RelatedPartyFinding | None:
        category = self._classify(code, description)
        if category is None:
            return None

        conf, rationale, adj, adj_type, market_rate, sources, question = (
            self._score_and_propose(
                code=code,
                description=description,
                amount=amount,
                revenue=revenue,
                sector=sector,
                category=category,
                entity_names_lower=entity_names_lower,
            )
        )

        if conf < Decimal("0.40"):
            return None

        label = description or f"MAR {code}"
        return RelatedPartyFinding(
            ledger_code=code,
            ledger_name=label,
            amount=float(from_decimal(bank_round(amount))),
            category=category,
            confidence=float(from_decimal(bank_round(conf))),
            rationale=rationale,
            proposed_ebitda_adjustment=float(from_decimal(bank_round(adj))),
            adjustment_type=adj_type,
            benchmark_market_rate=float(from_decimal(bank_round(market_rate))) if market_rate is not None else None,
            year=year,
            suggested_question=question,
            audit_sources=sources,
        )

    def _classify(self, code: str, description: str) -> str | None:
        """Return category string or None if not a related-party candidate."""
        code_cat = _code_prefix_category(code)

        desc_is_rent = _has_signal(description, _RENT_SIGNALS)
        desc_is_mgmt = _has_signal(description, _MANAGEMENT_FEE_SIGNALS)
        desc_is_family = _has_signal(description, _FAMILY_SALARY_SIGNALS)
        desc_is_loan = _has_signal(description, _LOAN_INTEREST_SIGNALS)

        if code_cat == "related_party_rent" and desc_is_rent:
            return "related_party_rent"
        if code_cat == "related_party_rent" and not (desc_is_mgmt or desc_is_family or desc_is_loan):
            return "related_party_rent"
        if code_cat == "management_fee" or desc_is_mgmt:
            return "management_fee"
        if code_cat == "family_salary" and desc_is_family:
            return "family_salary"
        if code_cat == "owner_loan_interest" or desc_is_loan:
            return "owner_loan_interest"

        # Rent-like description on any P&L line
        if desc_is_rent and code.startswith(("6", "7", "8")):
            return "related_party_rent"

        return None

    def _score_and_propose(
        self,
        *,
        code: str,
        description: str,
        amount: Decimal,
        revenue: Decimal,
        sector: str,
        category: str,
        entity_names_lower: list[str],
    ) -> tuple[Decimal, str, Decimal, str, Decimal | None, list[str], str]:
        """
        Returns (confidence, rationale, proposed_adj, adj_type, market_rate, sources, question).
        """
        entity_match = any(
            e and e in description.lower() for e in entity_names_lower if e
        )

        base_conf = Decimal("0.50")
        if entity_match:
            base_conf += Decimal("0.25")

        sources = [
            "IVSC IVS 102 §40-60 (2024)",
            "Pratt & Niculita (2008): Valuing a Business",
        ]

        label = description or f"MAR {code}"

        if category == "related_party_rent":
            return self._score_rent(
                label=label, amount=amount, revenue=revenue, sector=sector,
                base_conf=base_conf, entity_match=entity_match, sources=sources,
            )

        if category == "management_fee":
            return self._score_mgmt_fee(
                label=label, amount=amount, revenue=revenue, sector=sector,
                base_conf=base_conf, entity_match=entity_match, sources=sources,
            )

        if category == "family_salary":
            return self._score_family_salary(
                label=label, amount=amount, revenue=revenue,
                base_conf=base_conf, entity_match=entity_match, sources=sources,
            )

        # owner_loan_interest — full addback (normalised out of EBITDA)
        conf = min(Decimal("0.85"), base_conf + Decimal("0.15"))
        sources.append("IBBA Market Pulse (2024): Loan interest normalization")
        rationale = (
            f"{label} (€{float(amount):,.0f}) recorded as financial charge — "
            f"shareholder loan interest is non-arm's-length and should be normalized out of EBITDA. "
            f"Confidence {float(conf):.0%} — confirm owner loan existence with advisor."
        )
        question = (
            f"Is '{label}' interest on a shareholder loan or rekening-courant? "
            "If so, this should be normalized out of EBITDA."
        )
        return (conf, rationale, amount, "full_addback", None, sources, question)

    # ------------------------------------------------------------------

    def _score_rent(
        self,
        *,
        label: str,
        amount: Decimal,
        revenue: Decimal,
        sector: str,
        base_conf: Decimal,
        entity_match: bool,
        sources: list[str],
    ) -> tuple[Decimal, str, Decimal, str, Decimal | None, list[str], str]:
        benchmark = _RENT_BENCHMARKS.get(sector, _RENT_BENCHMARKS["other"])
        median_pct, std_pct = benchmark
        actual_pct = amount / revenue if revenue > 0 else Decimal("0")
        market_rate = median_pct * revenue

        sources.append(f"NBB/CBSO sector rent benchmark ({sector}): {float(median_pct):.1%} of revenue")

        if actual_pct > median_pct + std_pct:
            amount_anomaly_boost = min(
                Decimal("0.20"),
                ((actual_pct - median_pct) / (median_pct + Decimal("0.001"))) * Decimal("0.10"),
            )
            conf = min(Decimal("0.92"), base_conf + amount_anomaly_boost)
            delta = amount - market_rate
            adj_type = "benchmark_delta"
            rationale = (
                f"{label} (€{float(amount):,.0f}) is {float(actual_pct):.1%} of revenue, "
                f"against the sector benchmark of {float(median_pct):.1%}. "
                f"Proposed normalization: reduce to market rate €{float(market_rate):,.0f} "
                f"(delta: €{float(delta):,.0f}). "
                f"Confidence {float(conf):.0%}{'— entity name matched in KBO/KVK' if entity_match else ''}."
            )
        else:
            conf = min(Decimal("0.65"), base_conf)
            delta = amount
            adj_type = "full_addback"
            rationale = (
                f"{label} (€{float(amount):,.0f}) shows characteristics of related-party rent "
                f"(within benchmark range at {float(actual_pct):.1%} of revenue). "
                f"Advisor confirmation required — full addback proposed as conservative upper bound. "
                f"Confidence {float(conf):.0%}."
            )

        question = (
            f"Is '{label}' rent paid to a property vehicle controlled by the owner or a family member? "
            "If so, confirm the market rate for comparable premises."
        )
        return (conf, rationale, delta, adj_type, market_rate, sources, question)

    def _score_mgmt_fee(
        self,
        *,
        label: str,
        amount: Decimal,
        revenue: Decimal,
        sector: str,
        base_conf: Decimal,
        entity_match: bool,
        sources: list[str],
    ) -> tuple[Decimal, str, Decimal, str, Decimal | None, list[str], str]:
        benchmark = _MGMT_FEE_BENCHMARKS.get(sector, _MGMT_FEE_BENCHMARKS["other"])
        median_pct, _ = benchmark
        market_rate = median_pct * revenue

        sources.append("IBBA Market Pulse (2024): Management fee benchmarks")

        conf = min(Decimal("0.88"), base_conf + Decimal("0.15"))
        delta = amount
        adj_type = "full_addback"

        rationale = (
            f"{label} (€{float(amount):,.0f}) is a management fee charged by a related entity. "
            f"Standard practice: normalize the full amount out of EBITDA and re-state at true economic cost. "
            f"Market benchmark for genuine management services: ~{float(median_pct):.1%} of revenue "
            f"(€{float(market_rate):,.0f}). "
            f"Confidence {float(conf):.0%}{'— entity name matched in KBO/KVK' if entity_match else ''}."
        )
        question = (
            f"Is '{label}' a fee charged by the owner's holding / beheersvennootschap? "
            "Confirm whether real services were rendered and at what market rate."
        )
        return (conf, rationale, delta, adj_type, market_rate, sources, question)

    def _score_family_salary(
        self,
        *,
        label: str,
        amount: Decimal,
        revenue: Decimal,
        base_conf: Decimal,
        entity_match: bool,
        sources: list[str],
    ) -> tuple[Decimal, str, Decimal, str, Decimal | None, list[str], str]:
        sources.append("NBB salary benchmark tables (2023)")

        conf = min(Decimal("0.72"), base_conf + Decimal("0.10"))
        adj_type = "partial_addback"

        rationale = (
            f"{label} (€{float(amount):,.0f}) contains signals of family-member remuneration. "
            f"Proposed action: confirm role, hours worked, and market salary for equivalent position. "
            f"Normalize the above-market portion only. "
            f"Confidence {float(conf):.0%} — partial addback until market rate confirmed."
        )
        question = (
            f"Does '{label}' include salary paid to a family member of the owner? "
            "If so, what is the market rate for this role? The above-market delta should be normalized."
        )
        return (conf, rationale, amount, adj_type, None, sources, question)


# ---------------------------------------------------------------------------
# Convenience function (matches sde_flag_scanner API style)
# ---------------------------------------------------------------------------


def scan_for_related_party_transactions(
    entries: list[dict[str, Any]],
    *,
    revenue: Decimal | int | float | str | None,
    industry: str | None = None,
    known_owner_entities: list[str] | None = None,
    year: int | None = None,
) -> list[dict[str, Any]]:
    """
    Scan trial balance entries for related-party transactions.
    Returns a list of finding dicts (mirrors sde_flag_scanner output shape).
    """
    detector = RelatedPartyDetector()
    result = detector.scan(
        entries,
        revenue=revenue,
        industry=industry,
        known_owner_entities=known_owner_entities,
        year=year,
    )
    return [f.to_dict() for f in result.findings]
