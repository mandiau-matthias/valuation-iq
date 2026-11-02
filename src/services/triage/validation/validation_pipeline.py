"""
ValidationPipeline

5-gate validation pipeline for Q&A response validation:
Gate 1: Source Verification
Gate 2: Fact Checking
Gate 3: Context Alignment
Gate 4: Recency Validation
Gate 5: Safety Screening
"""

import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional

from src.services.triage.engines.question_detector import EnhancedQuestionAnalysis, QuestionDomain
from src.services.triage.validation.truth_database import TruthDatabase


class ValidationResult(str, Enum):
    PASS = "pass"
    WARNING = "warning"
    FAIL = "fail"


class ValidationGate(str, Enum):
    SOURCE_VERIFICATION = "source_verification"
    FACT_CHECKING = "fact_checking"
    CONTEXT_ALIGNMENT = "context_alignment"
    RECENCY_VALIDATION = "recency_validation"
    SAFETY_SCREENING = "safety_screening"


@dataclass
class GateResult:
    gate: ValidationGate
    result: ValidationResult
    confidence: Decimal
    evidence: List[str]
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ValidationReport:
    overall_result: ValidationResult
    confidence_score: int
    gate_results: List[GateResult]
    approved_for_delivery: bool = False
    requires_human_review: bool = True
    risk_level: str = "medium"
    disclaimer_required: bool = False
    validation_duration_ms: int = 0


_INVESTMENT_PATTERNS = [
    re.compile(r"\bshould\s+invest\b", re.IGNORECASE),
    re.compile(r"\bbuy\s+(this|the)\s+(stock|share|business)\b", re.IGNORECASE),
    re.compile(r"\binvest\s+immediately\b", re.IGNORECASE),
    re.compile(r"\brecommend\s+(buying|investing)\b", re.IGNORECASE),
]
_LEGAL_ADVICE_PATTERNS = [
    re.compile(r"\bmust\s+legally\b", re.IGNORECASE),
    re.compile(r"\byou\s+are\s+legally\s+required\b", re.IGNORECASE),
    re.compile(r"\blegal\s+obligation\b", re.IGNORECASE),
    re.compile(r"\blegally\s+sign\b", re.IGNORECASE),
]
_GUARANTEE_PATTERNS = [
    re.compile(r"\bguarantee\b", re.IGNORECASE),
    re.compile(r"\b100%\s+certain\b", re.IGNORECASE),
    re.compile(r"\bpromise\s+that\b", re.IGNORECASE),
]
_PII_EMAIL = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
_PII_PHONE = re.compile(r"\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b")

_NL_INDICATORS = {
    "een",
    "het",
    "de",
    "van",
    "voor",
    "wordt",
    "bij",
    "waardering",
    "bedrijven",
    "financiële",
    "maatstaf",
    "gebruikt",
}
_FR_INDICATORS = {
    "est",
    "une",
    "dans",
    "des",
    "les",
    "pour",
    "qui",
    "mesure",
    "financière",
    "utilisée",
    "entreprises",
    "évaluation",
}

_RECENCY_THRESHOLDS = {
    QuestionDomain.TAX: 180,
    QuestionDomain.LEGAL: 365,
    QuestionDomain.FINANCIAL: 365,
    QuestionDomain.VALUATION: 730,
    QuestionDomain.GENERAL: 1000,
}

_FINANCIAL_DOMAIN_KEYWORDS = {
    "ebitda",
    "revenue",
    "profit",
    "margin",
    "cash flow",
    "earnings",
    "financial",
    "income",
}
_VALUATION_DOMAIN_KEYWORDS = {"valuation", "multiple", "dcf", "enterprise value", "equity value"}


class ValidationPipeline:
    def __init__(self, truth_db: TruthDatabase, confidence_threshold: Decimal = Decimal("0.85")):
        self._truth_db = truth_db
        self._confidence_threshold = confidence_threshold

    async def validate(
        self,
        question: str,
        answer: str,
        source: str,
        analysis: EnhancedQuestionAnalysis,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ValidationReport:
        start = time.monotonic()
        metadata = metadata or {}

        g1 = await self._gate_1_source_verification(answer, source, metadata)
        g2 = await self._gate_2_fact_checking(answer, analysis.domain, analysis.language)
        g3 = await self._gate_3_context_alignment(question, answer, analysis)
        g4 = await self._gate_4_recency_validation(answer, analysis.domain, metadata)
        g5 = await self._gate_5_safety_screening(answer, analysis.domain)

        gate_results = [g1, g2, g3, g4, g5]
        overall_result, confidence_score = self._calculate_overall_result(gate_results)

        high_risk_domains = {QuestionDomain.TAX, QuestionDomain.LEGAL}
        is_high_risk = analysis.domain in high_risk_domains
        risk_level = (
            "high"
            if is_high_risk and overall_result != ValidationResult.PASS
            else ("medium" if overall_result == ValidationResult.WARNING else "low")
        )

        approved = overall_result == ValidationResult.PASS and confidence_score >= 85
        needs_review = not approved
        disclaimer = is_high_risk or source == "ai"

        elapsed_ms = max(1, int((time.monotonic() - start) * 1000))

        return ValidationReport(
            overall_result=overall_result,
            confidence_score=confidence_score,
            gate_results=gate_results,
            approved_for_delivery=approved,
            requires_human_review=needs_review,
            risk_level=risk_level,
            disclaimer_required=disclaimer,
            validation_duration_ms=elapsed_ms,
        )

    async def _gate_1_source_verification(
        self, answer: str, source: str, metadata: Dict[str, Any]
    ) -> GateResult:
        if source == "glossary":
            return GateResult(
                ValidationGate.SOURCE_VERIFICATION,
                ValidationResult.PASS,
                Decimal("1.0"),
                ["Glossary source — highest trust"],
            )
        if source == "faq":
            if metadata.get("expert_approved"):
                return GateResult(
                    ValidationGate.SOURCE_VERIFICATION,
                    ValidationResult.PASS,
                    Decimal("0.95"),
                    ["Expert-approved FAQ source"],
                )
            return GateResult(
                ValidationGate.SOURCE_VERIFICATION,
                ValidationResult.WARNING,
                Decimal("0.70"),
                ["FAQ without expert approval — moderate trust"],
            )
        if source == "ai":
            return GateResult(
                ValidationGate.SOURCE_VERIFICATION,
                ValidationResult.WARNING,
                Decimal("0.50"),
                ["AI-generated content — requires verification"],
            )
        return GateResult(
            ValidationGate.SOURCE_VERIFICATION,
            ValidationResult.FAIL,
            Decimal("0.0"),
            ["Unknown source — cannot verify"],
        )

    async def _gate_2_fact_checking(
        self, answer: str, domain: QuestionDomain, language: str
    ) -> GateResult:
        claims = self._extract_factual_claims(answer)
        if not claims:
            return GateResult(
                ValidationGate.FACT_CHECKING,
                ValidationResult.PASS,
                Decimal("0.90"),
                ["No factual claims detected"],
            )

        matches = await self._truth_db.find_matching_truths(answer, domain, language)
        if matches:
            return GateResult(
                ValidationGate.FACT_CHECKING,
                ValidationResult.PASS,
                Decimal("0.85"),
                [f"Verified against {len(matches)} truth entries"],
            )

        return GateResult(
            ValidationGate.FACT_CHECKING,
            ValidationResult.WARNING,
            Decimal("0.50"),
            ["Factual claims could not be verified against truth database"],
        )

    async def _gate_3_context_alignment(
        self, question: str, answer: str, analysis: EnhancedQuestionAnalysis
    ) -> GateResult:
        evidence: List[str] = []
        score = Decimal("0.5")

        answer_lang = self._detect_language(answer)
        q_lang = analysis.language

        if answer_lang == q_lang:
            evidence.append("Language match confirmed")
            score += Decimal("0.2")
        else:
            evidence.append("Language mismatch detected")
            score -= Decimal("0.3")
            if score < Decimal("0"):
                score = Decimal("0")
            return GateResult(
                ValidationGate.CONTEXT_ALIGNMENT, ValidationResult.WARNING, score, evidence
            )

        answer_lower = answer.lower()
        domain_kws = set()
        if analysis.domain == QuestionDomain.FINANCIAL:
            domain_kws = _FINANCIAL_DOMAIN_KEYWORDS
        elif analysis.domain == QuestionDomain.VALUATION:
            domain_kws = _VALUATION_DOMAIN_KEYWORDS
        if domain_kws and any(kw in answer_lower for kw in domain_kws):
            evidence.append("Domain keywords present in answer")
            score += Decimal("0.15")

        if analysis.focus_topic and analysis.focus_topic.lower() in answer_lower:
            evidence.append("Topic present in answer")
            score += Decimal("0.1")
        elif analysis.focus_topic:
            evidence.append("Topic not mentioned in answer")

        score = min(score, Decimal("1.0"))
        result = ValidationResult.PASS if score >= Decimal("0.6") else ValidationResult.WARNING
        return GateResult(ValidationGate.CONTEXT_ALIGNMENT, result, score, evidence)

    async def _gate_4_recency_validation(
        self, answer: str, domain: QuestionDomain, metadata: Dict[str, Any]
    ) -> GateResult:
        last_updated = metadata.get("last_updated")
        threshold_days = _RECENCY_THRESHOLDS.get(domain, 365)

        if last_updated is None:
            return GateResult(
                ValidationGate.RECENCY_VALIDATION,
                ValidationResult.WARNING,
                Decimal("0.70"),
                ["No timestamp available"],
            )

        age_days = (datetime.utcnow() - last_updated).days

        if age_days <= threshold_days:
            return GateResult(
                ValidationGate.RECENCY_VALIDATION,
                ValidationResult.PASS,
                Decimal("1.0"),
                ["Current — updated recently"],
            )
        elif age_days <= threshold_days * 2:
            return GateResult(
                ValidationGate.RECENCY_VALIDATION,
                ValidationResult.WARNING,
                Decimal("0.70"),
                ["Aging — content may need review"],
            )
        else:
            return GateResult(
                ValidationGate.RECENCY_VALIDATION,
                ValidationResult.FAIL,
                Decimal("0.30"),
                ["Stale — content is outdated"],
            )

    async def _gate_5_safety_screening(self, answer: str, domain: QuestionDomain) -> GateResult:
        violations: List[str] = []

        for p in _INVESTMENT_PATTERNS:
            if p.search(answer):
                violations.append("investment_advice")
                break
        for p in _LEGAL_ADVICE_PATTERNS:
            if p.search(answer):
                violations.append("legal_advice")
                break
        for p in _GUARANTEE_PATTERNS:
            if p.search(answer):
                violations.append("guarantees")
                break
        if _PII_EMAIL.search(answer):
            violations.append("pii_email")
        if _PII_PHONE.search(answer):
            violations.append("pii_phone")

        if violations:
            return GateResult(
                ValidationGate.SAFETY_SCREENING,
                ValidationResult.FAIL,
                Decimal("0.0"),
                [f"Safety violations: {', '.join(violations)}"],
                metadata={"violations": violations},
            )

        return GateResult(
            ValidationGate.SAFETY_SCREENING,
            ValidationResult.PASS,
            Decimal("1.0"),
            ["No safety violations detected"],
        )

    def _calculate_overall_result(self, gate_results: List[GateResult]) -> tuple:
        if any(g.result == ValidationResult.FAIL for g in gate_results):
            avg = sum(float(g.confidence) for g in gate_results) / len(gate_results)
            return ValidationResult.FAIL, int(avg * 100)

        if any(g.result == ValidationResult.WARNING for g in gate_results):
            avg = sum(float(g.confidence) for g in gate_results) / len(gate_results)
            return ValidationResult.WARNING, int(avg * 100)

        avg = sum(float(g.confidence) for g in gate_results) / len(gate_results)
        return ValidationResult.PASS, int(avg * 100)

    def _extract_factual_claims(self, answer: str) -> List[str]:
        claims: List[str] = []
        sentences = re.split(r"[.!]\s+", answer)
        for s in sentences:
            s = s.strip()
            if not s:
                continue
            if re.search(r"\b\w+\s+is\s+", s, re.IGNORECASE):
                claims.append(s)
            elif re.search(r"=", s):
                claims.append(s)
            elif re.search(r"\d+%", s):
                claims.append(s)
            elif re.search(r"\b(formula|rate|rule)\b", s, re.IGNORECASE):
                claims.append(s)
            elif re.search(r"\b(Netherlands|Belgium|France|Germany)\b", s):
                claims.append(s)
            elif re.search(r"\bmeans?\b", s, re.IGNORECASE):
                claims.append(s)
        return claims

    def _detect_language(self, text: str) -> str:
        words = set(text.lower().split())
        nl_score = len(words & _NL_INDICATORS)
        fr_score = len(words & _FR_INDICATORS)
        if fr_score >= 3:
            return "fr"
        if nl_score >= 3:
            return "nl"
        return "en"
