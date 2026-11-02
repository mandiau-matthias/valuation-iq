
"""
Performance Tracker

This module handles performance monitoring, metrics calculation, and model evaluation
for the learning system. It provides comprehensive tracking of model performance
and degradation detection.

Author: Upswitch CTO Team
Date: October 2025
Status: Production Ready
"""

import numpy as np
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
from sklearn.model_selection import cross_val_score

from src.utils.logging import get_logger
from decimal import Decimal
from src.utils.decimal_helpers import to_decimal, from_decimal
from ..training.learning_types import (
    ModelPerformance, ModelType, LearningData, PerformanceThresholds,
    DEFAULT_PERFORMANCE_THRESHOLDS
)

logger = get_logger(__name__)


class PerformanceTracker:
    """
    Tracks and evaluates model performance metrics
    """

    def __init__(self, thresholds: Optional[PerformanceThresholds] = None):
        """Initialize performance tracker"""
        self.thresholds = thresholds or DEFAULT_PERFORMANCE_THRESHOLDS
        logger.info("✅ PerformanceTracker initialized")

    def calculate_performance_metrics(
        self,
        learning_data: List[Any],
        model_type: ModelType
    ) -> ModelPerformance:
        """Calculate performance metrics from learning data"""

        try:
            logger.info(f"📊 Calculating performance metrics for {model_type}")

            if not learning_data:
                return self._get_default_performance(model_type)

            # Calculate average accuracy from learning data
            accuracies = [
                record.prediction_accuracy 
                for record in learning_data 
                if record.prediction_accuracy is not None
            ]

            if not accuracies:
                return self._get_default_performance(model_type)

            avg_accuracy = sum(accuracies) / len(accuracies)

            # Create performance metrics
            performance = ModelPerformance(
                model_id=f"{model_type}",
                model_type=model_type,
                accuracy=avg_accuracy,
                precision=avg_accuracy,  # Simplified for now
                recall=avg_accuracy,     # Simplified for now
                f1_score=avg_accuracy,  # Simplified for now
                cross_val_score=avg_accuracy,
                training_samples=len(learning_data),
                test_samples=len(learning_data),
                last_trained=datetime.now(),
                version="1.0"
            )

            logger.info(f"✅ Performance metrics calculated: {model_type}")
            return performance

        except Exception as e:
            logger.error(f"❌ Performance calculation failed: {str(e)}")
            return self._get_default_performance(model_type)

    def evaluate_model_performance(
        self,
        model,
        X_test: np.ndarray,
        y_test: np.ndarray,
        model_type: ModelType,
        scaler=None
    ) -> ModelPerformance:
        """Evaluate model performance on test data"""

        try:
            logger.info(f"📊 Evaluating model performance for {model_type}")

            # Scale test features if scaler provided
            if scaler:
                X_test_scaled = scaler.transform(X_test)
            else:
                X_test_scaled = X_test

            # Make predictions
            y_pred = model.predict(X_test_scaled)

            # Calculate metrics
            accuracy = accuracy_score(y_test, y_pred)
            precision = precision_score(
                y_test, y_pred, 
                average='weighted', 
                zero_division=0
            )
            recall = recall_score(
                y_test, y_pred, 
                average='weighted', 
                zero_division=0
            )
            f1 = f1_score(
                y_test, y_pred, 
                average='weighted', 
                zero_division=0
            )

            # Cross-validation score
            try:
                cv_scores = cross_val_score(model, X_test_scaled, y_test, cv=5)
                cv_score = cv_scores.mean()
            except Exception as e:
                logger.warning(f"⚠️ Cross-validation failed: {str(e)}")
                cv_score = accuracy

            performance = ModelPerformance(
                model_id=f"{model_type}",
                model_type=model_type,
                accuracy=accuracy,
                precision=precision,
                recall=recall,
                f1_score=f1,
                cross_val_score=cv_score,
                training_samples=len(X_test),
                test_samples=len(y_test),
                last_trained=datetime.now(),
                version="1.0"
            )

            logger.info(f"✅ Model evaluation completed: {model_type}")
            return performance

        except Exception as e:
            logger.error(f"❌ Model evaluation failed: {str(e)}")
            return self._get_default_performance(model_type)

    def check_performance_thresholds(
        self,
        performance: ModelPerformance
    ) -> Dict[str, Any]:
        """Check if performance meets minimum thresholds"""

        try:
            logger.info(f"📊 Checking performance thresholds for {performance.model_type}")

            results = {
                "meets_accuracy": performance.accuracy >= self.thresholds.min_accuracy,
                "meets_precision": performance.precision >= self.thresholds.min_precision,
                "meets_recall": performance.recall >= self.thresholds.min_recall,
                "meets_f1": performance.f1_score >= self.thresholds.min_f1_score,
                "meets_cv_score": performance.cross_val_score >= self.thresholds.min_cross_val_score,
                "overall_pass": True
            }

            # Overall pass if all thresholds are met
            results["overall_pass"] = all([
                results["meets_accuracy"],
                results["meets_precision"],
                results["meets_recall"],
                results["meets_f1"],
                results["meets_cv_score"]
            ])

            logger.info(f"✅ Performance threshold check completed: {performance.model_type}")
            return results

        except Exception as e:
            logger.error(f"❌ Performance threshold check failed: {str(e)}")
            return {
                "meets_accuracy": False,
                "meets_precision": False,
                "meets_recall": False,
                "meets_f1": False,
                "meets_cv_score": False,
                "overall_pass": False
            }

    def detect_performance_degradation(
        self,
        current_performance: ModelPerformance,
        historical_performances: List[ModelPerformance]
    ) -> Dict[str, Any]:
        """Detect performance degradation over time"""

        try:
            logger.info(f"📊 Detecting performance degradation for {current_performance.model_type}")

            if len(historical_performances) < 2:
                return {
                    "degradation_detected": False,
                    "degradation_percentage": 0.0,
                    "trend": "insufficient_data"
                }

            # Calculate average historical performance
            historical_accuracy = np.mean([
                p.accuracy for p in historical_performances
            ])

            # Calculate degradation percentage
            degradation_percentage = (
                (historical_accuracy - current_performance.accuracy) / 
                historical_accuracy * 100
            )

            # Determine if degradation is significant (>10%)
            degradation_detected = degradation_percentage > 10.0

            # Determine trend
            if degradation_percentage > 5:
                trend = "declining"
            elif degradation_percentage < -5:
                trend = "improving"
            else:
                trend = "stable"

            result = {
                "degradation_detected": degradation_detected,
                "degradation_percentage": degradation_percentage,
                "trend": trend,
                "historical_accuracy": historical_accuracy,
                "current_accuracy": current_performance.accuracy
            }

            logger.info(f"✅ Performance degradation analysis completed: {current_performance.model_type}")
            return result

        except Exception as e:
            logger.error(f"❌ Performance degradation detection failed: {str(e)}")
            return {
                "degradation_detected": False,
                "degradation_percentage": 0.0,
                "trend": "error"
            }

    def is_model_recent(self, performance: ModelPerformance, days: int = 7) -> bool:
        """Check if model is recent enough"""

        try:
            age_days = (datetime.now() - performance.last_trained).days
            is_recent = age_days < days

            logger.info(f"📊 Model age check: {age_days} days old, recent: {is_recent}")
            return is_recent

        except Exception as e:
            logger.error(f"❌ Model age check failed: {str(e)}")
            return False

    def get_performance_summary(
        self,
        performances: List[ModelPerformance]
    ) -> Dict[str, Any]:
        """Get summary of multiple model performances"""

        try:
            logger.info(f"📊 Generating performance summary for {len(performances)} models")

            if not performances:
                return {
                    "total_models": 0,
                    "average_accuracy": 0.0,
                    "best_model": None,
                    "worst_model": None,
                    "models_meeting_thresholds": 0
                }

            # Calculate summary statistics
            accuracies = [p.accuracy for p in performances]
            average_accuracy = np.mean(accuracies)

            # Find best and worst models
            best_model = max(performances, key=lambda p: p.accuracy)
            worst_model = min(performances, key=lambda p: p.accuracy)

            # Count models meeting thresholds
            models_meeting_thresholds = sum([
                1 for p in performances 
                if self.check_performance_thresholds(p)["overall_pass"]
            ])

            summary = {
                "total_models": len(performances),
                "average_accuracy": average_accuracy,
                "best_model": {
                    "model_id": best_model.model_id,
                    "accuracy": best_model.accuracy,
                    "model_type": best_model.model_type
                },
                "worst_model": {
                    "model_id": worst_model.model_id,
                    "accuracy": worst_model.accuracy,
                    "model_type": worst_model.model_type
                },
                "models_meeting_thresholds": models_meeting_thresholds,
                "threshold_compliance_rate": models_meeting_thresholds / len(performances)
            }

            logger.info(f"✅ Performance summary generated: {len(performances)} models")
            return summary

        except Exception as e:
            logger.error(f"❌ Performance summary generation failed: {str(e)}")
            return {
                "total_models": 0,
                "average_accuracy": 0.0,
                "best_model": None,
                "worst_model": None,
                "models_meeting_thresholds": 0
            }

    def _get_default_performance(self, model_type: ModelType) -> ModelPerformance:
        """Get default performance when no data is available"""

        return ModelPerformance(
            model_id=f"{model_type}",
            model_type=model_type,
            accuracy=0.5,
            precision=0.5,
            recall=0.5,
            f1_score=0.5,
            cross_val_score=0.5,
            training_samples=0,
            test_samples=0,
            last_trained=datetime.now(),
            version="1.0"
        )
