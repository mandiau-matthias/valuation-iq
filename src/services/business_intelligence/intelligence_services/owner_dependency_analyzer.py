"""
Owner Dependency Analyzer Service

BANK-GRADE SRP-COMPLIANT: Owner dependency analysis ONLY

WHAT: Analyzes owner dependency and its impact on business value
WHY: Single responsibility - owner dependency assessment
HOW: Evaluates owner involvement, transferability, and succession planning

SINGLE RESPONSIBILITY: Owner dependency analysis
- Owner involvement assessment
- Transferability evaluation
- Risk scoring
- Mitigation strategy generation

EXTRACTED FROM: BusinessTypeIntelligenceService (780 lines)
COMPLIANCE: Bank-Grade Excellence Framework - SRP Phase 1
"""

from typing import Dict, Any, List, Optional
from decimal import Decimal
from src.utils.logging import get_logger
from src.utils.decimal_helpers import to_decimal

logger = get_logger(__name__)


class OwnerAdjustments:
    """Owner dependency adjustments for valuation methodology"""
    def __init__(
        self,
        dcf_factor: Decimal,
        multiples_factor: Decimal,
        dependency_score: Decimal,
        risk_mitigation_factor: Decimal
    ):
        self.dcf_factor = dcf_factor
        self.multiples_factor = multiples_factor
        self.dependency_score = dependency_score
        self.risk_mitigation_factor = risk_mitigation_factor


class OwnerDependencyAnalysis:
    """Owner dependency analysis result"""
    def __init__(
        self,
        dependency_score: Decimal,
        dependency_level: str,
        transferability_score: Decimal,
        risk_score: Decimal,
        mitigation_strategies: List[str],
        valuation_impact: Decimal,
        key_risks: List[str]
    ):
        self.dependency_score = dependency_score
        self.dependency_level = dependency_level
        self.transferability_score = transferability_score
        self.risk_score = risk_score
        self.mitigation_strategies = mitigation_strategies
        self.valuation_impact = valuation_impact
        self.key_risks = key_risks


class OwnerDependencyAnalyzer:
    """
    BANK-GRADE SRP-COMPLIANT: Owner dependency analysis.
    
    SINGLE RESPONSIBILITY: Analyze owner dependency ONLY.
    
    This service focuses solely on assessing how dependent a business is
    on its owner, evaluating transferability, and identifying risks and
    mitigation strategies.
    
    Design Pattern: Service Pattern
    - Separates owner analysis from business analysis
    - Enables independent testing and optimization
    - Allows extending with new dependency metrics
    
    Responsibilities:
    - Owner involvement assessment
    - Transferability evaluation
    - Dependency risk scoring
    - Mitigation strategy generation
    """
    
    def __init__(self):
        """
        Initialize owner dependency analyzer.
        
        SRP: Focused on owner dependency analysis only
        """
        self.logger = logger
        
        # Dependency thresholds (configurable)
        self.high_dependency_threshold = Decimal('0.7')
        self.medium_dependency_threshold = Decimal('0.4')
        self.high_risk_threshold = Decimal('0.6')
        
        self.logger.info("✅ [OWNER-DEPENDENCY] OwnerDependencyAnalyzer initialized (SRP-compliant)")
    
    async def analyze_owner_dependency(
        self,
        owner_profile: Dict[str, Any],
        business_type: str,
        business_characteristics: Optional[Dict[str, Any]] = None
    ) -> OwnerDependencyAnalysis:
        """
        Analyze owner dependency for a business.
        
        SRP: Only analyzes dependency, doesn't make valuation decisions.
        
        Args:
            owner_profile: Owner information including:
                - involvement_level: Daily involvement (0-1)
                - key_skills: Owner's critical skills
                - succession_plan: Existence of succession plan
                - years_experience: Owner's years in business
            business_type: Business type identifier
            business_characteristics: Business characteristics (optional)
            
        Returns:
            OwnerDependencyAnalysis containing:
            - dependency_score: Overall dependency score (0-1)
            - dependency_level: Low/Medium/High
            - transferability_score: How transferable is the business (0-1)
            - risk_score: Risk from owner dependency (0-1)
            - mitigation_strategies: List of recommended strategies
        """
        self.logger.info(
            f"🔍 [OWNER-DEPENDENCY] Analyzing owner dependency",
            extra={
                'business_type': business_type,
                'has_succession_plan': owner_profile.get('succession_plan', False)
            }
        )
        
        # Calculate dependency score
        dependency_score = self._calculate_dependency_score(owner_profile, business_type)
        
        # Determine dependency level
        dependency_level = self._determine_dependency_level(dependency_score)
        
        # Calculate transferability
        transferability_score = self.assess_transferability(owner_profile, business_characteristics)
        
        # Calculate risk score
        risk_score = self.calculate_risk_score(dependency_score, transferability_score)
        
        # Generate mitigation strategies
        mitigation_strategies = self.generate_mitigation_strategies(
            dependency_level,
            owner_profile,
            business_type
        )
        
        # Calculate valuation impact
        valuation_impact = self._calculate_valuation_impact(dependency_score, risk_score)
        
        # Identify key risks
        key_risks = self._identify_key_risks(dependency_score, transferability_score, owner_profile)
        
        analysis = OwnerDependencyAnalysis(
            dependency_score=dependency_score,
            dependency_level=dependency_level,
            transferability_score=transferability_score,
            risk_score=risk_score,
            mitigation_strategies=mitigation_strategies,
            valuation_impact=valuation_impact,
            key_risks=key_risks
        )
        
        self.logger.info(
            f"✅ [OWNER-DEPENDENCY] Analysis complete",
            extra={
                'dependency_score': float(dependency_score),
                'dependency_level': dependency_level,
                'risk_score': float(risk_score)
            }
        )
        
        return analysis
    
    def assess_transferability(
        self,
        owner_profile: Dict[str, Any],
        business_characteristics: Optional[Dict[str, Any]] = None
    ) -> Decimal:
        """
        Assess business transferability.
        
        SRP: Only assesses transferability, doesn't make decisions.
        
        Args:
            owner_profile: Owner information
            business_characteristics: Business characteristics (optional)
            
        Returns:
            Transferability score (0-1, higher is more transferable)
        """
        self.logger.info(
            "🔍 [OWNER-DEPENDENCY] Assessing transferability",
            extra={'has_succession_plan': owner_profile.get('succession_plan', False)}
        )
        
        score = Decimal('0.5')  # Base transferability
        
        # Succession plan significantly improves transferability
        if owner_profile.get('succession_plan', False):
            score += Decimal('0.3')
        
        # Lower involvement improves transferability
        involvement_level = to_decimal(owner_profile.get('involvement_level', 0.7))
        score += (Decimal('1.0') - involvement_level) * Decimal('0.2')
        
        # Documented processes improve transferability
        if owner_profile.get('documented_processes', False):
            score += Decimal('0.15')
        
        # Management team reduces dependency
        if owner_profile.get('management_team_size', 0) > 2:
            score += Decimal('0.15')
        elif owner_profile.get('management_team_size', 0) > 0:
            score += Decimal('0.08')
        
        # Business characteristics impact
        if business_characteristics:
            growth_stage = business_characteristics.get('growth_stage', 'Growth')
            if growth_stage == 'Mature':
                score += Decimal('0.1')  # Mature businesses often more transferable
        
        # Cap at 1.0
        score = min(score, Decimal('1.0'))
        
        self.logger.info(
            f"✅ [OWNER-DEPENDENCY] Transferability: {float(score):.2f}",
            extra={'score': float(score)}
        )
        
        return score
    
    def calculate_risk_score(
        self,
        dependency_score: Decimal,
        transferability_score: Decimal
    ) -> Decimal:
        """
        Calculate risk score from owner dependency.
        
        SRP: Only calculates risk, doesn't make decisions.
        
        Args:
            dependency_score: Owner dependency score
            transferability_score: Business transferability score
            
        Returns:
            Risk score (0-1, higher is more risky)
        """
        self.logger.info(
            "🔍 [OWNER-DEPENDENCY] Calculating risk score",
            extra={
                'dependency': float(dependency_score),
                'transferability': float(transferability_score)
            }
        )
        
        # High dependency + low transferability = high risk
        risk = (dependency_score * Decimal('0.7')) + ((Decimal('1.0') - transferability_score) * Decimal('0.3'))
        
        # Cap at 1.0
        risk = min(risk, Decimal('1.0'))
        
        self.logger.info(
            f"✅ [OWNER-DEPENDENCY] Risk score: {float(risk):.2f}",
            extra={'score': float(risk)}
        )
        
        return risk
    
    def generate_mitigation_strategies(
        self,
        dependency_level: str,
        owner_profile: Dict[str, Any],
        business_type: str
    ) -> List[str]:
        """
        Generate mitigation strategies for owner dependency.
        
        SRP: Only generates strategies, doesn't implement them.
        
        Args:
            dependency_level: Low/Medium/High
            owner_profile: Owner information
            business_type: Business type identifier
            
        Returns:
            List of recommended mitigation strategies
        """
        self.logger.info(
            f"🔍 [OWNER-DEPENDENCY] Generating mitigation strategies",
            extra={'dependency_level': dependency_level}
        )
        
        strategies = []
        
        if dependency_level == 'High':
            strategies.extend([
                "Develop comprehensive succession plan immediately",
                "Document all critical business processes and knowledge",
                "Build strong management team to reduce single-point dependency",
                "Create detailed standard operating procedures (SOPs)"
            ])
            
            if not owner_profile.get('succession_plan', False):
                strategies.append("Identify and train potential successor")
            
            if owner_profile.get('involvement_level', 0.7) > 0.8:
                strategies.append("Gradually reduce owner's daily operational involvement")
        
        elif dependency_level == 'Medium':
            strategies.extend([
                "Create succession plan to prepare for future transition",
                "Document key business processes",
                "Strengthen management team capabilities"
            ])
            
            if not owner_profile.get('documented_processes', False):
                strategies.append("Implement process documentation system")
        
        else:  # Low dependency
            strategies.extend([
                "Maintain current low dependency levels",
                "Continue investing in team development",
                "Regular succession plan reviews"
            ])
        
        # Business-type specific strategies
        if business_type in ['saas', 'software', 'b2b_saas']:
            strategies.append("Ensure technical knowledge is documented and shared")
        elif business_type in ['restaurant', 'catering']:
            strategies.append("Develop clear recipes and service procedures")
        elif business_type in ['consulting', 'legal', 'accounting']:
            strategies.append("Build client relationships beyond owner")
        
        self.logger.info(
            f"✅ [OWNER-DEPENDENCY] Generated {len(strategies)} strategies",
            extra={'count': len(strategies)}
        )
        
        return strategies
    
    def calculate_owner_adjustments(
        self,
        owner_profile: Dict[str, Any],
        historical_analysis: Optional[Any] = None
    ) -> OwnerAdjustments:
        """
        Calculate owner dependency adjustments for methodology selection.
        
        SRP: Only calculates adjustments, doesn't select methodology.
        
        Args:
            owner_profile: Owner information
            historical_analysis: Historical data analysis (optional)
            
        Returns:
            OwnerAdjustments with methodology adjustment factors
        """
        self.logger.info(
            "🔍 [OWNER-DEPENDENCY] Calculating owner adjustments",
            extra={'owner_profile_keys': list(owner_profile.keys())}
        )
        
        dependency_score = to_decimal(owner_profile.get("dependency_score", 0.5))
        
        # DCF adjustments (high dependency reduces DCF weight)
        dcf_factor = Decimal('1.0') - (dependency_score * Decimal('0.5'))
        
        # Multiples adjustments (high dependency slightly increases multiples weight)
        multiples_factor = Decimal('1.0') + (dependency_score * Decimal('0.2'))
        
        # Risk mitigation factor
        risk_mitigation = Decimal('1.0') - (dependency_score * Decimal('0.3'))
        
        adjustments = OwnerAdjustments(
            dcf_factor=max(dcf_factor, Decimal('0.3')),  # Minimum 30% weight
            multiples_factor=min(multiples_factor, Decimal('1.5')),  # Maximum 150% weight
            dependency_score=dependency_score,
            risk_mitigation_factor=risk_mitigation
        )
        
        self.logger.info(
            f"✅ [OWNER-DEPENDENCY] Owner adjustments calculated",
            extra={
                'dcf_factor': float(adjustments.dcf_factor),
                'multiples_factor': float(adjustments.multiples_factor)
            }
        )
        
        return adjustments
    
    def _calculate_dependency_score(
        self,
        owner_profile: Dict[str, Any],
        business_type: str
    ) -> Decimal:
        """Calculate overall owner dependency score (0-1)"""
        
        # Start with involvement level
        involvement = to_decimal(owner_profile.get('involvement_level', 0.7))
        
        # Adjust based on succession plan
        if owner_profile.get('succession_plan', False):
            involvement *= Decimal('0.7')  # Reduce dependency
        
        # Adjust based on management team
        team_size = owner_profile.get('management_team_size', 0)
        if team_size > 2:
            involvement *= Decimal('0.6')
        elif team_size > 0:
            involvement *= Decimal('0.8')
        
        # Adjust based on documented processes
        if owner_profile.get('documented_processes', False):
            involvement *= Decimal('0.8')
        
        # Business type specific adjustments
        if business_type in ['consulting', 'legal', 'accounting']:
            involvement *= Decimal('1.2')  # Higher typical dependency
        elif business_type in ['saas', 'software']:
            involvement *= Decimal('0.9')  # Lower typical dependency
        
        return min(involvement, Decimal('1.0'))
    
    def _determine_dependency_level(self, dependency_score: Decimal) -> str:
        """Determine dependency level from score"""
        if dependency_score >= self.high_dependency_threshold:
            return 'High'
        elif dependency_score >= self.medium_dependency_threshold:
            return 'Medium'
        else:
            return 'Low'
    
    def _calculate_valuation_impact(
        self,
        dependency_score: Decimal,
        risk_score: Decimal
    ) -> Decimal:
        """Calculate impact on valuation (negative impact as decimal)"""
        # High dependency and risk reduce valuation
        impact = -((dependency_score * Decimal('0.15')) + (risk_score * Decimal('0.10')))
        return impact
    
    def _identify_key_risks(
        self,
        dependency_score: Decimal,
        transferability_score: Decimal,
        owner_profile: Dict[str, Any]
    ) -> List[str]:
        """Identify key risks from owner dependency"""
        risks = []
        
        if dependency_score > self.high_dependency_threshold:
            risks.append("High owner dependency - significant business continuity risk")
        
        if transferability_score < Decimal('0.4'):
            risks.append("Low transferability - difficult to sell or transition business")
        
        if not owner_profile.get('succession_plan', False):
            risks.append("No succession plan - unprepared for owner exit")
        
        if owner_profile.get('management_team_size', 0) == 0:
            risks.append("No management team - single point of failure")
        
        return risks
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get service statistics.
        
        Returns:
            Dict containing:
            - service_name: Name of this service
            - responsibility: Single responsibility description
            - thresholds: Configuration thresholds
            - status: Operational status
        """
        return {
            'service_name': 'OwnerDependencyAnalyzer',
            'responsibility': 'Owner dependency analysis',
            'thresholds': {
                'high_dependency': float(self.high_dependency_threshold),
                'medium_dependency': float(self.medium_dependency_threshold),
                'high_risk': float(self.high_risk_threshold)
            },
            'status': 'operational',
            'srp_compliant': True
        }
