"""
Enhanced Question Detector

Multi-language question detection with domain classification,
false positive filtering, and complexity assessment.
"""

import re
from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Optional


class QuestionType(str, Enum):
    DEFINITION = "definition"
    PURPOSE = "purpose"
    EXAMPLE = "example"
    IMPACT = "impact"
    GENERAL = "general"


class QuestionDomain(str, Enum):
    FINANCIAL = "financial"
    VALUATION = "valuation"
    LEGAL = "legal"
    TAX = "tax"
    GENERAL = "general"


class ComplexityLevel(str, Enum):
    SIMPLE = "simple"
    MODERATE = "moderate"
    COMPLEX = "complex"


class QuestionIntent(str, Enum):
    LEARNING = "learning"
    CLARIFICATION = "clarification"
    CHALLENGE = "challenge"
    CONFIRMATION = "confirmation"


@dataclass
class EnhancedQuestionAnalysis:
    is_question: bool = False
    question_type: QuestionType = QuestionType.GENERAL
    domain: QuestionDomain = QuestionDomain.GENERAL
    complexity: ComplexityLevel = ComplexityLevel.SIMPLE
    intent: QuestionIntent = QuestionIntent.LEARNING
    confidence: Decimal = Decimal("0.0")
    focus_topic: Optional[str] = None
    language: str = "en"


_EN_QUESTION_WORDS = {"what", "why", "how", "when", "where", "which", "who", "whom", "whose", "can", "could", "would", "should", "do", "does", "did", "is", "are", "was", "were", "will"}
_NL_QUESTION_WORDS = {"wat", "waarom", "hoe", "wanneer", "waar", "welke", "wie", "wiens", "kan", "kun", "zou", "moet", "is", "zijn"}
_FR_QUESTION_WORDS = {"qu", "que", "quoi", "pourquoi", "comment", "quand", "où", "quel", "quelle", "qui", "est-ce", "peut", "pouvez"}

_HELP_PHRASES = {"help", "explain", "don't understand", "i don't understand", "don't know", "help me", "tell me"}
_UNCERTAIN_ANSWERS = {"no idea", "i don't know", "not sure", "unsure", "don't know", "dunno", "no clue"}

_FINANCIAL_KEYWORDS = {"ebitda", "revenue", "profit", "margin", "cash flow", "earnings", "income", "expenses", "operating", "net", "gross", "financial", "fiscal", "accounting", "balance sheet", "calculate"}
_VALUATION_KEYWORDS = {"valuation", "multiple", "dcf", "enterprise value", "equity value", "valued", "worth", "business value", "discount", "premium"}
_LEGAL_KEYWORDS = {"legal", "contract", "liability", "compliance", "regulation", "law", "statute", "court", "jurisdiction", "legal structure"}
_TAX_KEYWORDS = {"tax", "vat", "fiscal", "deduction", "withholding", "excise", "tariff"}

_CURRENCY_PATTERN = re.compile(r'^[€$£]?\s*[\d,]+\.?\d*\s*(euro|eur|dollar|usd|gbp)?$', re.IGNORECASE)
_AMOUNT_WITH_UNCERTAINTY = re.compile(r'^(maybe|probably|about|around|approximately|roughly)\s+[\d€$£,]+', re.IGNORECASE)
_DATA_CLARIFICATION = re.compile(r'^what\s+about\s+[€$£]?[\d,]+', re.IGNORECASE)
_HEDGED_ANSWER = re.compile(r'^(not\s+sure|unsure).*\d', re.IGNORECASE)


class QuestionDetector:
    def is_question(self, text: str) -> bool:
        if not text or len(text.strip()) < 2:
            return False

        text_stripped = text.strip()
        lower = text_stripped.lower()

        if _CURRENCY_PATTERN.match(text_stripped):
            return False
        if _AMOUNT_WITH_UNCERTAINTY.match(text_stripped):
            return False
        if _DATA_CLARIFICATION.match(text_stripped):
            return False
        if _HEDGED_ANSWER.match(text_stripped):
            return False

        for phrase in _UNCERTAIN_ANSWERS:
            if lower == phrase or lower.startswith(phrase):
                return False

        if re.match(r'^\d[\d,]*\.?\d*\s*(euro|eur)?$', lower):
            return False

        if text_stripped.endswith("?"):
            return True

        first_word = lower.split()[0] if lower.split() else ""

        if first_word in _EN_QUESTION_WORDS:
            return True
        if first_word in _NL_QUESTION_WORDS:
            return True
        if first_word in _FR_QUESTION_WORDS or lower.startswith("qu'est"):
            return True

        for phrase in _HELP_PHRASES:
            if phrase in lower:
                return True

        return False

    def analyze_question(self, text: str) -> EnhancedQuestionAnalysis:
        if not text or len(text.strip()) < 2:
            return EnhancedQuestionAnalysis(is_question=False, confidence=Decimal("0.0"))

        is_q = self.is_question(text)
        if not is_q:
            return EnhancedQuestionAnalysis(is_question=False, confidence=Decimal("0.0"))

        language = self._detect_language(text)
        q_type = self._classify_type(text)
        domain = self._classify_domain(text)
        complexity = self._assess_complexity(text)
        intent = self._detect_intent(text)
        focus = self._extract_focus(text)
        confidence = self._calculate_confidence(text)

        return EnhancedQuestionAnalysis(
            is_question=True,
            question_type=q_type,
            domain=domain,
            complexity=complexity,
            intent=intent,
            confidence=confidence,
            focus_topic=focus,
            language=language,
        )

    def get_question_type(self, text: str) -> QuestionType:
        return self._classify_type(text)

    def get_confidence(self, text: str) -> float:
        return float(self._calculate_confidence(text))

    def extract_question_focus(self, text: str) -> Optional[str]:
        return self._extract_focus(text)

    def _detect_language(self, text: str) -> str:
        lower = text.lower()
        if lower.startswith("qu'est") or any(w in lower.split() for w in {"pourquoi", "comment", "l'ebitda", "est", "une", "dans", "utilisée", "mesure", "financière"}):
            return "fr"
        nl_indicators = {"wat", "waarom", "hoe", "welke", "wie", "nodig", "werkt", "heeft", "dit"}
        words = set(lower.split())
        if words & nl_indicators:
            return "nl"
        return "en"

    def _classify_type(self, text: str) -> QuestionType:
        lower = text.lower()
        if re.search(r'\bwhat\s+is\b|\bwat\s+is\b|qu\'est.ce', lower):
            return QuestionType.DEFINITION
        if re.search(r'\bwhat\s+does\b.*\bmean\b', lower):
            return QuestionType.DEFINITION
        if re.search(r'\bwhy\b|\bwaarom\b|\bpourquoi\b|\bneed\b', lower):
            return QuestionType.PURPOSE
        if re.search(r'\bexample\b|\bvoorbeeld\b|\bexemple\b', lower):
            return QuestionType.EXAMPLE
        if re.search(r'\bimpact\b|\baffect\b|\binfluence\b|\beffect\b', lower):
            return QuestionType.IMPACT
        if re.search(r'\bhow\b|\bhoe\b|\bcomment\b', lower):
            if re.search(r'\bimpact\b|\baffect\b|\binfluence\b', lower):
                return QuestionType.IMPACT
            return QuestionType.GENERAL
        return QuestionType.GENERAL

    def _classify_domain(self, text: str) -> QuestionDomain:
        lower = text.lower()
        if any(kw in lower for kw in _VALUATION_KEYWORDS):
            return QuestionDomain.VALUATION
        if any(kw in lower for kw in _TAX_KEYWORDS):
            return QuestionDomain.TAX
        if any(kw in lower for kw in _LEGAL_KEYWORDS):
            return QuestionDomain.LEGAL
        if any(kw in lower for kw in _FINANCIAL_KEYWORDS):
            return QuestionDomain.FINANCIAL
        return QuestionDomain.GENERAL

    def _assess_complexity(self, text: str) -> ComplexityLevel:
        lower = text.lower()
        domain_terms = set()
        for kw_set in (_FINANCIAL_KEYWORDS, _VALUATION_KEYWORDS, _LEGAL_KEYWORDS, _TAX_KEYWORDS):
            for kw in kw_set:
                if kw in lower:
                    domain_terms.add(kw)
        if len(domain_terms) >= 2:
            return ComplexityLevel.COMPLEX
        if len(text.split()) > 10:
            return ComplexityLevel.MODERATE
        return ComplexityLevel.SIMPLE

    def _detect_intent(self, text: str) -> QuestionIntent:
        lower = text.lower()
        if any(p in lower for p in ("don't understand", "i don't understand", "help me", "explain", "unclear")):
            return QuestionIntent.CLARIFICATION
        if any(p in lower for p in ("correct", "right", "confirm", "sure")):
            return QuestionIntent.CONFIRMATION
        if any(p in lower for p in ("but", "however", "disagree", "wrong")):
            return QuestionIntent.CHALLENGE
        return QuestionIntent.LEARNING

    def _extract_focus(self, text: str) -> Optional[str]:
        lower = text.lower().strip()
        cleaned = re.sub(r"[?!.,;:]", "", lower)
        cleaned = re.sub(r"^(qu'est-ce que |what is |what does |why do you need |wat is )", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\bl'(\w)", r"\1", cleaned)
        cleaned = re.sub(r"\s+(mean|affect|impact|work|function).*$", "", cleaned)

        words = cleaned.split()
        if not words:
            return None

        focus_candidates = [w for w in words if len(w) > 2 and w not in {"the", "a", "an", "my", "your", "our", "this", "that", "for", "and", "but", "you", "how", "does"}]
        if focus_candidates:
            return focus_candidates[-1].upper()
        return words[-1].upper() if words else None

    def _calculate_confidence(self, text: str) -> Decimal:
        if not text:
            return Decimal("0.0")
        conf = Decimal("0.3")
        if text.strip().endswith("?"):
            conf += Decimal("0.4")
        first_word = text.strip().lower().split()[0] if text.strip().split() else ""
        all_q_words = _EN_QUESTION_WORDS | _NL_QUESTION_WORDS | _FR_QUESTION_WORDS
        if first_word in all_q_words:
            conf += Decimal("0.2")
        return min(conf, Decimal("1.0"))
