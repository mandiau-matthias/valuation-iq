"""
Quality Level Mapper for Step 0 Data Quality

Maps quality scores to quality level descriptions.
"""


class QualityLevelMapper:
    """Maps quality scores to quality level descriptions."""

    @staticmethod
    def get_quality_level(quality_score: int) -> str:
        """
        Get quality level description based on score.

        Args:
            quality_score: The quality score (0-100)

        Returns:
            Quality level string: "HIGH", "MEDIUM", "LOW", or "CRITICAL"
        """
        if quality_score >= 80:
            return "HIGH"
        elif quality_score >= 60:
            return "MEDIUM"
        elif quality_score >= 40:
            return "LOW"
        else:
            return "CRITICAL"
