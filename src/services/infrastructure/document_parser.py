from src.services.infrastructure.exceptions import ReportGenerationError as DocumentGenerationError
from src.utils.exceptions import APIError, DataValidationError, ExternalServiceError

"""
Document Parser Service

Parses financial documents (PDF, Excel, CSV) using rule-based extraction.

BRAIN & MUSCLE ARCHITECTURE:
Generated document parsing has moved to Titan.
For generated document analysis, use Titan's document processing endpoints.
This service now uses rule-based extraction patterns only.
"""

import json
import re
from typing import Dict, Any, List, Optional
from io import BytesIO

from src.utils.logging import get_logger
import pypdf
import openpyxl
import pandas as pd
from PIL import Image
from decimal import Decimal
from src.utils.decimal_helpers import to_decimal, from_decimal
from src.utils.fiscal_year import get_current_filing_year

logger = get_logger(__name__)


class DocumentParser:
    """
    Service for parsing financial documents and extracting valuation data.

    BRAIN & MUSCLE: generated extraction has been removed.
    This service now uses rule-based extraction patterns only.
    For generated extraction, use Titan's document endpoints.
    """

    def __init__(self, legacy_provider_api_key: Optional[str] = None, **legacy_kwargs: Any):
        """Initialize document parser.

        Legacy provider-key parameters are deprecated and ignored.
        Generated document parsing has moved to Titan.
        """
        legacy_key = legacy_provider_api_key
        if legacy_key is None:
            legacy_key = next(
                (
                    value
                    for key, value in legacy_kwargs.items()
                    if key.endswith("_api_key")
                ),
                None,
            )
        if legacy_key:
            logger.warning("DEPRECATED: provider key supplied but generated parsing has moved to Titan")
        self.confidence_threshold = Decimal('0.7')

    async def parse_document(
        self, file_content: bytes, filename: str
    ) -> Dict[str, Any]:
        """
        Main parsing orchestrator.

        Args:
            file_content: Binary file content
            filename: Original filename for type detection

        Returns:
            Dict with extracted_data, confidence, warnings, metadata
        """
        logger.info("Starting document parsing", extra={'filename': filename})

        # 1. Detect file type
        file_type = self._detect_file_type(filename)

        # 2. Extract text based on file type
        try:
            if file_type == "pdf":
                text = await self._extract_pdf_text(file_content)
            elif file_type in ["xlsx", "xls"]:
                text = await self._extract_excel_text(file_content)
            elif file_type == "csv":
                text = await self._extract_csv_text(file_content)
            elif file_type in ["png", "jpg", "jpeg"]:
                # Image OCR is Titan-owned; local parser returns a placeholder.
                text = await self._extract_image_text(file_content)
            else:
                raise ValueError(f"Unsupported file type: {file_type}")

            logger.info("Text extraction complete", extra={'text_length': len(text)})

        except (ValueError, IOError, OSError) as e:
            logger.warning("Text extraction failed (file error)", extra={'error_type': type(e).__name__, 'error': str(e)})
            return {
                "extracted_data": {},
                "confidence": Decimal('0.0'),
                "warnings": [f"Failed to extract text: {str(e)}"],
                "metadata": {"file_type": file_type, "error": str(e)},
            }
        except ExternalServiceError as e:
            logger.error("Text extraction failed (unexpected error)", extra={'error_type': type(e).__name__, 'error': str(e)}, exc_info=True)
            return {
                "extracted_data": {},
                "confidence": Decimal('0.0'),
                "warnings": [f"Failed to extract text: {str(e)}"],
                "metadata": {"file_type": file_type, "error": str(e)},
            }

        # 3. Rule-based extraction
        # BRAIN & MUSCLE: AI extraction removed - for AI use Titan
        logger.info("Using rule-based extraction (AI moved to Titan)")
        extracted = self._rule_based_extraction(text)

        # 4. Validation and confidence scoring
        validated = self._validate_extraction(extracted)
        confidence = self._calculate_confidence(validated)
        warnings = self._generate_warnings(validated)

        return {
            "extracted_data": validated,
            "confidence": confidence,
            "warnings": warnings,
            "metadata": {
                "file_type": file_type,
                "extraction_method": "rule-based",
                "text_length": len(text),
            },
        }

    def _detect_file_type(self, filename: str) -> str:
        """Detect file type from extension."""
        extension = filename.lower().split(".")[-1]
        return extension

    async def _extract_pdf_text(self, content: bytes) -> str:
        """Extract text from PDF using pypdf."""
        try:
            pdf_file = BytesIO(content)
            pdf_reader = pypdf.PdfReader(pdf_file)
            text = ""
            for page in pdf_reader.pages:
                text += page.extract_text() + "\n"
            return text
        except DocumentGenerationError as e:
            logger.error("PDF extraction failed", extra={'error': str(e)})
            raise

    async def _extract_excel_text(self, content: bytes) -> str:
        """Extract text from Excel file."""
        try:
            excel_file = BytesIO(content)
            workbook = openpyxl.load_workbook(excel_file)
            text = ""

            for sheet_name in workbook.sheetnames:
                sheet = workbook[sheet_name]
                text += f"\n=== Sheet: {sheet_name} ===\n"
                for row in sheet.iter_rows(values_only=True):
                    row_text = " | ".join([str(cell) if cell else "" for cell in row])
                    text += row_text + "\n"

            return text
        except (IOError, OSError, ValueError, KeyError) as e:
            logger.error("Excel extraction failed (file/data error)", extra={'error_type': type(e).__name__, 'error': str(e)})
            raise
        except ExternalServiceError as e:
            logger.error("Excel extraction failed (unexpected error)", extra={'error_type': type(e).__name__, 'error': str(e)}, exc_info=True)
            raise

    async def _extract_csv_text(self, content: bytes) -> str:
        """Extract text from CSV file."""
        try:
            csv_file = BytesIO(content)
            df = pd.read_csv(csv_file)
            return df.to_string()
        except (IOError, OSError, ValueError) as e:
            logger.error("CSV extraction failed (file error)", extra={'error_type': type(e).__name__, 'error': str(e)})
            raise
        except APIError as e:
            logger.error("CSV extraction failed (unexpected error)", extra={'error_type': type(e).__name__, 'error': str(e)}, exc_info=True)
            raise

    async def _extract_image_text(self, content: bytes) -> str:
        """Extract text from image using OCR.
        
        BRAIN & MUSCLE: generated OCR moved to Titan.
        For generated OCR, use Titan's document endpoints.
        """
        logger.warning("Image text extraction not fully implemented - use Titan for generated OCR")
        return "[Image content - use Titan for generated OCR]"

    async def _extract_with_provider_fallback(self, text: str) -> Dict[str, Any]:
        """
        DEPRECATED: Generated extraction has moved to Titan.

        This method now falls back to rule-based extraction.
        For generated extraction, use Titan's document endpoints.
        """
        logger.warning("DEPRECATED: provider extraction called - generated parsing has moved to Titan")
        return self._rule_based_extraction(text)

    def _rule_based_extraction(self, text: str) -> Dict[str, Any]:
        """
        Fallback rule-based extraction using regex patterns.
        """
        extracted = {}

        # Extract revenue (various patterns)
        revenue_patterns = [
            r"revenue[:\s]+\u20AC?([0-9,\.]+)",
            r"sales[:\s]+\u20AC?([0-9,\.]+)",
            r"turnover[:\s]+\u20AC?([0-9,\.]+)",
            r"umsatz[:\s]+\u20AC?([0-9,\.]+)",  # German
        ]
        for pattern in revenue_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                extracted["revenue"] = self._parse_number(match.group(1))
                break

        # Extract EBITDA
        ebitda_patterns = [r"ebitda[:\s]+\u20AC?([0-9,\.]+)", r"ebit[:\s]+\u20AC?([0-9,\.]+)"]
        for pattern in ebitda_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                extracted["ebitda"] = self._parse_number(match.group(1))
                break

        # Extract company name (first line or header)
        lines = text.split("\n")
        for line in lines[:10]:
            if "gmbh" in line.lower() or "ag" in line.lower() or "ltd" in line.lower():
                extracted["company_name"] = line.strip()
                break

        logger.info("Rule-based extraction complete", extra={'fields_found': len(extracted)})
        return extracted

    def _parse_number(self, number_str: str) -> Decimal:
        """Parse number string to float."""
        # Remove commas and convert to float
        cleaned = number_str.replace(",", "").replace(" ", "")
        try:
            return to_decimal(cleaned)
        except ValueError:
            return Decimal('0.0')

    def _validate_extraction(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate and clean extracted data.
        """
        validated = {}

        # Ensure required fields
        if "company_name" in data:
            validated["company_name"] = str(data["company_name"])

        if "industry" in data:
            validated["industry"] = str(data["industry"]).lower()

        if "country_code" in data:
            validated["country_code"] = str(data["country_code"]).upper()[:2]

        # Build current_year_data
        current_year_data = {"year": get_current_filing_year()}

        if "revenue" in data and data["revenue"]:
            current_year_data["revenue"] = to_decimal(data["revenue"])

        if "ebitda" in data and data["ebitda"]:
            current_year_data["ebitda"] = to_decimal(data["ebitda"])

        if "operating_expenses" in data and data["operating_expenses"]:
            current_year_data["operating_expenses"] = to_decimal(data["operating_expenses"])

        if "net_income" in data and data["net_income"]:
            current_year_data["net_income"] = to_decimal(data["net_income"])

        if current_year_data.keys() != {"year"}:
            validated["current_year_data"] = current_year_data

        # Optional fields
        if "founding_year" in data and data["founding_year"]:
            validated["founding_year"] = int(data["founding_year"])

        if "employees" in data and data["employees"]:
            validated["employees"] = int(data["employees"])

        return validated

    def _calculate_confidence(self, data: Dict[str, Any]) -> Decimal:
        """
        Calculate confidence score based on completeness.
        """
        required_fields = ["company_name", "industry", "country_code"]
        important_fields = ["revenue", "ebitda"]

        score = Decimal('0.0')

        # Check required fields (40% weight)
        required_found = sum(1 for field in required_fields if field in data)
        score += (required_found / len(required_fields)) * Decimal('0.4')

        # Check current_year_data (60% weight)
        if "current_year_data" in data:
            year_data = data["current_year_data"]
            important_found = sum(1 for field in important_fields if field in year_data)
            score += (important_found / len(important_fields)) * Decimal('0.6')

        return round(score, 2)

    def _generate_warnings(self, data: Dict[str, Any]) -> List[str]:
        """
        Generate warnings for missing or questionable data.
        """
        warnings = []

        if "company_name" not in data:
            warnings.append("Company name not found - please enter manually")

        if "current_year_data" not in data:
            warnings.append("No financial data extracted - please enter manually")
        else:
            year_data = data["current_year_data"]
            if "revenue" not in year_data:
                warnings.append("Revenue not found - please enter manually")
            if "ebitda" not in year_data:
                warnings.append("EBITDA not found - please enter manually")

        if "industry" not in data:
            warnings.append("Industry not detected - please select manually")

        if "country_code" not in data:
            warnings.append("Country not detected - please select manually")

        return warnings
