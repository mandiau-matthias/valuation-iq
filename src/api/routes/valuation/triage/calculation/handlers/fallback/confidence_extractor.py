"""
Confidence Score Extractor

Extracts confidence score from Step 9.
"""

from typing import Any, Dict

from src.api.routes.valuation.steps.base_step import StepOutput, StepStatus


class ConfidenceScoreExtractor:
    """Extracts confidence score from step results."""
    
    DEFAULT_CONFIDENCE = 66  # Default medium confidence
    
    @staticmethod
    def extract(previous_results: Dict[int, StepOutput]) -> int:
        """
        Extract confidence score from Step 9 or use default.
        
        Args:
            previous_results: Results from previous steps
            
        Returns:
            Confidence score (0-100)
        """
        step9_output = previous_results.get(9)
        
        if step9_output and step9_output.status == StepStatus.COMPLETED:
            return step9_output.result.get("overall_confidence_score", ConfidenceScoreExtractor.DEFAULT_CONFIDENCE)
        
        return ConfidenceScoreExtractor.DEFAULT_CONFIDENCE

