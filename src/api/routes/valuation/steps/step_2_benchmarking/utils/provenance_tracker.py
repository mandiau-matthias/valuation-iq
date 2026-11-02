"""
Step 2 Calculation Provenance Tracker

Tracks the complete provenance of all calculations and data sources.
Provides full audit trail for bank-grade transparency.
"""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, Optional


class Step2ProvenanceTracker:
    """Tracks calculation provenance for Step 2."""
    
    def __init__(self, correlation_id: Optional[str] = None):
        """
        Initialize provenance tracker.
        
        Args:
            correlation_id: Correlation ID for this calculation
        """
        self.correlation_id = correlation_id
        self.provenance: Dict[str, Any] = {
            "correlation_id": correlation_id,
            "calculation_timestamp": datetime.now(timezone.utc).isoformat(),
            "steps": [],
        }
    
    def track_multiples_selection(
        self,
        data_source: str,
        multiples_data: Dict[str, Any],
        priority: Optional[int] = None,
        fallback_used: bool = False,
    ) -> None:
        """
        Track multiples selection with full provenance.
        
        Args:
            data_source: Source of multiples (e.g., "business_type_db", "fmp_api")
            multiples_data: The multiples data selected
            priority: Priority level used (0 = highest)
            fallback_used: Whether fallback was used
        """
        step_provenance = {
            "step": "select_multiples",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data_source": data_source,
            "data_source_details": multiples_data.get("data_source_details", {}),
            "priority": priority,
            "fallback_used": fallback_used,
            "multiples": {
                "ev_ebitda": str(multiples_data.get("ev_ebitda")) if multiples_data.get("ev_ebitda") else None,
                "ev_revenue": str(multiples_data.get("ev_revenue")) if multiples_data.get("ev_revenue") else None,
                "pe_ratio": str(multiples_data.get("pe_ratio")) if multiples_data.get("pe_ratio") else None,
                "ev_ebitda_percentile_source": multiples_data.get("ev_ebitda_percentile_source"),
                "ev_revenue_percentile_source": multiples_data.get("ev_revenue_percentile_source"),
            },
            "confidence": (
                "high"
                if data_source in ("titan_enrichment", "delphi-resolved-benchmark")
                else "medium" if not fallback_used else "low"
            ),
        }
        self.provenance["steps"].append(step_provenance)
    
    def track_sme_calibration(
        self,
        calibration_applied: bool,
        calibration_data: Dict[str, Any],
    ) -> None:
        """Track SME calibration application."""
        step_provenance = {
            "step": "sme_calibration",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "calibration_applied": calibration_applied,
            "calibration_data": calibration_data,
        }
        self.provenance["steps"].append(step_provenance)
    
    def track_primary_method_selection(
        self,
        primary_method: str,
        factors: Dict[str, Any],
    ) -> None:
        """Track primary method selection with factors."""
        step_provenance = {
            "step": "primary_method_selection",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "primary_method": primary_method,
            "factors": factors,
        }
        self.provenance["steps"].append(step_provenance)
    
    def track_recovery(
        self,
        recovery_method: str,
        backup_available: bool,
        error_type: str,
    ) -> None:
        """Track recovery operations."""
        step_provenance = {
            "step": "recovery",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "recovery_method": recovery_method,
            "backup_available": backup_available,
            "error_type": error_type,
            "recovery_applied": True,
        }
        self.provenance["steps"].append(step_provenance)
    
    def get_provenance(self) -> Dict[str, Any]:
        """Get complete provenance dictionary."""
        return self.provenance.copy()
    
    def add_to_result_dict(self, result_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        Add provenance to result dictionary.
        
        Args:
            result_dict: Result dictionary to enhance
            
        Returns:
            Result dictionary with provenance added
        """
        result_dict["calculation_provenance"] = self.get_provenance()
        return result_dict
