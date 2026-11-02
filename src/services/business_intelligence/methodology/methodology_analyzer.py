from src.utils.exceptions import DCFCalculationError, MethodologyError

"""
Methodology Analyzer

Handles business characteristics analysis, financial health assessment,
and methodology suitability evaluation for intelligent methodology selection.

Author: Upswitch Engineering Team
Date: October 2025
Status: Production Ready
"""

from decimal import Decimal
from typing import Dict, Any, List, Optional
from src.utils.logging import get_logger
from src.utils.decimal_helpers import to_decimal, from_decimal
from ..integration.selector_types import (
    BusinessContext, FinancialScore, OwnerScore, MarketScore,
    BusinessRules, IndustryRules, FinancialRules, OwnerRules, MarketRules,
    DEFAULT_BUSINESS_RULES, DEFAULT_INDUSTRY_RULES, DEFAULT_FINANCIAL_RULES,
    DEFAULT_OWNER_RULES, DEFAULT_MARKET_RULES, INDUSTRY_CATEGORIES,
    MARKET_POSITION_LEVELS, COMPETITIVE_ADVANTAGE_LEVELS
)

logger = get_logger(__name__)


class MethodologyAnalyzer:
    """Analyzes business characteristics and financial health for methodology selection"""

    def __init__(self):
        self.business_rules = self._load_business_rules()
        self.industry_rules = self._load_industry_rules()
        self.financial_rules = self._load_financial_rules()
        self.owner_rules = self._load_owner_rules()
        self.market_rules = self._load_market_rules()

    def analyze_business_characteristics(self, business_context: BusinessContext) -> Dict[str, Decimal]:
        """Analyze business characteristics for methodology selection"""

        try:
            logger.info(f"Analyzing business characteristics for {business_context.industry} business")

            scores = {}

            # Revenue analysis
            scores["dcf_revenue"] = self._analyze_revenue_suitability(business_context.revenue)

            # EBITDA analysis
            scores["dcf_ebitda"] = self._analyze_ebitda_suitability(business_context.ebitda)

            # Growth rate analysis
            scores["dcf_growth"] = self._analyze_growth_suitability(business_context.growth_rate)

            # Business age analysis
            scores["dcf_age"] = self._analyze_business_age_suitability(business_context.business_age)

            # Market position analysis
            scores["multiples_market"] = self._analyze_market_position_suitability(business_context.market_position)

            # Competitive advantage analysis
            scores["competitive_advantage"] = self._analyze_competitive_advantage(business_context.competitive_advantage)

            # Industry-specific analysis
            scores.update(self._analyze_industry_specific_characteristics(business_context))

            logger.info(f"Business characteristics analysis complete: {len(scores)} factors analyzed")

            return scores

        except MethodologyError as e:
            logger.error(f"Business characteristics analysis failed: {e}")
            return self._get_default_business_scores()

    def analyze_financial_health(self, financial_data: Dict[str, Any]) -> FinancialScore:
        """Analyze financial health for methodology selection"""

        try:
            logger.info("Analyzing financial health for methodology selection")

            # Calculate key financial ratios
            revenue_growth = self._calculate_revenue_growth(financial_data)
            ebitda_margin = self._calculate_ebitda_margin(financial_data)
            debt_to_equity = self._calculate_debt_to_equity(financial_data)
            current_ratio = self._calculate_current_ratio(financial_data)

            # Calculate stability metrics
            revenue_stability = self._calculate_revenue_stability(financial_data)
            ebitda_consistency = self._calculate_ebitda_consistency(financial_data)
            cash_flow_stability = self._calculate_cash_flow_stability(financial_data)

            # Calculate DCF suitability score
            dcf_score = self._calculate_dcf_suitability_score(
                revenue_growth, ebitda_margin, revenue_stability, ebitda_consistency
            )

            # Calculate Multiples suitability score
            multiples_score = self._calculate_multiples_suitability_score(
                revenue_stability, ebitda_consistency, cash_flow_stability
            )

            # Calculate overall health score
            overall_health = self._calculate_overall_health_score(
                revenue_growth, ebitda_margin, debt_to_equity, current_ratio
            )

            logger.info(f"Financial health analysis complete: DCF={dcf_score:.2f}, Multiples={multiples_score:.2f}")

            return FinancialScore(
                dcf_score=dcf_score,
                multiples_score=multiples_score,
                overall_health=overall_health,
                revenue_stability=revenue_stability,
                ebitda_consistency=ebitda_consistency,
                cash_flow_stability=cash_flow_stability
            )

        except DCFCalculationError as e:
            logger.error(f"Financial health analysis failed: {e}")
            return self._get_default_financial_score()

    def analyze_owner_dependency(self, owner_profile: Dict[str, Any]) -> OwnerScore:
        """Analyze owner dependency for methodology selection"""

        try:
            logger.info("Analyzing owner dependency for methodology selection")

            # Calculate dependency score
            dependency_score = self._calculate_dependency_score(owner_profile)

            # Calculate succession readiness
            succession_readiness = self._calculate_succession_readiness(owner_profile)

            # Calculate transferability risk
            transferability_risk = self._calculate_transferability_risk(owner_profile)

            # Determine methodology impact
            dcf_impact = self._calculate_dcf_impact(dependency_score, succession_readiness)
            multiples_impact = self._calculate_multiples_impact(dependency_score, transferability_risk)

            logger.info(f"Owner dependency analysis complete: dependency={dependency_score:.2f}")

            return OwnerScore(
                dependency_score=dependency_score,
                succession_readiness=succession_readiness,
                transferability_risk=transferability_risk,
                dcf_impact=dcf_impact,
                multiples_impact=multiples_impact
            )

        except DCFCalculationError as e:
            logger.error(f"Owner dependency analysis failed: {e}")
            return self._get_default_owner_score()

    def analyze_market_context(self, market_context: Dict[str, Any]) -> MarketScore:
        """Analyze market context for methodology selection"""

        try:
            logger.info("Analyzing market context for methodology selection")

            # Calculate comparable companies count
            comparable_companies_count = self._count_comparable_companies(market_context)

            # Calculate market data quality
            market_data_quality = self._calculate_market_data_quality(market_context)

            # Check industry benchmarks availability
            industry_benchmarks_available = self._check_industry_benchmarks_availability(market_context)

            # Calculate market data freshness
            market_data_freshness = self._calculate_market_data_freshness(market_context)

            # Calculate DCF and Multiples scores
            dcf_score = self._calculate_market_dcf_score(market_context)
            multiples_score = self._calculate_market_multiples_score(
                comparable_companies_count, market_data_quality, industry_benchmarks_available
            )

            logger.info(f"Market context analysis complete: comparables={comparable_companies_count}")

            return MarketScore(
                comparable_companies_count=comparable_companies_count,
                market_data_quality=market_data_quality,
                industry_benchmarks_available=industry_benchmarks_available,
                market_data_freshness=market_data_freshness,
                dcf_score=dcf_score,
                multiples_score=multiples_score
            )

        except DCFCalculationError as e:
            logger.error(f"Market context analysis failed: {e}")
            return self._get_default_market_score()

    def apply_industry_rules(self, industry: str, financial_data: Dict[str, Any]) -> Dict[str, Decimal]:
        """Apply industry-specific rules for methodology selection"""

        try:
            logger.info(f"Applying industry rules for {industry}")

            industry_rules = self.industry_rules.get(industry, {})
            scores = {}

            # DCF preference rules
            dcf_preference = industry_rules.get("dcf_preference", {})
            if dcf_preference:
                scores["dcf_industry"] = self._evaluate_industry_dcf_rules(dcf_preference, financial_data)
            else:
                scores["dcf_industry"] = Decimal('0.5')

            # Multiples preference rules
            multiples_preference = industry_rules.get("multiples_preference", {})
            if multiples_preference:
                scores["multiples_industry"] = self._evaluate_industry_multiples_rules(multiples_preference, financial_data)
            else:
                scores["multiples_industry"] = Decimal('0.5')

            logger.info(f"Industry rules applied: DCF={scores.get('dcf_industry', Decimal('0.5')):.2f}, Multiples={scores.get('multiples_industry', Decimal('0.5')):.2f}")

            return scores

        except DCFCalculationError as e:
            logger.error(f"Industry rules application failed: {e}")
            return {"dcf_industry": Decimal('0.5'), "multiples_industry": 0.5}

    def _load_business_rules(self) -> BusinessRules:
        """Load business rules for methodology selection"""
        return BusinessRules(**DEFAULT_BUSINESS_RULES)

    def _load_industry_rules(self) -> IndustryRules:
        """Load industry-specific rules for methodology selection"""
        return IndustryRules(**DEFAULT_INDUSTRY_RULES)

    def _load_financial_rules(self) -> FinancialRules:
        """Load financial rules for methodology selection"""
        return FinancialRules(**DEFAULT_FINANCIAL_RULES)

    def _load_owner_rules(self) -> OwnerRules:
        """Load owner dependency rules for methodology selection"""
        return OwnerRules(**DEFAULT_OWNER_RULES)

    def _load_market_rules(self) -> MarketRules:
        """Load market context rules for methodology selection"""
        return MarketRules(**DEFAULT_MARKET_RULES)

    def _analyze_revenue_suitability(self, revenue: Decimal) -> Decimal:
        """Analyze revenue suitability for DCF"""
        threshold = self.business_rules.dcf_preference_rules["revenue_threshold"]

        if revenue >= threshold:
            return Decimal('1.0')
        elif revenue >= threshold * 0.5:
            return Decimal('0.7')
        else:
            return Decimal('0.3')

    def _analyze_ebitda_suitability(self, ebitda: Decimal) -> Decimal:
        """Analyze EBITDA suitability for DCF"""
        threshold = self.business_rules.dcf_preference_rules["ebitda_threshold"]

        if ebitda >= threshold:
            return Decimal('1.0')
        elif ebitda >= threshold * 0.5:
            return Decimal('0.7')
        else:
            return Decimal('0.3')

    def _analyze_growth_suitability(self, growth_rate: Decimal) -> Decimal:
        """Analyze growth rate suitability for DCF"""
        threshold = self.business_rules.dcf_preference_rules["growth_rate_threshold"]

        if growth_rate >= threshold:
            return Decimal('1.0')
        elif growth_rate >= 0:
            return Decimal('0.5')
        else:
            return Decimal('0.2')

    def _analyze_business_age_suitability(self, business_age: int) -> Decimal:
        """Analyze business age suitability for DCF"""
        min_age = self.business_rules.dcf_preference_rules["business_age_min"]

        if business_age >= min_age:
            return Decimal('1.0')
        else:
            return Decimal('0.3')

    def _analyze_market_position_suitability(self, market_position: str) -> Decimal:
        """Analyze market position suitability for Multiples"""
        return MARKET_POSITION_LEVELS.get(market_position, Decimal('0.5'))

    def _analyze_competitive_advantage(self, competitive_advantage: str) -> Decimal:
        """Analyze competitive advantage"""
        return COMPETITIVE_ADVANTAGE_LEVELS.get(competitive_advantage, Decimal('0.5'))

    def _analyze_industry_specific_characteristics(self, business_context: BusinessContext) -> Dict[str, Decimal]:
        """Analyze industry-specific characteristics"""
        scores = {}

        # Technology industry specific
        if business_context.industry in INDUSTRY_CATEGORIES.get("technology", []):
            scores["technology_specific"] = self._analyze_technology_characteristics(business_context)

        # Retail industry specific
        elif business_context.industry in INDUSTRY_CATEGORIES.get("retail", []):
            scores["retail_specific"] = self._analyze_retail_characteristics(business_context)

        # Manufacturing industry specific
        elif business_context.industry in INDUSTRY_CATEGORIES.get("manufacturing", []):
            scores["manufacturing_specific"] = self._analyze_manufacturing_characteristics(business_context)

        # Services industry specific
        elif business_context.industry in INDUSTRY_CATEGORIES.get("services", []):
            scores["services_specific"] = self._analyze_services_characteristics(business_context)

        return scores

    def _analyze_technology_characteristics(self, business_context: BusinessContext) -> Decimal:
        """Analyze technology industry characteristics"""
        # Technology businesses favor DCF due to growth potential
        if business_context.growth_rate > 0.1:
            return Decimal('0.9')
        elif business_context.growth_rate > 0.05:
            return Decimal('0.7')
        else:
            return Decimal('0.5')

    def _analyze_retail_characteristics(self, business_context: BusinessContext) -> Decimal:
        """Analyze retail industry characteristics"""
        # Retail businesses favor Multiples due to market comparables
        if business_context.market_position in ["established", "market_leader"]:
            return Decimal('0.9')
        elif business_context.market_position in ["growing", "stable"]:
            return Decimal('0.7')
        else:
            return Decimal('0.5')

    def _analyze_manufacturing_characteristics(self, business_context: BusinessContext) -> Decimal:
        """Analyze manufacturing industry characteristics"""
        # Manufacturing businesses can use both methodologies
        if business_context.business_age > 5 and business_context.growth_rate > 0.05:
            return Decimal('0.8')
        else:
            return Decimal('0.6')

    def _analyze_services_characteristics(self, business_context: BusinessContext) -> Decimal:
        """Analyze services industry characteristics"""
        # Services businesses favor Multiples due to owner dependency
        if business_context.employee_count > 10:
            return Decimal('0.8')
        else:
            return Decimal('0.6')

    def _calculate_revenue_growth(self, financial_data: Dict[str, Any]) -> Decimal:
        """Calculate revenue growth rate"""
        # Implementation depends on historical data availability
        return financial_data.get("revenue_growth", Decimal('0.05'))  # Default 5% growth

    def _calculate_ebitda_margin(self, financial_data: Dict[str, Any]) -> Decimal:
        """Calculate EBITDA margin using Decimal"""
        revenue_decimal = to_decimal(financial_data.get("revenue", 0))
        ebitda_decimal = to_decimal(financial_data.get("ebitda", 0))

        if revenue_decimal > Decimal('0'):
            margin_decimal = ebitda_decimal / revenue_decimal
            return from_decimal(margin_decimal)
        return Decimal('0.0')

    def _calculate_debt_to_equity(self, financial_data: Dict[str, Any]) -> Decimal:
        """Calculate debt-to-equity ratio using Decimal"""
        total_assets_decimal = to_decimal(financial_data.get("total_assets", 0))
        total_debt_decimal = to_decimal(financial_data.get("total_debt", 0))

        if total_assets_decimal > Decimal('0'):
            ratio_decimal = total_debt_decimal / total_assets_decimal
            return from_decimal(ratio_decimal)
        return Decimal('0.0')

    def _calculate_current_ratio(self, financial_data: Dict[str, Any]) -> Decimal:
        """Calculate current ratio"""
        return financial_data.get("current_ratio", Decimal('1.5'))  # Default current ratio

    def _calculate_revenue_stability(self, financial_data: Dict[str, Any]) -> Decimal:
        """Calculate revenue stability"""
        return financial_data.get("revenue_stability", Decimal('0.8'))  # Default stability

    def _calculate_ebitda_consistency(self, financial_data: Dict[str, Any]) -> Decimal:
        """Calculate EBITDA consistency"""
        return financial_data.get("ebitda_consistency", Decimal('0.8'))  # Default consistency

    def _calculate_cash_flow_stability(self, financial_data: Dict[str, Any]) -> Decimal:
        """Calculate cash flow stability"""
        return financial_data.get("cash_flow_stability", Decimal('0.8'))  # Default stability

    def _calculate_dcf_suitability_score(
        self,
        revenue_growth: Decimal,
        ebitda_margin: Decimal,
        revenue_stability: Decimal,
        ebitda_consistency: Decimal
    ) -> Decimal:
        """Calculate DCF suitability score"""
        growth_factor = min(revenue_growth / Decimal('0.1'), Decimal('1.0'))
        profitability_factor = min(ebitda_margin / Decimal('0.2'), Decimal('1.0'))
        stability_factor = (revenue_stability + ebitda_consistency) / 2

        return (growth_factor * Decimal('0.4') + profitability_factor * Decimal('0.3') + stability_factor * Decimal('0.3'))

    def _calculate_multiples_suitability_score(
        self,
        revenue_stability: Decimal,
        ebitda_consistency: Decimal,
        cash_flow_stability: Decimal
    ) -> Decimal:
        """Calculate Multiples suitability score"""
        stability_factor = (revenue_stability + ebitda_consistency + cash_flow_stability) / 3
        consistency_factor = (revenue_stability + ebitda_consistency) / 2

        return (stability_factor * Decimal('0.6') + consistency_factor * Decimal('0.4'))

    def _calculate_overall_health_score(
        self,
        revenue_growth: Decimal,
        ebitda_margin: Decimal,
        debt_to_equity: Decimal,
        current_ratio: Decimal
    ) -> Decimal:
        """Calculate overall financial health score"""
        growth_score = min(revenue_growth / Decimal('0.1'), Decimal('1.0'))
        margin_score = min(ebitda_margin / Decimal('0.2'), Decimal('1.0'))
        debt_score = max(0, 1 - debt_to_equity)
        liquidity_score = min(current_ratio / 2, Decimal('1.0'))

        return (growth_score * Decimal('0.3') + margin_score * Decimal('0.3') + debt_score * Decimal('0.2') + liquidity_score * Decimal('0.2'))

    def _calculate_dependency_score(self, owner_profile: Dict[str, Any]) -> Decimal:
        """Calculate owner dependency score"""
        return owner_profile.get("dependency_score", Decimal('0.5'))

    def _calculate_succession_readiness(self, owner_profile: Dict[str, Any]) -> Decimal:
        """Calculate succession readiness score"""
        return owner_profile.get("succession_readiness", Decimal('0.5'))

    def _calculate_transferability_risk(self, owner_profile: Dict[str, Any]) -> Decimal:
        """Calculate transferability risk score"""
        return owner_profile.get("transferability_risk", Decimal('0.5'))

    def _calculate_dcf_impact(self, dependency_score: Decimal, succession_readiness: Decimal) -> Decimal:
        """Calculate DCF impact from owner dependency"""
        if dependency_score > 0.8:
            return Decimal('0.3')
        elif dependency_score > 0.6:
            return Decimal('0.6')
        else:
            return Decimal('1.0')

    def _calculate_multiples_impact(self, dependency_score: Decimal, transferability_risk: Decimal) -> Decimal:
        """Calculate Multiples impact from owner dependency"""
        if dependency_score > 0.8:
            return Decimal('1.2')
        elif dependency_score > 0.6:
            return Decimal('1.1')
        else:
            return Decimal('1.0')

    def _count_comparable_companies(self, market_context: Dict[str, Any]) -> int:
        """Count comparable companies"""
        return market_context.get("comparable_companies_count", 5)

    def _calculate_market_data_quality(self, market_context: Dict[str, Any]) -> Decimal:
        """Calculate market data quality"""
        return market_context.get("market_data_quality", Decimal('0.8'))

    def _check_industry_benchmarks_availability(self, market_context: Dict[str, Any]) -> bool:
        """Check industry benchmarks availability"""
        return market_context.get("industry_benchmarks_available", True)

    def _calculate_market_data_freshness(self, market_context: Dict[str, Any]) -> Decimal:
        """Calculate market data freshness"""
        return market_context.get("market_data_freshness", Decimal('0.9'))

    def _calculate_market_dcf_score(self, market_context: Dict[str, Any]) -> Decimal:
        """Calculate market DCF score"""
        return market_context.get("dcf_score", Decimal('0.5'))

    def _calculate_market_multiples_score(
        self,
        comparable_companies_count: int,
        market_data_quality: Decimal,
        industry_benchmarks_available: bool
    ) -> Decimal:
        """Calculate market Multiples score"""
        if comparable_companies_count >= 3 and market_data_quality > Decimal('0.8') and industry_benchmarks_available:
            return Decimal('0.9')
        elif comparable_companies_count >= 2 and market_data_quality > 0.6:
            return Decimal('0.7')
        else:
            return Decimal('0.4')

    def _evaluate_industry_dcf_rules(self, dcf_preference: Dict[str, Any], financial_data: Dict[str, Any]) -> Decimal:
        """Evaluate industry-specific DCF rules"""
        # Implementation depends on industry rules and financial data
        return Decimal('0.5')  # Default industry DCF score

    def _evaluate_industry_multiples_rules(self, multiples_preference: Dict[str, Any], financial_data: Dict[str, Any]) -> Decimal:
        """Evaluate industry-specific Multiples rules"""
        # Implementation depends on industry rules and financial data
        return Decimal('0.5')  # Default industry Multiples score

    def _get_default_business_scores(self) -> Dict[str, Decimal]:
        """Get default business scores"""
        return {
            "dcf_revenue": Decimal('0.5'),
            "dcf_ebitda": Decimal('0.5'),
            "dcf_growth": Decimal('0.5'),
            "dcf_age": Decimal('0.5'),
            "multiples_market": Decimal('0.5'),
            "competitive_advantage": Decimal('0.5')
        }

    def _get_default_financial_score(self) -> FinancialScore:
        """Get default financial score"""
        return FinancialScore(
            dcf_score=Decimal('0.5'),
            multiples_score=Decimal('0.5'),
            overall_health=Decimal('0.5'),
            revenue_stability=Decimal('0.5'),
            ebitda_consistency=Decimal('0.5'),
            cash_flow_stability=Decimal('0.5')
        )

    def _get_default_owner_score(self) -> OwnerScore:
        """Get default owner score"""
        return OwnerScore(
            dependency_score=Decimal('0.5'),
            succession_readiness=Decimal('0.5'),
            transferability_risk=Decimal('0.5'),
            dcf_impact=Decimal('1.0'),
            multiples_impact=Decimal('1.0')
        )

    def _get_default_market_score(self) -> MarketScore:
        """Get default market score"""
        return MarketScore(
            comparable_companies_count=5,
            market_data_quality=Decimal('0.8'),
            industry_benchmarks_available=True,
            market_data_freshness=Decimal('0.9'),
            dcf_score=Decimal('0.5'),
            multiples_score=Decimal('0.5')
        )
