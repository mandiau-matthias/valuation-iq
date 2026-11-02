"""
Report Transformer

Modular system for transforming ValuationResponse and ValuationRequest into template-friendly
data structures for HTML report generation.

REFACTORED ARCHITECTURE (SRP-Compliant):
- Coordinators: Main facade for orchestration (ReportTransformerCoordinator)
- Extractors: Extract data from requests
- Enrichers: Enrich business type data
- Determiners: Determine methodologies
- Analyzers: Analyze data quality
- Builders: Build data structures
- Assemblers: Assemble final template data
- Validators: Validate data structures
- Converters: Convert models to dicts
- Transformers: Transform sections

Pattern: Facade (like BusinessTypeIntelligenceCoordinator and StructuredFlowCoordinator)
"""

# Main coordinator (facade pattern - recommended)
from .coordinators import ReportTransformerCoordinator

# Legacy orchestrator (backward compatibility)
from .orchestrators import ReportTransformerOrchestrator

# Specialized services
from .extractors import RequestDataExtractor
from .enrichers import BusinessTypeEnricher
from .determiners import MethodologyDeterminer
from .analyzers import DataQualityAnalyzer
from .builders import CalculationStepsBuilder, WaterfallBuilder
from .assemblers import TemplateDataAssembler
from .validators import ReportDataValidator

__all__ = [
    # Recommended: Use ReportTransformerCoordinator (SRP-compliant facade)
    'ReportTransformerCoordinator',
    
    # Legacy: ReportTransformerOrchestrator (backward compatibility)
    'ReportTransformerOrchestrator',
    
    # Specialized services (for fine-grained control)
    'RequestDataExtractor',
    'BusinessTypeEnricher',
    'MethodologyDeterminer',
    'DataQualityAnalyzer',
    'CalculationStepsBuilder',
    'WaterfallBuilder',
    'TemplateDataAssembler',
    'ReportDataValidator',
]

