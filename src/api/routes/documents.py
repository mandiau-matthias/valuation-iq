from src.utils.exceptions import APIError, DataValidationError

"""
Document Parsing API Routes

Handles document upload and rule-based data extraction.

BRAIN & MUSCLE ARCHITECTURE:
Generated extraction has been removed from ValuationIQ.
For generated document analysis, use Titan's document endpoints.
This service uses rule-based extraction patterns only.
"""

import os

from fastapi import APIRouter, File, UploadFile, HTTPException, status
# CRITICAL FIX: Use custom JSONResponse that handles Decimal serialization
from src.api.json_response import JSONResponse  # Custom JSONResponse with Decimal support
from src.utils.logging import get_logger

from src.services.infrastructure.document_parser import DocumentParser
from decimal import Decimal
from src.utils.decimal_helpers import to_decimal, from_decimal

logger = get_logger(__name__)

router = APIRouter()

# Initialize document parser (generated extraction moved to Titan).
document_parser = DocumentParser()

# Supported file types
ALLOWED_EXTENSIONS = {".pdf", ".xlsx", ".xls", ".csv", ".png", ".jpg", ".jpeg"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB


@router.post(
    "/parse",
    summary="Parse financial document",
    description="Upload a financial document (PDF, Excel, CSV, or image) and extract structured valuation data using rule-based extraction. For generated extraction, use Titan's document endpoints.",
    status_code=status.HTTP_200_OK,
    response_model=dict[str, object],
)
async def parse_document(file: UploadFile = File(...)) -> dict[str, object]:
    """
    Parse a financial document and extract structured data.

    Supported formats:
    - PDF (.pdf)
    - Excel (.xlsx, .xls)
    - CSV (.csv)
    - Images (.png, .jpg, .jpeg)

    Maximum file size: 10MB

    Args:
        file: Uploaded file to parse

    Returns:
        Dictionary containing:
        - extracted_data: Partial valuation request data
        - confidence: Confidence score (0-1)
        - warnings: List of missing or uncertain fields
        - metadata: File information and processing details

    Raises:
        HTTPException: If file format is unsupported, file is too large, or parsing fails
    """
    logger.info("Received document parse request", filename=file.filename)

    # 1. Validate file extension
    file_ext = os.path.splitext(file.filename)[1].lower()
    if file_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file format. Supported: {', '.join(ALLOWED_EXTENSIONS)}",
        )

    # 2. Read file content
    try:
        content = await file.read()
    except DataValidationError as e:
        logger.error("Failed to read file", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to read the uploaded file.",
        )

    # 3. Check file size
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File size exceeds {MAX_FILE_SIZE / 1024 / 1024}MB limit",
        )

    # 4. Parse document
    try:
        result = await document_parser.parse_document(content, file.filename)
        logger.info(
            "Document parsed successfully",
            confidence=result["confidence"],
            warnings_count=len(result["warnings"]),
        )
        return result

    except APIError as e:
        logger.error("Document parsing failed", error=str(e), filename=file.filename)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to parse the document. Please check the file format and try again.",
        )


@router.get(
    "/supported-formats",
    summary="Get supported file formats",
    description="Returns list of supported file formats for document upload.",
)
async def get_supported_formats() -> dict[str, object]:
    """
    Get list of supported file formats.

    Returns:
        Dictionary containing supported formats and maximum file size
    """
    return {
        "formats": list(ALLOWED_EXTENSIONS),
        "max_file_size_mb": MAX_FILE_SIZE / 1024 / 1024,
        "ai_available": False,  # AI moved to Titan
    }
