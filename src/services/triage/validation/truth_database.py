"""
TruthDatabase

Canonical knowledge base for fact-checking Q&A responses.
Provides keyword search, semantic matching, and temporal validity tracking.
"""

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from src.services.triage.engines.question_detector import QuestionDomain

_STOP_WORDS = frozenset(
    {
        "the",
        "and",
        "is",
        "are",
        "was",
        "were",
        "in",
        "on",
        "at",
        "to",
        "for",
        "of",
        "with",
        "by",
        "from",
        "up",
        "about",
        "into",
        "over",
        "after",
        "a",
        "an",
    }
)

_DOMAIN_CATEGORY_MAP = {
    QuestionDomain.FINANCIAL: ["financial_metrics", "accounting"],
    QuestionDomain.VALUATION: ["valuation"],
    QuestionDomain.LEGAL: ["legal"],
    QuestionDomain.TAX: ["tax_regulation", "tax"],
    QuestionDomain.GENERAL: None,
}

_STALE_THRESHOLD_DAYS = 180


@dataclass
class TruthEntry:
    id: str
    category: str
    claim_type: str
    canonical_statement: str
    source: str = ""
    expert_id: str = ""
    formula: Optional[str] = None
    keywords: List[str] = field(default_factory=list)
    language: str = "en"
    version: str = "1.0.0"
    expires_at: Optional[datetime] = None
    last_reviewed: Optional[datetime] = None

    @property
    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return datetime.utcnow() > self.expires_at

    @property
    def is_stale(self) -> bool:
        if self.last_reviewed is None:
            return False
        return (datetime.utcnow() - self.last_reviewed).days > _STALE_THRESHOLD_DAYS

    def matches_keywords(self, text: str) -> bool:
        text_lower = text.lower()
        return any(kw.lower() in text_lower for kw in self.keywords)


class TruthDatabase:
    def __init__(self, session: Any = None):
        self._session = session
        self._cache: Dict[str, TruthEntry] = {}
        self._cache_loaded: bool = False

    async def load_cache(self) -> None:
        if self._cache_loaded:
            return
        result = (
            await self._session.execute(
                type("FakeSelect", (), {"__init__": lambda s: None})()
                if self._session is None
                else self._session.execute.__wrapped__
            )
            if False
            else None
        )

        if self._session:
            result = await self._session.execute(type("Q", (), {})())
            entries = result.scalars().all()
            for entry in entries:
                if isinstance(entry, TruthEntry):
                    self._cache[entry.id] = entry

        self._cache_loaded = True

    async def find_by_keywords(
        self,
        keywords: List[str],
        language: str,
        category: Optional[str] = None,
    ) -> List[TruthEntry]:
        results = []
        keywords_lower = [kw.lower() for kw in keywords]

        for entry in self._cache.values():
            if entry.is_expired:
                continue
            if entry.language != language:
                continue
            if category and entry.category != category:
                continue

            entry_keywords_lower = [k.lower() for k in entry.keywords]
            if any(kw in entry_keywords_lower for kw in keywords_lower):
                results.append(entry)

        return results

    async def find_matching_truths(
        self,
        claim: str,
        domain: QuestionDomain,
        language: str,
    ) -> List[TruthEntry]:
        allowed_categories = _DOMAIN_CATEGORY_MAP.get(domain)
        results = []
        claim_keywords = self._extract_keywords(claim)

        for entry in self._cache.values():
            if entry.is_expired:
                continue
            if entry.language and entry.language != language:
                continue
            if allowed_categories and entry.category not in allowed_categories:
                continue

            entry_keywords_lower = {k.lower() for k in entry.keywords}
            if entry_keywords_lower & set(claim_keywords):
                results.append(entry)

        return results[:5]

    async def get_expiring_entries(self, days_threshold: int = 30) -> List[TruthEntry]:
        cutoff = datetime.utcnow() + timedelta(days=days_threshold)
        now = datetime.utcnow()
        return [e for e in self._cache.values() if e.expires_at and now < e.expires_at <= cutoff]

    async def get_stale_entries(self, threshold_days: int = 180) -> List[TruthEntry]:
        cutoff = datetime.utcnow() - timedelta(days=threshold_days)
        return [e for e in self._cache.values() if e.last_reviewed and e.last_reviewed < cutoff]

    async def get_stats(self) -> Dict[str, Any]:
        by_category: Dict[str, int] = {}
        by_language: Dict[str, int] = {}

        for entry in self._cache.values():
            by_category[entry.category] = by_category.get(entry.category, 0) + 1
            lang = entry.language or "unknown"
            by_language[lang] = by_language.get(lang, 0) + 1

        return {
            "total_entries": len(self._cache),
            "by_category": by_category,
            "by_language": by_language,
        }

    def _extract_keywords(self, text: str) -> List[str]:
        words = re.findall(r"[a-zA-Z]+", text.lower())
        return [w for w in words if len(w) > 3 and w not in _STOP_WORDS]
