"""
Academic Metadata Models

Data models for academic methodology validation, provenance tracking,
and citation generation.

Author: Upswitch CTO Team
Date: December 2025
Status: Production Ready
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Set
from datetime import datetime
from decimal import Decimal
from enum import Enum


class CitationStyle(Enum):
    """Academic citation formatting styles"""

    APA = "apa"
    CHICAGO = "chicago"
    HARVARD = "harvard"
    MLA = "mla"


class ConfidenceLevel(Enum):
    """Confidence levels for academic sources and validations"""

    VERY_HIGH = "very_high"  # 95%+
    HIGH = "high"  # 85-94%
    MEDIUM_HIGH = "medium_high"  # 75-84%
    MEDIUM = "medium"  # 65-74%
    LOW = "low"  # <65%


class SourceType(Enum):
    """Types of academic sources"""

    PEER_REVIEWED_JOURNAL = "peer_reviewed_journal"
    ACADEMIC_TEXTBOOK = "academic_textbook"
    ACADEMIC_RESEARCH = "academic_research"
    BIG_4_METHODOLOGY = "big_4_methodology"
    INDUSTRY_REPORT = "industry_report"
    PROFESSIONAL_STANDARD = "professional_standard"
    WORKING_PAPER = "working_paper"


@dataclass
class AcademicSource:
    """
    Academic source metadata for citations and validation
    """

    source_id: str  # Unique identifier (e.g., "damodaran_2012")
    author: str  # Author(s) name
    year: int  # Publication year
    title: str  # Full title
    source_type: SourceType  # Type of source

    # Optional fields
    publisher: Optional[str] = None
    edition: Optional[str] = None
    journal: Optional[str] = None
    volume: Optional[str] = None
    issue: Optional[str] = None
    pages: Optional[str] = None
    section: Optional[str] = None
    doi: Optional[str] = None
    isbn: Optional[str] = None
    url: Optional[str] = None

    # Metadata
    relevance: Optional[str] = None  # Why this source is relevant
    confidence_level: ConfidenceLevel = ConfidenceLevel.HIGH
    verified: bool = True  # Has source been verified?
    notes: Optional[str] = None  # Additional notes about the source
    category: Optional[str] = None  # Source category (e.g., "multiples", "discounts")

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "source_id": self.source_id,
            "author": self.author,
            "year": self.year,
            "title": self.title,
            "source_type": self.source_type.value,
            "publisher": self.publisher,
            "edition": self.edition,
            "journal": self.journal,
            "volume": self.volume,
            "pages": self.pages,
            "section": self.section,
            "doi": self.doi,
            "isbn": self.isbn,
            "url": self.url,
            "relevance": self.relevance,
            "confidence_level": self.confidence_level.value,
            "verified": self.verified,
        }

    def format_citation(self, style: CitationStyle = CitationStyle.APA) -> str:
        """
        Format citation according to academic style

        Args:
            style: Citation style to use

        Returns:
            Formatted citation string
        """
        if style == CitationStyle.APA:
            return self._format_apa()
        elif style == CitationStyle.CHICAGO:
            return self._format_chicago()
        elif style == CitationStyle.HARVARD:
            return self._format_harvard()
        else:
            return self._format_apa()  # Default to APA

    def _format_apa(self) -> str:
        """Format in APA style"""
        citation = f"{self.author} ({self.year}). {self.title}."

        if self.journal:
            citation += f" {self.journal}"
            if self.volume:
                citation += f", {self.volume}"
            if self.pages:
                citation += f", {self.pages}"
        elif self.publisher:
            citation += f" {self.publisher}"
            if self.edition:
                citation += f" ({self.edition})"

        if self.section:
            citation += f" [{self.section}]"

        citation += "."
        return citation

    def _format_chicago(self) -> str:
        """Format in Chicago style"""
        citation = f"{self.author}. {self.title}."

        if self.publisher:
            citation += f" {self.publisher}, {self.year}"
        elif self.journal:
            citation += f" {self.journal}"
            if self.volume:
                citation += f" {self.volume}"
            citation += f" ({self.year})"
            if self.pages:
                citation += f": {self.pages}"

        citation += "."
        return citation

    def _format_harvard(self) -> str:
        """Format in Harvard style"""
        citation = f"{self.author} {self.year}, '{self.title}'"

        if self.journal:
            citation += f", {self.journal}"
            if self.volume:
                citation += f", vol. {self.volume}"
            if self.pages:
                citation += f", pp. {self.pages}"
        elif self.publisher:
            citation += f", {self.publisher}"

        citation += "."
        return citation


@dataclass
class ValidationRule:
    """
    Validation rule for academic correctness
    """

    rule_id: str  # Unique identifier
    rule_name: str  # Human-readable name
    rule_type: str  # Type of validation (range, formula, logic)

    # Rule specification
    min_value: Optional[Decimal] = None
    max_value: Optional[Decimal] = None
    formula: Optional[str] = None  # Expected formula
    validation_function: Optional[str] = None  # Python function name

    # Metadata
    academic_source_ids: List[str] = field(default_factory=list)  # Sources supporting this rule
    confidence_level: ConfidenceLevel = ConfidenceLevel.HIGH
    error_message: Optional[str] = None  # Message if validation fails
    warning_message: Optional[str] = None  # Warning message

    def validate(self, value: Any, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Validate a value against this rule

        Args:
            value: Value to validate
            context: Additional context for validation

        Returns:
            Validation result with status, message, etc.
        """
        result = {
            "rule_id": self.rule_id,
            "rule_name": self.rule_name,
            "passed": True,
            "warnings": [],
            "errors": [],
        }

        # Range validation
        if self.rule_type == "range" and self.min_value is not None and self.max_value is not None:
            try:
                numeric_value = Decimal(str(value))
                min_value = self.min_value
                max_value = self.max_value
                range_label = "acceptable"
                if self.rule_id == "ebitda_multiple_sme_range" and context:
                    sme_class = str(context.get("sme_class") or "").strip().lower()
                    sme_bounds = {
                        "micro": (Decimal("1.5"), Decimal("5.0")),
                        "small": (Decimal("2.0"), Decimal("6.5")),
                        "medium": (Decimal("2.5"), Decimal("10.0")),
                    }
                    if sme_class in sme_bounds:
                        min_value, max_value = sme_bounds[sme_class]
                        range_label = f"{sme_class} SME calibrated"

                if numeric_value < min_value or numeric_value > max_value:
                    result["passed"] = False
                    result["errors"].append(
                        (
                            f"Value {value} outside {range_label} range "
                            f"[{min_value}, {max_value}]"
                        )
                        if range_label != "acceptable"
                        else (
                            self.error_message
                            or f"Value {value} outside acceptable range [{min_value}, {max_value}]"
                        )
                    )
            except (ValueError, TypeError) as e:
                result["passed"] = False
                result["errors"].append(f"Could not validate value: {e}")

        return result


@dataclass
class CalculationMetadata:
    """
    Metadata linking a calculation to academic sources and validation rules
    """

    calculation_id: str  # Unique identifier (e.g., "ebitda_multiple_adjustment")
    calculation_name: str  # Human-readable name
    description: str  # What this calculation does

    # Academic provenance
    academic_sources: List[AcademicSource] = field(default_factory=list)
    validation_rules: List[ValidationRule] = field(default_factory=list)

    # Formula specification
    formula: Optional[str] = None  # Mathematical formula
    formula_latex: Optional[str] = None  # LaTeX representation

    # Metadata
    confidence_level: ConfidenceLevel = ConfidenceLevel.HIGH
    category: Optional[str] = None  # Category (multiples, dcf, discounts, etc.)
    notes: Optional[str] = None  # Additional notes about the calculation
    last_validated: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "calculation_id": self.calculation_id,
            "calculation_name": self.calculation_name,
            "description": self.description,
            "academic_sources": [source.to_dict() for source in self.academic_sources],
            "validation_rules": [
                {
                    "rule_id": rule.rule_id,
                    "rule_name": rule.rule_name,
                    "rule_type": rule.rule_type,
                    "confidence_level": rule.confidence_level.value,
                }
                for rule in self.validation_rules
            ],
            "formula": self.formula,
            "formula_latex": self.formula_latex,
            "confidence_level": self.confidence_level.value,
            "category": self.category,
            "last_validated": self.last_validated.isoformat() if self.last_validated else None,
        }


@dataclass
class ProvenanceRecord:
    """
    Runtime record of a calculation with academic provenance
    """

    record_id: str  # Unique identifier for this record
    calculation_id: str  # Reference to CalculationMetadata
    timestamp: datetime  # When calculation was performed

    # Calculation details
    inputs: Dict[str, Any] = field(default_factory=dict)
    outputs: Dict[str, Any] = field(default_factory=dict)

    # Academic metadata
    academic_source_ids: List[str] = field(default_factory=list)  # Sources used
    validation_results: List[Dict[str, Any]] = field(default_factory=list)

    # Context
    valuation_id: Optional[str] = None
    section_name: Optional[str] = None
    step_number: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "record_id": self.record_id,
            "calculation_id": self.calculation_id,
            "timestamp": self.timestamp.isoformat(),
            "inputs": self.inputs,
            "outputs": self.outputs,
            "academic_source_ids": self.academic_source_ids,
            "validation_results": self.validation_results,
            "valuation_id": self.valuation_id,
            "section_name": self.section_name,
            "step_number": self.step_number,
        }


@dataclass
class Citation:
    """
    Citation for use in reports
    """

    citation_id: str  # Unique identifier
    academic_source: AcademicSource  # Source being cited
    citation_number: Optional[int] = None  # Number for inline citations

    # Context
    calculation_ids: List[str] = field(default_factory=list)  # Calculations using this source
    section_name: Optional[str] = None  # Section where cited

    def format(self, style: CitationStyle = CitationStyle.APA, inline: bool = False) -> str:
        """
        Format citation

        Args:
            style: Citation style to use
            inline: If True, format for inline use (short form)

        Returns:
            Formatted citation string
        """
        if inline:
            # Short inline format: (Author, Year)
            return f"({self.academic_source.author.split(',')[0]}, {self.academic_source.year})"
        else:
            # Full citation
            return self.academic_source.format_citation(style)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "citation_id": self.citation_id,
            "academic_source": self.academic_source.to_dict(),
            "citation_number": self.citation_number,
            "calculation_ids": self.calculation_ids,
            "section_name": self.section_name,
        }
