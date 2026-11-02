from src.utils.exceptions import DCFCalculationError

"""
Intelligence Processor

Handles the processing of business intelligence data, methodology weight
calculations, and learning model applications.

Author: Upswitch Engineering Team
Date: October 2025
Status: Production Ready
"""

from typing import Dict, Any, List, Optional, Tuple
from decimal import Decimal
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from src.utils.logging import get_logger
from src.utils.decimal_helpers import to_decimal, from_decimal
from .intelligence_types import (
    MethodologyWeights, LearnedAdjustments, BusinessAdjustments,
    MarketAdjustments, OwnerAdjustments, HistoricalAnalysis,
    LearningModel, ML_MODEL_CONFIG
)

logger = get_logger(__name__)


class IntelligenceProcessor:
    """Processes business intelligence data and applies learning models"""

    def __init__(self):
        self.learning_models = {}
        self.scaler = StandardScaler()
        self.model_config = ML_MODEL_CONFIG

    def calculate_methodology_weights(
        self,
        business_adjustments: BusinessAdjustments,
        market_adjustments: MarketAdjustments,
        owner_adjustments: Optional[OwnerAdjustments],
        historical_analysis: HistoricalAnalysis
    ) -> MethodologyWeights:
        """Calculate methodology weights based on multiple factors"""

        try:
            logger.info("Calculating methodology weights")

            # Start with base weights from historical analysis
            dcf_success_rate_decimal = to_decimal(historical_analysis.dcf_success_rate) if hasattr(historical_analysis, 'dcf_success_rate') else Decimal('0.5')
            multiples_success_rate_decimal = to_decimal(historical_analysis.multiples_success_rate) if hasattr(historical_analysis, 'multiples_success_rate') else Decimal('0.5')
            dcf_weight_decimal = dcf_success_rate_decimal
            multiples_weight_decimal = multiples_success_rate_decimal

            # Apply business adjustments
            dcf_factor_decimal = to_decimal(business_adjustments.dcf_factor) if hasattr(business_adjustments, 'dcf_factor') else Decimal('1.0')
            multiples_factor_decimal = to_decimal(business_adjustments.multiples_factor) if hasattr(business_adjustments, 'multiples_factor') else Decimal('1.0')
            dcf_weight_decimal *= dcf_factor_decimal
            multiples_weight_decimal *= multiples_factor_decimal

            # Apply market adjustments
            market_dcf_factor_decimal = to_decimal(market_adjustments.dcf_factor) if hasattr(market_adjustments, 'dcf_factor') else Decimal('1.0')
            market_multiples_factor_decimal = to_decimal(market_adjustments.multiples_factor) if hasattr(market_adjustments, 'multiples_factor') else Decimal('1.0')
            dcf_weight_decimal *= market_dcf_factor_decimal
            multiples_weight_decimal *= market_multiples_factor_decimal

            # Apply owner adjustments if available
            if owner_adjustments:
                owner_dcf_factor_decimal = to_decimal(owner_adjustments.dcf_factor) if hasattr(owner_adjustments, 'dcf_factor') else Decimal('1.0')
                owner_multiples_factor_decimal = to_decimal(owner_adjustments.multiples_factor) if hasattr(owner_adjustments, 'multiples_factor') else Decimal('1.0')
                dcf_weight_decimal *= owner_dcf_factor_decimal
                multiples_weight_decimal *= owner_multiples_factor_decimal

            # Normalize weights
            total_weight_decimal = dcf_weight_decimal + multiples_weight_decimal
            if total_weight_decimal > Decimal('0'):
                dcf_weight_decimal = dcf_weight_decimal / total_weight_decimal
                multiples_weight_decimal = multiples_weight_decimal / total_weight_decimal
            dcf_weight = from_decimal(dcf_weight_decimal)
            multiples_weight = from_decimal(multiples_weight_decimal)

            # Calculate confidence score
            confidence_score = self._calculate_confidence_score(
                dcf_weight, multiples_weight, historical_analysis
            )

            # Generate reasoning
            reasoning = self._generate_reasoning(
                dcf_weight, multiples_weight, business_adjustments, 
                market_adjustments, owner_adjustments, historical_analysis
            )

            # Get business type factors
            business_type_factors = self._get_business_type_factors(
                business_adjustments, market_adjustments, owner_adjustments
            )

            return MethodologyWeights(
                dcf_weight=dcf_weight,
                multiples_weight=multiples_weight,
                confidence_score=confidence_score,
                reasoning=reasoning,
                business_type_factors=business_type_factors,
                historical_analysis=self._format_historical_analysis(historical_analysis),
                market_context_analysis=self._format_market_analysis(market_adjustments)
            )

        except DCFCalculationError as e:
            logger.error(f"Methodology weights calculation failed: {e}")
            return self._get_default_methodology_weights()

    def apply_learning_models(
        self,
        business_type: str,
        user_data: Dict[str, Any],
        methodology_weights: MethodologyWeights
    ) -> LearnedAdjustments:
        """Apply machine learning models for methodology selection"""

        try:
            logger.info(f"Applying learning models for {business_type}")

            # Get learning model for business type
            model = self._get_learning_model(business_type)

            if not model:
                return self._get_default_learned_adjustments()

            # Prepare features
            features = self._prepare_features(user_data, business_type)

            # Make prediction
            prediction = model.predict(features.reshape(1, -1))[0]

            # Apply learned adjustments
            dcf_adjustment = prediction[0] if len(prediction) > 0 else Decimal('1.0')
            multiples_adjustment = prediction[1] if len(prediction) > 1 else Decimal('1.0')

            # Calculate confidence and accuracy
            confidence_score = self._calculate_model_confidence(model, features)
            prediction_accuracy = self._get_model_accuracy(model)

            return LearnedAdjustments(
                dcf_adjustment=dcf_adjustment,
                multiples_adjustment=multiples_adjustment,
                confidence_score=confidence_score,
                model_version=model.version if hasattr(model, 'version') else "1.0",
                learning_source="machine_learning",
                prediction_accuracy=prediction_accuracy
            )

        except DCFCalculationError as e:
            logger.warning(f"Learning model application failed: {e}")
            return self._get_default_learned_adjustments()

    def train_learning_model(
        self, 
        business_type: str, 
        training_data: List[Dict[str, Any]]
    ) -> Optional[LearningModel]:
        """Train learning model on historical data"""

        try:
            logger.info(f"Training learning model for {business_type}")

            if len(training_data) < self.model_config["min_training_samples"]:
                logger.warning(f"Insufficient training data for {business_type}")
                return None

            # Prepare training data
            X, y = self._prepare_training_data(training_data)

            if X is None or y is None:
                return None

            # Scale features if configured
            if self.model_config["feature_scaling"]:
                X = self.scaler.fit_transform(X)

            # Train model
            model = RandomForestClassifier(
                n_estimators=self.model_config["random_forest"]["n_estimators"],
                random_state=self.model_config["random_forest"]["random_state"],
                max_depth=self.model_config["random_forest"]["max_depth"]
            )

            model.fit(X, y)

            # Create learning model object
            learning_model = LearningModel(
                model_type="random_forest",
                version="1.0",
                accuracy=model.score(X, y),
                training_data_size=len(training_data),
                last_updated=datetime.now(),
                features=self._get_feature_names(),
                target_variables=["dcf_weight", "multiples_weight"]
            )

            # Store model
            self.learning_models[business_type] = {
                "model": model,
                "metadata": learning_model
            }

            logger.info(f"Learning model trained successfully for {business_type}")
            return learning_model

        except DCFCalculationError as e:
            logger.error(f"Learning model training failed: {e}")
            return None

    def _calculate_confidence_score(
        self,
        dcf_weight: Decimal,
        multiples_weight: Decimal,
        historical_analysis: HistoricalAnalysis
    ) -> Decimal:
        """Calculate confidence score for methodology selection"""

        # Convert inputs to Decimal
        dcf_weight_decimal = to_decimal(dcf_weight)
        multiples_weight_decimal = to_decimal(multiples_weight)
        dcf_success_decimal = to_decimal(historical_analysis.dcf_success_rate) if hasattr(historical_analysis, 'dcf_success_rate') else Decimal('0.5')
        multiples_success_decimal = to_decimal(historical_analysis.multiples_success_rate) if hasattr(historical_analysis, 'multiples_success_rate') else Decimal('0.5')

        # Weighted confidence
        confidence_decimal = (dcf_weight_decimal * dcf_success_decimal) + (multiples_weight_decimal * multiples_success_decimal)

        # Adjust for data quality
        market_quality_decimal = to_decimal(historical_analysis.market_data_quality) if hasattr(historical_analysis, 'market_data_quality') else Decimal('1.0')
        confidence_decimal *= market_quality_decimal

        # Adjust for sample size (approximated from comparable companies)
        comparable_count = historical_analysis.comparable_companies_count if hasattr(historical_analysis, 'comparable_companies_count') else 0
        if comparable_count > 100:
            confidence_decimal *= Decimal('1.1')
        elif comparable_count > 50:
            confidence_decimal *= Decimal('1.05')

        return from_decimal(min(confidence_decimal, Decimal('1.0')))

    def _generate_reasoning(
        self,
        dcf_weight: Decimal,
        multiples_weight: Decimal,
        business_adjustments: BusinessAdjustments,
        market_adjustments: MarketAdjustments,
        owner_adjustments: Optional[OwnerAdjustments],
        historical_analysis: HistoricalAnalysis
    ) -> str:
        """Generate reasoning for methodology selection"""

        reasoning_parts = []

        # DCF reasoning
        if dcf_weight > 0.6:
            reasoning_parts.append("DCF is preferred due to strong financial performance and growth potential")
        elif dcf_weight > 0.4:
            reasoning_parts.append("DCF is moderately weighted based on financial characteristics")

        # Multiples reasoning
        if multiples_weight > 0.6:
            reasoning_parts.append("Multiples are preferred due to strong comparable company data and market benchmarks")
        elif multiples_weight > 0.4:
            reasoning_parts.append("Multiples are moderately weighted based on market data availability")

        # Historical performance
        dcf_success = historical_analysis.dcf_success_rate
        multiples_success = historical_analysis.multiples_success_rate

        if dcf_success > 0.7:
            reasoning_parts.append("Historical DCF performance has been strong for this business type")
        if multiples_success > 0.7:
            reasoning_parts.append("Historical Multiples performance has been strong for this business type")

        # Business characteristics
        if business_adjustments.growth_factor > 1.2:
            reasoning_parts.append("High growth rate favors DCF methodology")
        if business_adjustments.revenue_factor > 1.5:
            reasoning_parts.append("Large revenue base provides good foundation for DCF analysis")

        # Market context
        if market_adjustments.benchmark_availability_factor > 1.2:
            reasoning_parts.append("Strong market benchmarks favor Multiples methodology")

        # Owner dependency
        if owner_adjustments and owner_adjustments.dependency_score > 0.7:
            reasoning_parts.append("High owner dependency reduces DCF reliability")

        return ". ".join(reasoning_parts) if reasoning_parts else "Balanced methodology selection based on available data"

    def _get_business_type_factors(
        self,
        business_adjustments: BusinessAdjustments,
        market_adjustments: MarketAdjustments,
        owner_adjustments: Optional[OwnerAdjustments]
    ) -> List[str]:
        """Get business type specific factors"""

        factors = []

        # Revenue factors
        if business_adjustments.revenue_factor > 1.5:
            factors.append("High revenue business")
        elif business_adjustments.revenue_factor > 1.0:
            factors.append("Medium revenue business")

        # Growth factors
        if business_adjustments.growth_factor > 1.5:
            factors.append("High growth potential")
        elif business_adjustments.growth_factor > 1.0:
            factors.append("Moderate growth potential")

        # Profitability factors
        if business_adjustments.profitability_factor > 0.2:
            factors.append("High profitability")
        elif business_adjustments.profitability_factor > 0.1:
            factors.append("Moderate profitability")

        # Market factors
        if market_adjustments.benchmark_availability_factor > 1.2:
            factors.append("Strong market benchmarks available")

        # Owner dependency factors
        if owner_adjustments:
            if owner_adjustments.dependency_score > 0.7:
                factors.append("High owner dependency")
            elif owner_adjustments.dependency_score > 0.4:
                factors.append("Moderate owner dependency")
            else:
                factors.append("Low owner dependency")

        return factors

    def _get_learning_model(self, business_type: str) -> Optional[Any]:
        """Get learning model for business type"""

        if business_type in self.learning_models:
            return self.learning_models[business_type]["model"]

        return None

    def _prepare_features(self, user_data: Dict[str, Any], business_type: str) -> np.ndarray:
        """Prepare features for machine learning model"""

        features = [
            user_data.get("revenue", 0),
            user_data.get("ebitda", 0),
            user_data.get("growth_rate", 0),
            user_data.get("owner_dependency", Decimal('0.5')),
            user_data.get("market_data_quality", Decimal('0.5')),
            user_data.get("years_in_operation", 0),
            user_data.get("employee_count", 0)
        ]

        return np.array(features)

    def _prepare_training_data(
        self, 
        training_data: List[Dict[str, Any]]
    ) -> Tuple[Optional[np.ndarray], Optional[np.ndarray]]:
        """Prepare training data for machine learning model"""

        try:
            X = []
            y = []

            for data in training_data:
                # Extract features
                features = [
                    data.get("revenue", 0),
                    data.get("ebitda", 0),
                    data.get("growth_rate", 0),
                    data.get("owner_dependency", Decimal('0.5')),
                    data.get("market_data_quality", Decimal('0.5')),
                    data.get("years_in_operation", 0),
                    data.get("employee_count", 0)
                ]
                X.append(features)

                # Extract targets
                targets = [
                    data.get("dcf_weight", Decimal('0.5')),
                    data.get("multiples_weight", Decimal('0.5'))
                ]
                y.append(targets)

            return np.array(X), np.array(y)

        except DCFCalculationError as e:
            logger.error(f"Training data preparation failed: {e}")
            return None, None

    def _get_feature_names(self) -> List[str]:
        """Get feature names for the model"""
        return [
            "revenue", "ebitda", "growth_rate", "owner_dependency",
            "market_data_quality", "years_in_operation", "employee_count"
        ]

    def _calculate_model_confidence(self, model: Any, features: np.ndarray) -> Decimal:
        """Calculate model confidence score"""

        try:
            if hasattr(model, 'predict_proba'):
                probabilities = model.predict_proba(features.reshape(1, -1))
                return to_decimal(probabilities.max())
            else:
                return Decimal('0.8')  # Default confidence
        except (ValueError, TypeError, AttributeError, IndexError):
            return Decimal('0.5')  # Fallback confidence

    def _get_model_accuracy(self, model: Any) -> Decimal:
        """Get model accuracy score"""

        try:
            if hasattr(model, 'score'):
                return to_decimal(model.score)
            else:
                return Decimal('0.8')  # Default accuracy
        except (ValueError, TypeError, AttributeError):
            return Decimal('0.5')  # Fallback accuracy

    def _format_historical_analysis(self, historical_analysis: HistoricalAnalysis) -> Dict[str, Any]:
        """Format historical analysis for output"""

        return {
            "dcf_success_rate": historical_analysis.dcf_success_rate,
            "multiples_success_rate": historical_analysis.multiples_success_rate,
            "avg_revenue": historical_analysis.avg_revenue,
            "avg_ebitda": historical_analysis.avg_ebitda,
            "avg_growth_rate": historical_analysis.avg_growth_rate,
            "market_data_quality": historical_analysis.market_data_quality,
            "comparable_companies_count": historical_analysis.comparable_companies_count,
            "valuation_accuracy": historical_analysis.valuation_accuracy
        }

    def _format_market_analysis(self, market_adjustments: MarketAdjustments) -> Dict[str, Any]:
        """Format market analysis for output"""

        return {
            "dcf_factor": market_adjustments.dcf_factor,
            "multiples_factor": market_adjustments.multiples_factor,
            "growth_expectations_factor": market_adjustments.growth_expectations_factor,
            "risk_factor": market_adjustments.risk_factor,
            "benchmark_availability_factor": market_adjustments.benchmark_availability_factor
        }

    def _get_default_methodology_weights(self) -> MethodologyWeights:
        """Get default methodology weights"""

        return MethodologyWeights(
            dcf_weight=Decimal('0.5'),
            multiples_weight=Decimal('0.5'),
            confidence_score=Decimal('0.5'),
            reasoning="Default methodology selection",
            business_type_factors=["Default analysis"],
            historical_analysis={},
            market_context_analysis={}
        )

    def _get_default_learned_adjustments(self) -> LearnedAdjustments:
        """Get default learned adjustments"""

        return LearnedAdjustments(
            dcf_adjustment=Decimal('1.0'),
            multiples_adjustment=Decimal('1.0'),
            confidence_score=Decimal('0.5'),
            model_version="default",
            learning_source="default",
            prediction_accuracy=Decimal('0.5')
        )

    def get_model_info(self, business_type: str) -> Optional[Dict[str, Any]]:
        """Get information about learning model for business type"""

        if business_type in self.learning_models:
            metadata = self.learning_models[business_type]["metadata"]
            return {
                "model_type": metadata.model_type,
                "version": metadata.version,
                "accuracy": metadata.accuracy,
                "training_data_size": metadata.training_data_size,
                "last_updated": metadata.last_updated,
                "features": metadata.features,
                "target_variables": metadata.target_variables
            }

        return None

    def list_available_models(self) -> List[str]:
        """List all available learning models"""
        return list(self.learning_models.keys())
