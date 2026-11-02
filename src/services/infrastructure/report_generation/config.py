"""
Report Generation Configuration

BANK-GRADE: Centralized configuration for report generation.
"""


class ReportGenerationConfig:
    """Configuration constants for report generation."""
    # Timeouts
    TRANSFORMATION_TIMEOUT_SECONDS = 30.0
    RENDERING_TIMEOUT_SECONDS = 60.0
    
    # Content validation
    MIN_HTML_CONTENT_LENGTH = 100
    
    # Accountant View specific
    ACCOUNTANT_VIEW_TIMEOUT_SECONDS = 45.0
    
    # Main Report specific
    MAIN_REPORT_TIMEOUT_SECONDS = 30.0
    
    # PDF generation specific
    PDF_CONVERSION_TIMEOUT_SECONDS = 60.0  # PDF conversion can be slower
    MIN_PDF_SIZE_BYTES = 1000  # Minimum reasonable PDF size

