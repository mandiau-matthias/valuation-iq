"""
Owner Profiling Engine - Stateless Implementation

BRAIN & MUSCLE ARCHITECTURE:
ValuationIQ (The Muscle) is a stateless calculation engine.
Owner profiling data comes from Titan via the CalculateRequest payload.

This service provides:
- Owner dependency score calculation
- Valuation adjustment factors
- Transferability risk assessment
- NO database queries (all data comes from request payload)

Profile persistence is handled by Titan (The Brain).

@author UpSwitch CTO Team
@version 2.0.0 - Brain & Muscle Stateless
"""

from decimal import Decimal
from typing import Dict, Any, List, Optional
from datetime import datetime
from dataclasses import dataclass
from enum import Enum
import logging

from src.utils.decimal_helpers import to_decimal, from_decimal

logger = logging.getLogger(__name__)


class DependencyLevel(Enum):
    """Owner dependency levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class TransferabilityRisk(Enum):
    """Transferability risk levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class SuccessionReadiness(Enum):
    """Succession readiness levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass
class OwnerProfile:
    """Owner profile data structure (from request payload)"""
    hours_per_week: int = 40
    primary_tasks: List[str] = None
    delegation_capability: int = 5
    succession_plan: bool = False
    succession_details: Optional[str] = None
    
    def __post_init__(self):
        if self.primary_tasks is None:
            self.primary_tasks = []
    
    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> "OwnerProfile":
        """Create OwnerProfile from dictionary payload."""
        if not data:
            return cls()
        
        return cls(
            hours_per_week=data.get("hours_per_week", 40),
            primary_tasks=data.get("primary_tasks", []),
            delegation_capability=data.get("delegation_capability", 5),
            succession_plan=data.get("succession_plan", False),
            succession_details=data.get("succession_details"),
        )


@dataclass
class OwnerImpactAssessment:
    """Owner impact assessment result"""
    dependency_score: Decimal
    adjustment_factor: Decimal
    transferability_risk: TransferabilityRisk
    succession_readiness: SuccessionReadiness
    key_risks: List[str]
    recommendations: List[str]
    impact_summary: str
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "dependency_score": float(self.dependency_score),
            "adjustment_factor": float(self.adjustment_factor),
            "transferability_risk": self.transferability_risk.value,
            "succession_readiness": self.succession_readiness.value,
            "key_risks": self.key_risks,
            "recommendations": self.recommendations,
            "impact_summary": self.impact_summary,
        }


class OwnerProfilingEngine:
    """
    Stateless Owner Profiling Engine.
    
    BRAIN & MUSCLE ARCHITECTURE:
    - All owner data comes from the request payload
    - No database queries
    - Pure calculation logic only
    
    Profile persistence is handled by Titan (The Brain).
    """

    def __init__(self):
        """Initialize owner profiling engine (stateless)."""
        self.dependency_weights = {
            "hours_per_week": Decimal('0.4'),
            "delegation_capability": Decimal('0.4'),
            "succession_plan": Decimal('0.2')
        }

        self.adjustment_thresholds = {
            "high_dependency": Decimal('0.7'),
            "medium_dependency": Decimal('0.4')
        }

        self.adjustment_factors = {
            "high_dependency": -Decimal('0.15'),  # 15% reduction
            "medium_dependency": -Decimal('0.05'),  # 5% reduction
            "low_dependency": Decimal('0.0')  # No adjustment
        }

        logger.info("OwnerProfilingEngine initialized (stateless mode)")

    def assess_owner_impact(
        self,
        owner_data: Optional[Dict[str, Any]] = None,
    ) -> OwnerImpactAssessment:
        """
        Assess owner impact on valuation from request payload.
        
        BRAIN & MUSCLE: Owner data comes from Titan via the payload.
        
        Args:
            owner_data: Owner profiling data from request payload
            
        Returns:
            OwnerImpactAssessment with calculated metrics
        """
        profile = OwnerProfile.from_dict(owner_data)
        
        # Calculate dependency score
        dependency_score = self._calculate_dependency_score(
            profile.hours_per_week,
            profile.delegation_capability,
            profile.succession_plan
        )

        # Determine dependency level
        dependency_level = self._determine_dependency_level(dependency_score)

        # Calculate adjustment factor
        adjustment_factor = self._calculate_adjustment_factor(dependency_level)

        # Assess transferability risk
        transferability_risk = self._assess_transferability_risk(
            profile.hours_per_week,
            profile.delegation_capability,
            profile.succession_plan
        )

        # Assess succession readiness
        succession_readiness = self._assess_succession_readiness(
            profile.delegation_capability,
            profile.succession_plan,
            profile.succession_details
        )

        # Generate key risks
        key_risks = self._identify_key_risks(profile, dependency_level)

        # Generate recommendations
        recommendations = self._generate_recommendations(profile, dependency_level)

        # Generate impact summary
        impact_summary = self._generate_impact_summary(
            dependency_score, adjustment_factor, transferability_risk
        )

        return OwnerImpactAssessment(
            dependency_score=dependency_score,
            adjustment_factor=adjustment_factor,
            transferability_risk=transferability_risk,
            succession_readiness=succession_readiness,
            key_risks=key_risks,
            recommendations=recommendations,
            impact_summary=impact_summary
        )

    def get_valuation_adjustment(
        self,
        owner_data: Optional[Dict[str, Any]] = None
    ) -> Decimal:
        """
        Get the valuation adjustment factor for owner dependency.
        
        Args:
            owner_data: Owner profiling data from request payload
            
        Returns:
            Adjustment factor (e.g., -0.15 for 15% reduction)
        """
        assessment = self.assess_owner_impact(owner_data)
        return assessment.adjustment_factor

    def _calculate_dependency_score(
        self, 
        hours_per_week: int, 
        delegation_capability: int, 
        succession_plan: bool
    ) -> Decimal:
        """
        Calculate owner dependency score (0-1).
        
        Higher score = more dependent on owner
        """
        # Hours factor (0-1, normalized to 40 hours)
        hours_decimal = Decimal(str(hours_per_week))
        hours_factor = min(hours_decimal / Decimal('40'), Decimal('1.0'))

        # Delegation factor (0-1, inverted - lower capability = higher dependency)
        delegation_decimal = Decimal(str(delegation_capability))
        delegation_factor = Decimal('1') - (delegation_decimal / Decimal('10'))

        # Succession factor (0-1, inverted - no plan = higher dependency)
        succession_factor = Decimal('0') if succession_plan else Decimal('1')

        # Weighted average
        dependency_score = (
            hours_factor * self.dependency_weights["hours_per_week"] +
            delegation_factor * self.dependency_weights["delegation_capability"] +
            succession_factor * self.dependency_weights["succession_plan"]
        )

        # Clamp to 0-1 range
        return min(max(dependency_score, Decimal('0')), Decimal('1'))

    def _determine_dependency_level(self, dependency_score: Decimal) -> DependencyLevel:
        """Determine dependency level based on score."""
        if dependency_score >= self.adjustment_thresholds["high_dependency"]:
            return DependencyLevel.HIGH
        elif dependency_score >= self.adjustment_thresholds["medium_dependency"]:
            return DependencyLevel.MEDIUM
        else:
            return DependencyLevel.LOW

    def _calculate_adjustment_factor(self, dependency_level: DependencyLevel) -> Decimal:
        """Calculate valuation adjustment factor."""
        return self.adjustment_factors[f"{dependency_level.value}_dependency"]

    def _assess_transferability_risk(
        self, 
        hours_per_week: int, 
        delegation_capability: int, 
        succession_plan: bool
    ) -> TransferabilityRisk:
        """Assess business transferability risk."""
        risk_score = 0

        # Hours risk
        if hours_per_week > 50:
            risk_score += 3
        elif hours_per_week > 40:
            risk_score += 2
        elif hours_per_week > 30:
            risk_score += 1

        # Delegation risk
        if delegation_capability < 3:
            risk_score += 3
        elif delegation_capability < 5:
            risk_score += 2
        elif delegation_capability < 7:
            risk_score += 1

        # Succession risk
        if not succession_plan:
            risk_score += 2

        # Determine risk level
        if risk_score >= 6:
            return TransferabilityRisk.HIGH
        elif risk_score >= 3:
            return TransferabilityRisk.MEDIUM
        else:
            return TransferabilityRisk.LOW

    def _assess_succession_readiness(
        self,
        delegation_capability: int,
        succession_plan: bool,
        succession_details: Optional[str]
    ) -> SuccessionReadiness:
        """Assess succession readiness."""
        readiness_score = 0

        # Delegation capability contributes to readiness
        if delegation_capability >= 7:
            readiness_score += 3
        elif delegation_capability >= 5:
            readiness_score += 2
        elif delegation_capability >= 3:
            readiness_score += 1

        # Succession plan exists
        if succession_plan:
            readiness_score += 2
            # Detailed plan is better
            if succession_details and len(succession_details) > 50:
                readiness_score += 1

        # Determine readiness level
        if readiness_score >= 5:
            return SuccessionReadiness.HIGH
        elif readiness_score >= 3:
            return SuccessionReadiness.MEDIUM
        else:
            return SuccessionReadiness.LOW

    def _identify_key_risks(
        self,
        profile: OwnerProfile,
        dependency_level: DependencyLevel
    ) -> List[str]:
        """Identify key owner-related risks."""
        risks = []

        if profile.hours_per_week > 50:
            risks.append("Owner works excessive hours (>50/week) - high operational dependency")

        if profile.delegation_capability < 4:
            risks.append("Limited delegation capability - key person risk")

        if not profile.succession_plan:
            risks.append("No succession plan in place - transition risk")

        if dependency_level == DependencyLevel.HIGH:
            risks.append("High owner dependency may significantly reduce buyer interest")

        if len(profile.primary_tasks) > 5:
            risks.append("Owner handles many different tasks - knowledge concentration risk")

        return risks

    def _generate_recommendations(
        self,
        profile: OwnerProfile,
        dependency_level: DependencyLevel
    ) -> List[str]:
        """Generate recommendations for reducing owner dependency."""
        recommendations = []

        if profile.hours_per_week > 40:
            recommendations.append(
                "Reduce owner involvement by delegating routine tasks to staff"
            )

        if profile.delegation_capability < 5:
            recommendations.append(
                "Develop management team to improve delegation capability"
            )

        if not profile.succession_plan:
            recommendations.append(
                "Create a formal succession plan to reduce transition risk"
            )

        if dependency_level in [DependencyLevel.HIGH, DependencyLevel.MEDIUM]:
            recommendations.append(
                "Document key processes and SOPs to reduce knowledge dependency"
            )
            recommendations.append(
                "Consider hiring or promoting a manager to handle day-to-day operations"
            )

        return recommendations

    def _generate_impact_summary(
        self,
        dependency_score: Decimal,
        adjustment_factor: Decimal,
        transferability_risk: TransferabilityRisk
    ) -> str:
        """Generate a summary of owner impact on valuation."""
        adjustment_pct = abs(float(adjustment_factor) * 100)
        
        if adjustment_factor == Decimal('0'):
            return (
                f"Low owner dependency ({float(dependency_score):.1%}). "
                f"No valuation adjustment required. "
                f"Transferability risk: {transferability_risk.value}."
            )
        else:
            return (
                f"Owner dependency score: {float(dependency_score):.1%}. "
                f"Recommended valuation adjustment: -{adjustment_pct:.0f}%. "
                f"Transferability risk: {transferability_risk.value}. "
                f"Consider reducing owner involvement before sale."
            )


# Module-level convenience functions

def calculate_owner_adjustment(owner_data: Optional[Dict[str, Any]] = None) -> Decimal:
    """
    Calculate owner adjustment factor from payload data.
    
    Args:
        owner_data: Owner profiling data from request
        
    Returns:
        Adjustment factor (e.g., -0.15 for 15% reduction)
    """
    engine = OwnerProfilingEngine()
    return engine.get_valuation_adjustment(owner_data)


def assess_owner_impact(owner_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Assess owner impact and return as dictionary.
    
    Args:
        owner_data: Owner profiling data from request
        
    Returns:
        Dictionary with assessment results
    """
    engine = OwnerProfilingEngine()
    assessment = engine.assess_owner_impact(owner_data)
    return assessment.to_dict()
