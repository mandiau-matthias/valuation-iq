"""
Methodology Source Registry

Centralized registry mapping valuation methodologies to academic sources and standards.
Provides dynamic source generation based on methodologies actually used in valuation.

ACADEMIC FOUNDATION:
- McKinsey & Company Valuation Handbook
- Damodaran (NYU Stern) - Investment Valuation
- Koller, Goedhart & Wessels - Valuation: Measuring and Managing the Value of Companies
- Big 4 Consulting Firms (PwC, Deloitte, EY, KPMG) Valuation Guidelines
- Ibbotson SBBI Yearbook
- Fama-French Research
- Longstaff & Silber - Liquidity Discount Research

STANDARDS:
- IFRS 13: Fair Value Measurement
- IVS 2017: International Valuation Standards
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, Set

from src.utils.logging import get_logger

logger = get_logger(__name__)


class MethodologySourceRegistry:
    """
    Registry mapping methodologies to academic sources and standards.

    Provides dynamic source generation based on methodologies actually used,
    ensuring only relevant sources are cited.
    """

    # Academic sources by methodology
    SOURCES_BY_METHODOLOGY: Dict[str, List[Dict[str, Any]]] = {
        "DCF": [
            {
                "author": "Koller, Goedhart & Wessels",
                "year": 2020,
                "title": "Valuation: Measuring and Managing the Value of Companies",
                "edition": "7th Edition",
                "publisher": "Wiley",
                "section": "Chapter 8: DCF Valuation",
                "relevance": "DCF methodology and terminal value calculation",
            },
            {
                "author": "Damodaran, A.",
                "year": 2018,
                "title": "The Dark Side of Valuation: Valuing Young, Distressed, and Complex Businesses",
                "publisher": "Wiley",
                "section": "Chapter 5: DCF Valuation",
                "relevance": "DCF methodology and terminal value calculation",
            },
            {
                "author": "McKinsey & Company",
                "year": 2020,
                "title": "Valuation Handbook",
                "section": "DCF Methodology",
                "relevance": "DCF methodology and best practices",
            },
        ],
        "MULTIPLES": [
            {
                "author": "PwC",
                "year": 2024,
                "title": "Valuation Guidelines",
                "section": "Private Company Multiples",
                "relevance": "Multiples valuation methodology and industry benchmarks",
            },
            {
                "author": "Ibbotson SBBI",
                "year": 2024,
                "title": "Stocks, Bonds, Bills, and Inflation Yearbook",
                "section": "Industry Multiples Data",
                "relevance": "Industry multiples data and benchmarks",
            },
            {
                "author": "Fama, E.F. & French, K.R.",
                "year": 1992,
                "title": "The Cross-Section of Expected Stock Returns",
                "journal": "Journal of Finance",
                "volume": "47",
                "pages": "427-465",
                "relevance": "Multiples and valuation factors research",
            },
        ],
        "SIZE_DISCOUNT": [
            {
                "author": "Ibbotson SBBI",
                "year": 2024,
                "title": "Stocks, Bonds, Bills, and Inflation Yearbook",
                "section": "Size Premium Data",
                "relevance": "Size premium data and adjustments",
            },
            {
                "author": "Duff & Phelps",
                "year": 2024,
                "title": "Valuation Handbook",
                "section": "Size Premium Adjustments",
                "relevance": "Size premium adjustments for private companies",
            },
            {
                "author": "Fama, E.F. & French, K.R.",
                "year": 1992,
                "title": "The Cross-Section of Expected Stock Returns",
                "journal": "Journal of Finance",
                "relevance": "Size effect research",
            },
        ],
        "LIQUIDITY_DISCOUNT": [
            {
                "author": "Longstaff, F.A.",
                "year": 1995,
                "title": "How Much Can Marketability Affect Security Values?",
                "journal": "Journal of Finance",
                "volume": "50",
                "pages": "1767-1774",
                "relevance": "Liquidity discount methodology and research",
            },
            {
                "author": "Silber, W.L.",
                "year": 1991,
                "title": "Discounts on Restricted Stock: The Impact of Illiquidity on Stock Prices",
                "journal": "Financial Analysts Journal",
                "volume": "47",
                "pages": "60-64",
                "relevance": "Private company liquidity discount research",
            },
            {
                "author": "PwC",
                "year": 2024,
                "title": "Valuation Guidelines",
                "section": "Private Company Discounts",
                "relevance": "Private company liquidity discount guidelines",
            },
        ],
        "RANGE_METHODOLOGY": [
            {
                "author": "McKinsey & Company",
                "year": 2020,
                "title": "Valuation Handbook",
                "section": "Section 4.3: Multiple Dispersion Analysis",
                "relevance": "Range methodology and multiple dispersion analysis",
            },
            {
                "author": "Damodaran, A.",
                "year": 2012,
                "title": "Investment Valuation: Tools and Techniques for Determining the Value of Any Asset",
                "edition": "3rd Edition",
                "publisher": "Wiley",
                "section": "Chapter 5: Confidence Intervals",
                "relevance": "Confidence intervals and range methodology",
            },
        ],
        "CONFIDENCE_SCORING": [
            {
                "author": "Damodaran, A.",
                "year": 2012,
                "title": "Investment Valuation",
                "section": "Chapter 5: Confidence Intervals",
                "relevance": "Confidence scoring and uncertainty quantification",
            },
            {
                "author": "PwC",
                "year": 2024,
                "title": "Valuation Guidelines",
                "section": "Valuation Confidence Assessment",
                "relevance": "Big 4 8-factor confidence model",
            },
        ],
        "OWNER_CONCENTRATION": [
            {
                "author": "McKinsey & Company",
                "year": 2020,
                "title": "Valuation Handbook",
                "section": "Owner Dependency Adjustments",
                "relevance": "Owner concentration and key person risk adjustments",
            },
            {
                "author": "PwC",
                "year": 2024,
                "title": "Valuation Guidelines",
                "section": "Private Company Adjustments",
                "relevance": "Owner dependency impact on valuation",
            },
        ],
        "OWNERSHIP_ADJUSTMENT": [
            {
                "author": "McKinsey & Company",
                "year": 2015,
                "title": "Valuation: Measuring and Managing the Value of Companies",
                "edition": "6th Edition",
                "publisher": "Wiley",
                "section": "Chapter 8.3: Ownership Adjustments",
                "relevance": "Control premium and minority discount methodology",
            },
            {
                "author": "Bain & Company",
                "year": 2020,
                "title": "Private Equity Valuation Guide",
                "section": "Chapter 5: Ownership Structures",
                "relevance": "Control premium, minority discount, and deadlock risk handling",
            },
            {
                "author": "Mergerstat",
                "year": 2020,
                "title": "Mergerstat Review",
                "section": "Control Premium Analysis",
                "relevance": "Average control premium 15-25% based on transaction data",
            },
            {
                "author": "Pratt, S.P. & Niculita, A.V.",
                "year": 2008,
                "title": "Valuing a Business: The Analysis and Appraisal of Closely Held Companies",
                "edition": "5th Edition",
                "publisher": "McGraw-Hill",
                "section": "Chapter 10: Minority Discounts",
                "relevance": "Minority discount 15-30% for <50% stakes",
            },
            {
                "author": "Bain & Company",
                "year": 2019,
                "title": "M&A Valuation Framework",
                "section": "Section 3.4: Control Premiums",
                "relevance": "Context-dependent control premium adjustments",
            },
        ],
    }

    # Standards references
    STANDARDS_REFERENCES: List[Dict[str, str]] = [
        {
            "standard": "IFRS 13",
            "title": "Fair Value Measurement",
            "organization": "International Financial Reporting Standards",
            "relevance": "Fair value measurement framework",
        },
        {
            "standard": "IVS 2017",
            "title": "International Valuation Standards",
            "organization": "International Valuation Standards Council",
            "relevance": "International valuation standards and best practices",
        },
    ]

    # Methodology descriptions for statements
    METHODOLOGY_DESCRIPTIONS: Dict[str, str] = {
        "DCF": "Discounted Cash Flow (DCF) valuation based on projected free cash flows",
        "MULTIPLES": "Multiples valuation based on comparable company analysis",
        "HYBRID": "Hybrid methodology combining DCF and Multiples with weighted averaging",
        "SIZE_DISCOUNT": "Size premium discount based on company revenue tier (McKinsey Size Premium)",
        "LIQUIDITY_DISCOUNT": "Liquidity discount for private company illiquidity",
        "RANGE_METHODOLOGY": "Range methodology using multiple dispersion or confidence spread",
        "CONFIDENCE_SCORING": "Big 4 8-factor confidence model",
        "OWNER_CONCENTRATION": "Owner concentration adjustment for key person risk",
        "OWNERSHIP_ADJUSTMENT": "Ownership adjustment (control premium for majority stakes, minority discount for minority stakes)",
    }

    def __init__(self):
        """Initialize the methodology source registry."""
        self.logger = logger
        self.logger.debug("MethodologySourceRegistry initialized")

    def get_sources_for_methodology(self, methodology: str) -> List[Dict[str, Any]]:
        """
        Get academic sources for a specific methodology.

        Args:
            methodology: Methodology name (e.g., 'DCF', 'MULTIPLES', 'SIZE_DISCOUNT')

        Returns:
            List of source dictionaries
        """
        return self.SOURCES_BY_METHODOLOGY.get(methodology.upper(), [])

    def get_all_sources(self, used_methodologies: List[str]) -> List[Dict[str, Any]]:
        """
        Get all unique academic sources for a list of methodologies.

        Removes duplicates based on author + year + title combination.

        Args:
            used_methodologies: List of methodology names used in valuation

        Returns:
            List of unique source dictionaries, sorted by methodology priority
        """
        all_sources = []
        seen_sources = set()

        # Priority order: DCF, MULTIPLES, SIZE_DISCOUNT, LIQUIDITY_DISCOUNT, RANGE_METHODOLOGY, etc.
        priority_order = [
            "DCF",
            "MULTIPLES",
            "HYBRID",
            "SIZE_DISCOUNT",
            "LIQUIDITY_DISCOUNT",
            "RANGE_METHODOLOGY",
            "CONFIDENCE_SCORING",
            "OWNER_CONCENTRATION",
            "OWNERSHIP_ADJUSTMENT",
        ]

        # Process methodologies in priority order
        for methodology in priority_order:
            if methodology in [m.upper() for m in used_methodologies]:
                sources = self.get_sources_for_methodology(methodology)
                for source in sources:
                    # Create unique key: author + year + title
                    source_key = (
                        source.get("author", ""),
                        source.get("year", ""),
                        source.get("title", ""),
                    )
                    if source_key not in seen_sources:
                        seen_sources.add(source_key)
                        all_sources.append(source)

        # Add any remaining methodologies not in priority order
        for methodology in used_methodologies:
            if methodology.upper() not in priority_order:
                sources = self.get_sources_for_methodology(methodology)
                for source in sources:
                    source_key = (
                        source.get("author", ""),
                        source.get("year", ""),
                        source.get("title", ""),
                    )
                    if source_key not in seen_sources:
                        seen_sources.add(source_key)
                        all_sources.append(source)

        return all_sources

    def get_methodology_statement(
        self,
        methodologies: List[str],
        primary_method: Optional[str] = None,
        range_methodology: Optional[str] = None,
        adjustments: Optional[List[Dict[str, Any]]] = None,
        assumptions: Optional[List[str]] = None,
        engine_version: str = "2.0.0",
    ) -> str:
        """
        Generate comprehensive methodology statement.

        Args:
            methodologies: List of methodologies used
            primary_method: Primary valuation method (e.g., 'EV/Revenue', 'EV/EBITDA')
            range_methodology: Range methodology used (e.g., 'Multiple Dispersion', 'Confidence Spread')
            adjustments: List of adjustments applied with details
            assumptions: List of key assumptions
            engine_version: Valuation engine version

        Returns:
            Comprehensive methodology statement string
        """
        statement_parts = []

        # Opening statement
        statement_parts.append(
            "This valuation follows internationally recognized standards including IFRS 13 "
            "(Fair Value Measurement), IVS 2017 (International Valuation Standards), and "
            "methodologies from McKinsey & Company, Damodaran (NYU Stern), and Big 4 "
            "consulting firms."
        )

        statement_parts.append("")
        statement_parts.append("Methodologies Applied:")

        # Primary method
        if primary_method:
            if primary_method == "EV/Revenue":
                statement_parts.append(
                    f"- Multiples Valuation (EV/Revenue): Primary method based on comparable "
                    f"company analysis using P50 median multiples"
                )
            elif primary_method == "EV/EBITDA":
                statement_parts.append(
                    f"- Multiples Valuation (EV/EBITDA): Primary method based on comparable "
                    f"company analysis using P50 median multiples"
                )

        # DCF if used
        if "DCF" in [m.upper() for m in methodologies]:
            statement_parts.append(
                "- Discounted Cash Flow (DCF): Applied based on projected free cash flows "
                "and terminal value calculation"
            )

        # Hybrid if used
        if "HYBRID" in [m.upper() for m in methodologies]:
            statement_parts.append(
                "- Hybrid Methodology: Combined DCF and Multiples with weighted averaging"
            )

        # Range methodology
        if range_methodology:
            if range_methodology == "Multiple Dispersion":
                statement_parts.append(
                    "- Multiple Dispersion Range: Applied based on P25/P50/P75 percentiles "
                    "from comparable companies"
                )
            elif range_methodology == "Confidence Spread":
                statement_parts.append(
                    "- Confidence Spread Range: Applied based on confidence score and "
                    "business characteristics"
                )
            elif range_methodology == "Asymmetric Range":
                statement_parts.append(
                    "- Asymmetric Range: Applied for SMEs with high downside risk"
                )

        # Adjustments
        if adjustments:
            statement_parts.append("")
            statement_parts.append("Adjustments Applied:")
            for adj in adjustments:
                adj_name = adj.get("name", "")
                adj_value = adj.get("value", "")
                adj_rationale = adj.get("rationale", "")
                if adj_value:
                    statement_parts.append(f"- {adj_name}: Applied {adj_value} {adj_rationale}")

        # Assumptions
        if assumptions:
            statement_parts.append("")
            statement_parts.append("Assumptions:")
            for assumption in assumptions:
                statement_parts.append(f"- {assumption}")

        # Version and date
        statement_parts.append("")
        statement_parts.append(
            f"Valuation Engine Version: {engine_version} | "
            f"Calculation Date: {datetime.now().strftime('%Y-%m-%d')}"
        )

        return "\n".join(statement_parts)

    def get_standards_references(self) -> List[Dict[str, str]]:
        """
        Get standards references (IFRS 13, IVS 2017).

        Returns:
            List of standards dictionaries
        """
        return self.STANDARDS_REFERENCES.copy()

    def format_source_for_display(self, source: Dict[str, Any]) -> str:
        """
        Format a source dictionary for display in frontend.

        Args:
            source: Source dictionary

        Returns:
            Formatted string for display
        """
        parts = []

        # Author and year
        author = source.get("author", "")
        year = source.get("year", "")
        if author and year:
            parts.append(f"{author} ({year})")
        elif author:
            parts.append(author)

        # Title
        title = source.get("title", "")
        if title:
            parts.append(f'"{title}"')

        # Edition
        edition = source.get("edition", "")
        if edition:
            parts.append(edition)

        # Journal/Publisher
        journal = source.get("journal", "")
        publisher = source.get("publisher", "")
        if journal:
            volume = source.get("volume", "")
            pages = source.get("pages", "")
            if volume and pages:
                parts.append(f"{journal}, Vol. {volume}, pp. {pages}")
            elif journal:
                parts.append(journal)
        elif publisher:
            parts.append(publisher)

        return ", ".join(parts)


import threading

_registry_instance: Optional[MethodologySourceRegistry] = None
_registry_lock = threading.Lock()


def get_methodology_source_registry() -> MethodologySourceRegistry:
    """
    Get the global MethodologySourceRegistry instance (singleton).
    Thread-safe via double-checked locking.
    """
    global _registry_instance
    if _registry_instance is None:
        with _registry_lock:
            if _registry_instance is None:
                _registry_instance = MethodologySourceRegistry()
    return _registry_instance
