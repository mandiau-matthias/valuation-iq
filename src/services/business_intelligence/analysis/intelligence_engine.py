
"""
Intelligence Engine for Business Type Intelligence Service

This module provides the main intelligence processing capabilities including
machine learning integration, learning system management, and intelligent
decision making.
"""

from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
from src.utils.logging import get_logger
from decimal import Decimal
from src.utils.decimal_helpers import to_decimal, from_decimal
from .intelligence_types import (
    BusinessTypeAnalysis,
    MethodologyWeights,
    LearnedAdjustments,
    LearningMetrics,
    AnalysisRequest,
    AnalysisResponse,
    LearningType,
    AnalysisStatus,
    ConfidenceLevel
)
from .business_analyzer import BusinessAnalyzer
from .type_classifier import BusinessTypeClassifier

logger = get_logger(__name__)


class IntelligenceEngine:
    """
    Main intelligence processing engine.

    Coordinates business analysis, type classification, and machine learning
    to provide comprehensive business intelligence insights.
    """

    def __init__(self):
        """Initialize the intelligence engine"""
        self.logger = logger

        # Initialize component engines
        self.business_analyzer = BusinessAnalyzer()
        self.type_classifier = BusinessTypeClassifier()

        # Learning system state
        self.learning_models = {}
        self.learning_metrics = {}
        self.model_versions = {}

        # Analysis cache
        self.analysis_cache = {}
        self.cache_ttl = timedelta(hours=1)

    async def analyze_business_intelligence(
        self, 
        request: AnalysisRequest
    ) -> AnalysisResponse:
        """
        Perform comprehensive business intelligence analysis

        Args:
            request: Analysis request with business data

        Returns:
            AnalysisResponse with comprehensive analysis results
        """
        try:
            start_time = datetime.now()

            # Check cache first
            cache_key = self._create_cache_key(request)
            if cache_key in self.analysis_cache:
                cached_analysis = self.analysis_cache[cache_key]
                if datetime.now() - cached_analysis['timestamp'] < self.cache_ttl:
                    self.logger.info(f"Returning cached analysis for {request.business_type}")
                    return cached_analysis['response']

            # Classify business type if not provided
            if not request.business_type:
                business_type, category, confidence = self.type_classifier.classify_business_type(
                    request.business_type or 'unknown',
                    request.industry,
                    request.business_model
                )
                request.business_type = business_type

            # Perform business analysis
            business_analysis = self.business_analyzer.analyze_business_type(request)

            # Get business insights
            business_insights = self.type_classifier.get_business_insights(
                request.business_type, 
                business_analysis.category
            )

            # Calculate methodology weights
            methodology_weights = self._calculate_methodology_weights(business_analysis)

            # Get learned adjustments
            learned_adjustments = await self._get_learned_adjustments(request.business_type)

            # Get market context analysis
            market_context = self._analyze_market_context(request)

            # Get owner dependency analysis
            owner_dependency = self._analyze_owner_dependency(request)

            # Get learning metrics
            learning_metrics = self._get_learning_metrics(request.business_type)

            # Calculate processing time
            processing_time = (datetime.now() - start_time).total_seconds()

            # Create comprehensive response
            response = AnalysisResponse(
                analysis=business_analysis,
                methodology_weights=methodology_weights,
                learned_adjustments=learned_adjustments,
                market_context=market_context,
                owner_dependency=owner_dependency,
                insights=business_insights,
                learning_metrics=learning_metrics,
                processing_time=processing_time,
                analysis_date=datetime.now().isoformat()
            )

            # Cache the response
            self.analysis_cache[cache_key] = {
                'response': response,
                'timestamp': datetime.now()
            }

            self.logger.info(f"Completed business intelligence analysis for {request.business_type}")
            return response

        except Exception as e:
            self.logger.error(f"Error in business intelligence analysis: {e}")
            return self._get_default_response(request)

    async def learn_from_valuation(
        self,
        business_type: str,
        methodology_used: str,
        success_rate: Decimal,
        user_satisfaction: Decimal,
        completion_time: Decimal
    ) -> bool:
        """
        Learn from valuation results to improve future analysis

        Args:
            business_type: Business type that was valued
            methodology_used: Methodology that was used
            success_rate: Success rate of the valuation
            user_satisfaction: User satisfaction score
            completion_time: Time taken to complete valuation

        Returns:
            True if learning was successful, False otherwise
        """
        try:
            # Update learning models
            await self._update_learning_models(
                business_type, methodology_used, success_rate, user_satisfaction, completion_time
            )

            # Update learning metrics
            self._update_learning_metrics(business_type, success_rate, user_satisfaction)

            # Clear cache for this business type
            self._clear_cache_for_business_type(business_type)

            self.logger.info(f"Updated learning for business type: {business_type}")
            return True

        except Exception as e:
            self.logger.error(f"Error learning from valuation: {e}")
            return False

    async def get_learning_insights(self, business_type: str) -> Dict[str, Any]:
        """
        Get learning insights for a business type

        Args:
            business_type: Business type to get insights for

        Returns:
            Dictionary with learning insights
        """
        try:
            # Get learning metrics
            metrics = self.learning_metrics.get(business_type, {})

            # Get model performance
            model_performance = self._get_model_performance(business_type)

            # Get learning recommendations
            recommendations = self._get_learning_recommendations(business_type, metrics)

            return {
                'business_type': business_type,
                'learning_metrics': metrics,
                'model_performance': model_performance,
                'recommendations': recommendations,
                'last_updated': datetime.now().isoformat()
            }

        except Exception as e:
            self.logger.error(f"Error getting learning insights: {e}")
            return {}

    def _calculate_methodology_weights(self, business_analysis: BusinessTypeAnalysis) -> MethodologyWeights:
        """Calculate methodology weights based on business analysis"""
        try:
            # Extract weights from analysis
            dcf_weight = business_analysis.avg_dcf_weight
            multiples_weight = business_analysis.avg_multiples_weight
            confidence_score = business_analysis.confidence_score

            # Generate reasoning
            reasoning = f"Methodology weights based on historical analysis: DCF {dcf_weight:.1%}, Multiples {multiples_weight:.1%}"

            # Generate business type factors
            business_type_factors = business_analysis.key_factors

            # Generate historical analysis
            historical_analysis = {
                'dcf_success_rate': business_analysis.dcf_success_rate,
                'multiples_success_rate': business_analysis.multiples_success_rate,
                'avg_revenue': business_analysis.avg_revenue,
                'avg_ebitda_margin': business_analysis.avg_ebitda_margin,
                'comparable_companies_count': business_analysis.comparable_companies_count
            }

            # Generate market context analysis
            market_context_analysis = {
                'market_data_quality': business_analysis.market_data_quality,
                'industry_benchmarks_available': business_analysis.industry_benchmarks_available,
                'growth_potential': business_analysis.growth_potential
            }

            return MethodologyWeights(
                dcf_weight=dcf_weight,
                multiples_weight=multiples_weight,
                confidence_score=confidence_score,
                reasoning=reasoning,
                business_type_factors=business_type_factors,
                historical_analysis=historical_analysis,
                market_context_analysis=market_context_analysis
            )

        except Exception as e:
            self.logger.error(f"Error calculating methodology weights: {e}")
            return MethodologyWeights(
                dcf_weight=Decimal('0.5'),
                multiples_weight=Decimal('0.5'),
                confidence_score=Decimal('0.5'),
                reasoning="Default methodology weights",
                business_type_factors=[],
                historical_analysis={},
                market_context_analysis={}
            )

    async def _get_learned_adjustments(self, business_type: str) -> LearnedAdjustments:
        """Get learned adjustments for business type"""
        try:
            # Get learning model for business type
            model = self.learning_models.get(business_type)

            if model:
                # Calculate adjustments based on model
                dcf_adjustment = model.get('dcf_adjustment', Decimal('0.0'))
                multiples_adjustment = model.get('multiples_adjustment', Decimal('0.0'))
                confidence_boost = model.get('confidence_boost', Decimal('0.0'))
                prediction_accuracy = model.get('prediction_accuracy', Decimal('0.5'))
            else:
                # Default adjustments
                dcf_adjustment = Decimal('0.0')
                multiples_adjustment = Decimal('0.0')
                confidence_boost = Decimal('0.0')
                prediction_accuracy = Decimal('0.5')

            return LearnedAdjustments(
                dcf_adjustment=dcf_adjustment,
                multiples_adjustment=multiples_adjustment,
                confidence_boost=confidence_boost,
                prediction_accuracy=prediction_accuracy,
                learning_type=LearningType.METHODOLOGY_SELECTION,
                adjustment_factors={'business_type': business_type},
                model_version=self.model_versions.get(business_type, '1.0'),
                last_updated=datetime.now().isoformat()
            )

        except Exception as e:
            self.logger.error(f"Error getting learned adjustments: {e}")
            return LearnedAdjustments(
                dcf_adjustment=Decimal('0.0'),
                multiples_adjustment=Decimal('0.0'),
                confidence_boost=Decimal('0.0'),
                prediction_accuracy=Decimal('0.5'),
                learning_type=LearningType.METHODOLOGY_SELECTION,
                adjustment_factors={},
                model_version='1.0',
                last_updated=datetime.now().isoformat()
            )

    def _analyze_market_context(self, request: AnalysisRequest) -> Dict[str, Any]:
        """Analyze market context for business type"""
        try:
            # Simplified market context analysis
            return {
                'industry_growth_rate': Decimal('0.05'),
                'market_size': 1000000000,
                'competitive_intensity': Decimal('0.5'),
                'regulatory_environment': 'moderate',
                'technology_adoption': Decimal('0.5'),
                'market_maturity': 'developing',
                'key_trends': [],
                'risk_factors': []
            }

        except Exception as e:
            self.logger.error(f"Error analyzing market context: {e}")
            return {}

    def _analyze_owner_dependency(self, request: AnalysisRequest) -> Dict[str, Any]:
        """Analyze owner dependency for business type"""
        try:
            # Simplified owner dependency analysis
            return {
                'dependency_score': Decimal('0.5'),
                'key_person_risk': Decimal('0.5'),
                'succession_planning': 'unknown',
                'transferability': Decimal('0.5'),
                'owner_skills_importance': [],
                'mitigation_strategies': [],
                'valuation_impact': Decimal('0.0')
            }

        except Exception as e:
            self.logger.error(f"Error analyzing owner dependency: {e}")
            return {}

    def _get_learning_metrics(self, business_type: str) -> LearningMetrics:
        """Get learning metrics for business type"""
        try:
            metrics = self.learning_metrics.get(business_type, {})

            return LearningMetrics(
                model_accuracy=metrics.get('accuracy', Decimal('0.5')),
                prediction_confidence=metrics.get('confidence', Decimal('0.5')),
                false_positive_rate=metrics.get('false_positive_rate', Decimal('0.1')),
                false_negative_rate=metrics.get('false_negative_rate', Decimal('0.1')),
                training_samples=metrics.get('training_samples', 0),
                validation_samples=metrics.get('validation_samples', 0),
                last_training_date=metrics.get('last_training_date', datetime.now().isoformat()),
                model_performance=metrics.get('performance', {})
            )

        except Exception as e:
            self.logger.error(f"Error getting learning metrics: {e}")
            return LearningMetrics(
                model_accuracy=Decimal('0.5'),
                prediction_confidence=Decimal('0.5'),
                false_positive_rate=Decimal('0.1'),
                false_negative_rate=Decimal('0.1'),
                training_samples=0,
                validation_samples=0,
                last_training_date=datetime.now().isoformat(),
                model_performance={}
            )

    async def _update_learning_models(
        self,
        business_type: str,
        methodology_used: str,
        success_rate: Decimal,
        user_satisfaction: Decimal,
        completion_time: Decimal
    ):
        """Update learning models based on valuation results"""
        try:
            # Initialize model if not exists
            if business_type not in self.learning_models:
                self.learning_models[business_type] = {
                    'dcf_adjustment': Decimal('0.0'),
                    'multiples_adjustment': Decimal('0.0'),
                    'confidence_boost': Decimal('0.0'),
                    'prediction_accuracy': Decimal('0.5'),
                    'total_valuations': 0,
                    'successful_valuations': 0
                }

            model = self.learning_models[business_type]

            # Update model based on results
            if methodology_used == 'dcf':
                model['dcf_adjustment'] += (success_rate - Decimal('0.5')) * Decimal('0.1')
            elif methodology_used == 'multiples':
                model['multiples_adjustment'] += (success_rate - Decimal('0.5')) * Decimal('0.1')

            # Update confidence boost
            model['confidence_boost'] += (user_satisfaction - Decimal('0.5')) * Decimal('0.05')

            # Update prediction accuracy
            model['prediction_accuracy'] = (model['prediction_accuracy'] + success_rate) / 2

            # Update counters
            model['total_valuations'] += 1
            if success_rate > 0.7:
                model['successful_valuations'] += 1

            # Update model version
            self.model_versions[business_type] = f"1.{model['total_valuations']}"

        except Exception as e:
            self.logger.error(f"Error updating learning models: {e}")

    def _update_learning_metrics(self, business_type: str, success_rate: Decimal, user_satisfaction: Decimal):
        """Update learning metrics for business type"""
        try:
            if business_type not in self.learning_metrics:
                self.learning_metrics[business_type] = {
                    'accuracy': Decimal('0.5'),
                    'confidence': Decimal('0.5'),
                    'false_positive_rate': Decimal('0.1'),
                    'false_negative_rate': Decimal('0.1'),
                    'training_samples': 0,
                    'validation_samples': 0,
                    'last_training_date': datetime.now().isoformat(),
                    'performance': {}
                }

            metrics = self.learning_metrics[business_type]

            # Update accuracy
            metrics['accuracy'] = (metrics['accuracy'] + success_rate) / 2

            # Update confidence
            metrics['confidence'] = (metrics['confidence'] + user_satisfaction) / 2

            # Update training samples
            metrics['training_samples'] += 1

            # Update last training date
            metrics['last_training_date'] = datetime.now().isoformat()

        except Exception as e:
            self.logger.error(f"Error updating learning metrics: {e}")

    def _get_model_performance(self, business_type: str) -> Dict[str, Decimal]:
        """Get model performance metrics"""
        try:
            model = self.learning_models.get(business_type, {})
            metrics = self.learning_metrics.get(business_type, {})

            return {
                'accuracy': metrics.get('accuracy', Decimal('0.5')),
                'confidence': metrics.get('confidence', Decimal('0.5')),
                'dcf_adjustment': model.get('dcf_adjustment', Decimal('0.0')),
                'multiples_adjustment': model.get('multiples_adjustment', Decimal('0.0')),
                'prediction_accuracy': model.get('prediction_accuracy', Decimal('0.5'))
            }

        except Exception as e:
            self.logger.error(f"Error getting model performance: {e}")
            return {}

    def _get_learning_recommendations(self, business_type: str, metrics: Dict[str, Any]) -> List[str]:
        """Get learning recommendations for business type"""
        try:
            recommendations = []

            accuracy = metrics.get('accuracy', Decimal('0.5'))
            confidence = metrics.get('confidence', Decimal('0.5'))
            training_samples = metrics.get('training_samples', 0)

            if accuracy < 0.7:
                recommendations.append("Increase training data for better accuracy")

            if confidence < 0.7:
                recommendations.append("Improve model confidence through more data")

            if training_samples < 10:
                recommendations.append("Collect more training samples")

            if not recommendations:
                recommendations.append("Model performance is satisfactory")

            return recommendations

        except Exception as e:
            self.logger.error(f"Error getting learning recommendations: {e}")
            return ["Monitor model performance"]

    def _clear_cache_for_business_type(self, business_type: str):
        """Clear cache for specific business type"""
        try:
            keys_to_remove = [key for key in self.analysis_cache.keys() if business_type in key]
            for key in keys_to_remove:
                del self.analysis_cache[key]

            self.logger.info(f"Cleared cache for business type: {business_type}")

        except Exception as e:
            self.logger.error(f"Error clearing cache: {e}")

    def _create_cache_key(self, request: AnalysisRequest) -> str:
        """Create cache key for analysis request"""
        try:
            key_parts = [
                request.business_type or 'unknown',
                str(request.revenue or 0),
                request.industry or 'unknown',
                request.business_model or 'unknown'
            ]
            return '_'.join(key_parts)

        except Exception as e:
            self.logger.error(f"Error creating cache key: {e}")
            return 'default'

    def _get_default_response(self, request: AnalysisRequest) -> AnalysisResponse:
        """Get default response when analysis fails"""
        try:
            # Create default analysis
            from .intelligence_types import BusinessTypeAnalysis, MethodologyWeights, LearnedAdjustments, LearningMetrics

            default_analysis = BusinessTypeAnalysis(
                business_type=request.business_type or 'unknown',
                category='unknown',
                industry='unknown',
                dcf_success_rate=Decimal('0.5'),
                multiples_success_rate=Decimal('0.5'),
                avg_dcf_weight=Decimal('0.5'),
                avg_multiples_weight=Decimal('0.5'),
                avg_revenue=Decimal('0.0'),
                avg_ebitda_margin=Decimal('0.0'),
                avg_growth_rate=Decimal('0.05'),
                avg_owner_dependency=Decimal('0.5'),
                comparable_companies_count=0,
                industry_benchmarks_available=False,
                market_data_quality=Decimal('0.5'),
                valuation_accuracy=Decimal('0.5'),
                user_satisfaction=Decimal('0.5'),
                completion_rate=Decimal('0.5'),
                confidence_score=Decimal('0.5')
            )

            return AnalysisResponse(
                analysis=default_analysis,
                methodology_weights=MethodologyWeights(
                    dcf_weight=Decimal('0.5'),
                    multiples_weight=Decimal('0.5'),
                    confidence_score=Decimal('0.5'),
                    reasoning="Default analysis",
                    business_type_factors=[],
                    historical_analysis={},
                    market_context_analysis={}
                ),
                learned_adjustments=LearnedAdjustments(
                    dcf_adjustment=Decimal('0.0'),
                    multiples_adjustment=Decimal('0.0'),
                    confidence_boost=Decimal('0.0'),
                    prediction_accuracy=Decimal('0.5'),
                    learning_type=LearningType.METHODOLOGY_SELECTION,
                    adjustment_factors={},
                    model_version='1.0',
                    last_updated=datetime.now().isoformat()
                ),
                market_context={},
                owner_dependency={},
                insights=None,
                learning_metrics=LearningMetrics(
                    model_accuracy=Decimal('0.5'),
                    prediction_confidence=Decimal('0.5'),
                    false_positive_rate=Decimal('0.1'),
                    false_negative_rate=Decimal('0.1'),
                    training_samples=0,
                    validation_samples=0,
                    last_training_date=datetime.now().isoformat(),
                    model_performance={}
                ),
                processing_time=Decimal('0.0'),
                analysis_date=datetime.now().isoformat()
            )

        except Exception as e:
            self.logger.error(f"Error creating default response: {e}")
            raise
