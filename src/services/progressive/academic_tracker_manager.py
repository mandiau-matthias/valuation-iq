"""
Academic Tracker Manager

Responsibility: Manage academic provenance tracking.

Single Responsibility: Academic tracking management only.
"""

from typing import Dict, Any, Optional
from src.utils.logging import get_logger
from src.utils.exceptions import (
    ValuationEngineError,
    ExternalServiceError,
    ConfigurationError,
)

logger = get_logger(__name__)


class AcademicTrackerManager:
    """
    Manages academic provenance tracking for valuations.
    
    Single Responsibility: Academic tracking only.
    """

    def __init__(self):
        """Initialize academic tracker manager"""
        self.logger = logger
        self.academic_tracker = None
        self.academic_tracking_enabled = False
        self.validation_engine = None
        
        # Try to import academic services
        try:
            from src.services.academic.calculation_provenance_tracker import create_tracker, set_current_tracker
            from src.services.academic.academic_validation_engine import get_validation_engine
            self._create_tracker = create_tracker
            self._set_current_tracker = set_current_tracker
            self.validation_engine = get_validation_engine()
            self.academic_tracking_enabled = True
            self.logger.info("Academic provenance tracking enabled")
        except ImportError as e:
            self.logger.warning(f"Academic tracking not available: {e}")
            self.academic_tracking_enabled = False

    def ensure_tracker(self, data: Dict[str, Any]) -> Optional[Any]:
        """
        Ensure academic tracker is created for this valuation
        
        Args:
            data: Collected data dictionary
            
        Returns:
            Academic tracker instance or None if not available
        """
        if not self.academic_tracking_enabled:
            return None

        if self.academic_tracker is None:
            try:
                self.academic_tracker = self._create_tracker()
                self._set_current_tracker(self.academic_tracker)
                self.logger.debug("Academic tracker created for valuation")
            except (ImportError, AttributeError, TypeError) as e:
                # Handle import/initialization errors gracefully
                self.logger.warning(f"Failed to create academic tracker (initialization error): {e}")
                return None
            except (ConfigurationError, ExternalServiceError) as e:
                # Re-raise configuration/service errors
                self.logger.error(f"Failed to create academic tracker: {e}", exc_info=True)
                raise
            except ValuationEngineError as e:
                # Re-raise valuation engine errors
                raise

        return self.academic_tracker

    def get_validation_engine(self):
        """Get validation engine instance"""
        return self.validation_engine

