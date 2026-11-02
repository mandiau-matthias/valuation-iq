from src.utils.exceptions import ConfigurationError, DataValidationError

"""
Model Evaluator for ML Valuation Engine

This module provides comprehensive model evaluation capabilities including
performance metrics, cross-validation, hyperparameter tuning, and
model comparison for valuation methodology prediction.
"""

from typing import Dict, Any, List, Optional, Tuple, Union
import numpy as np
import pandas as pd
from datetime import datetime
import pickle
from decimal import Decimal
from src.utils.decimal_helpers import to_decimal, from_decimal
from sklearn.model_selection import (
    cross_val_score, StratifiedKFold, train_test_split,
    GridSearchCV, RandomizedSearchCV
)
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    mean_squared_error, mean_absolute_error, r2_score,
    classification_report, confusion_matrix, roc_auc_score
)
from sklearn.preprocessing import StandardScaler, LabelEncoder

from src.utils.logging import get_logger
from src.services.ml.ml_types import (
    ModelMetrics, ModelValidation, ModelComparison, ModelPerformance,
    TrainingData, ModelConfiguration, HyperparameterOptimization
)

logger = get_logger(__name__)


class ModelEvaluator:
    """
    Comprehensive model evaluator for ML valuation models.

    Provides evaluation capabilities including:
    - Performance metrics calculation
    - Cross-validation
    - Hyperparameter optimization
    - Model comparison
    - Validation strategies
    """

    def __init__(self):
        """Initialize the model evaluator"""
        self.logger = logger

        # Evaluation configuration
        self.evaluation_config = self._initialize_evaluation_config()

        # Performance tracking
        self.evaluation_history = []
        self.model_comparisons = []

        # Validation strategies
        self.validation_strategies = self._initialize_validation_strategies()

    async def evaluate_model_performance(
        self,
        model: Any,
        training_data: TrainingData,
        test_data: Optional[TrainingData] = None
    ) -> ModelMetrics:
        """
        Evaluate model performance comprehensively.

        Args:
            model: Trained model to evaluate
            training_data: Training data
            test_data: Test data (optional)

        Returns:
            Comprehensive performance metrics
        """
        try:
            self.logger.info("Starting model performance evaluation")

            # Prepare data
            if test_data is None:
                X_train, X_test, y_train, y_test = train_test_split(
                    training_data.features, training_data.labels,
                    test_size=Decimal('0.2'), random_state=42, stratify=training_data.labels
                )
            else:
                X_train, y_train = training_data.features, training_data.labels
                X_test, y_test = test_data.features, test_data.labels

            # Make predictions
            start_time = datetime.utcnow()
            y_pred = model.predict(X_test)
            prediction_time = (datetime.utcnow() - start_time).total_seconds()

            # Calculate classification metrics
            accuracy = accuracy_score(y_test, y_pred)
            precision = precision_score(y_test, y_pred, average='weighted')
            recall = recall_score(y_test, y_pred, average='weighted')
            f1 = f1_score(y_test, y_pred, average='weighted')

            # Calculate additional metrics if probabilities available
            try:
                y_pred_proba = model.predict_proba(X_test)
                auc_score = roc_auc_score(y_test, y_pred_proba, multi_class='ovr', average='weighted')
            except (ValueError, TypeError, AttributeError, IndexError):
                auc_score = Decimal('0.0')

            # Cross-validation
            cv_scores = cross_val_score(
                model, X_train, y_train, cv=5, scoring='accuracy'
            )

            # Calculate regression metrics (if applicable)
            try:
                mse = mean_squared_error(y_test, y_pred)
                mae = mean_absolute_error(y_test, y_pred)
                r2 = r2_score(y_test, y_pred)
            except (ValueError, TypeError, AttributeError):
                mse = mae = r2 = Decimal('0.0')

            # Model size estimation
            model_size = self._estimate_model_size(model)

            # Create metrics object
            metrics = ModelMetrics(
                accuracy=accuracy,
                precision=precision,
                recall=recall,
                f1_score=f1,
                mse=mse,
                mae=mae,
                r2_score=r2,
                cross_validation_score=np.mean(cv_scores),
                training_time=Decimal('0.0'),  # Would be measured during training
                prediction_time=prediction_time,
                model_size=model_size,
                memory_usage=Decimal('0.0'),  # Would be measured during training
                cpu_usage=Decimal('0.0')  # Would be measured during training
            )

            # Store evaluation history
            self.evaluation_history.append({
                'timestamp': datetime.utcnow(),
                'model_type': type(model).__name__,
                'metrics': metrics,
                'data_size': len(training_data.features)
            })

            self.logger.info(
                "Model performance evaluation completed",
                accuracy=accuracy,
                f1_score=f1,
                cv_score=np.mean(cv_scores)
            )

            return metrics

        except DataValidationError as e:
            self.logger.error(f"Error evaluating model performance: {e}")
            raise

    async def perform_cross_validation(
        self,
        model: Any,
        training_data: TrainingData,
        cv_folds: int = 5,
        scoring: str = 'accuracy'
    ) -> ModelValidation:
        """
        Perform cross-validation evaluation.

        Args:
            model: Model to evaluate
            training_data: Training data
            cv_folds: Number of cross-validation folds
            scoring: Scoring metric

        Returns:
            Cross-validation results
        """
        try:
            self.logger.info("Starting cross-validation evaluation", cv_folds=cv_folds)

            # Perform cross-validation
            cv_scores = cross_val_score(
                model, training_data.features, training_data.labels,
                cv=cv_folds, scoring=scoring
            )

            # Calculate statistics
            mean_score = np.mean(cv_scores)
            std_score = np.std(cv_scores)
            confidence_interval = (
                mean_score - Decimal('1.96') * std_score / np.sqrt(cv_folds),
                mean_score + Decimal('1.96') * std_score / np.sqrt(cv_folds)
            )

            # Detect overfitting/underfitting
            overfitting_detected = std_score > Decimal('0.1')  # High variance indicates overfitting
            underfitting_detected = mean_score < Decimal('0.6')  # Low score indicates underfitting

            validation_result = ModelValidation(
                validation_type="cross_validation",
                validation_scores=cv_scores.tolist(),
                mean_score=mean_score,
                std_score=std_score,
                confidence_interval=confidence_interval,
                validation_folds=cv_folds,
                validation_strategy="stratified_kfold",
                overfitting_detected=overfitting_detected,
                underfitting_detected=underfitting_detected
            )

            self.logger.info(
                "Cross-validation evaluation completed",
                mean_score=mean_score,
                std_score=std_score,
                overfitting=overfitting_detected,
                underfitting=underfitting_detected
            )

            return validation_result

        except DataValidationError as e:
            self.logger.error(f"Error performing cross-validation: {e}")
            raise

    async def optimize_hyperparameters(
        self,
        model_class: Any,
        training_data: TrainingData,
        param_grid: Dict[str, List[Any]],
        optimization_method: str = 'grid_search',
        cv_folds: int = 5,
        n_trials: int = 100
    ) -> HyperparameterOptimization:
        """
        Optimize hyperparameters for a model.

        Args:
            model_class: Model class to optimize
            training_data: Training data
            param_grid: Parameter grid for optimization
            optimization_method: Optimization method
            cv_folds: Number of CV folds
            n_trials: Number of trials for random search

        Returns:
            Hyperparameter optimization results
        """
        try:
            self.logger.info(
                "Starting hyperparameter optimization",
                method=optimization_method,
                param_count=len(param_grid)
            )

            if optimization_method == 'grid_search':
                # Grid search
                search = GridSearchCV(
                    model_class(),
                    param_grid,
                    cv=cv_folds,
                    scoring='accuracy',
                    n_jobs=-1
                )
                search.fit(training_data.features, training_data.labels)

                best_params = search.best_params_
                best_score = search.best_score_

            elif optimization_method == 'random_search':
                # Random search
                search = RandomizedSearchCV(
                    model_class(),
                    param_grid,
                    n_iter=n_trials,
                    cv=cv_folds,
                    scoring='accuracy',
                    n_jobs=-1,
                    random_state=42
                )
                search.fit(training_data.features, training_data.labels)

                best_params = search.best_params_
                best_score = search.best_score_

            else:
                raise ValueError(f"Unknown optimization method: {optimization_method}")

            # Create optimization result
            optimization_result = HyperparameterOptimization(
                optimization_method=optimization_method,
                parameter_space=param_grid,
                optimization_metric='accuracy',
                n_trials=n_trials if optimization_method == 'random_search' else len(param_grid),
                cv_folds=cv_folds,
                early_stopping=False,
                best_parameters=best_params,
                optimization_results={
                    'best_score': best_score,
                    'cv_results': search.cv_results_,
                    'best_estimator': search.best_estimator_
                }
            )

            self.logger.info(
                "Hyperparameter optimization completed",
                best_score=best_score,
                best_params=best_params
            )

            return optimization_result

        except ConfigurationError as e:
            self.logger.error(f"Error optimizing hyperparameters: {e}")
            raise

    async def compare_models(
        self,
        models: Dict[str, Any],
        training_data: TrainingData,
        test_data: Optional[TrainingData] = None
    ) -> List[ModelComparison]:
        """
        Compare multiple models.

        Args:
            models: Dictionary of model names and models
            training_data: Training data
            test_data: Test data (optional)

        Returns:
            List of model comparisons
        """
        try:
            self.logger.info("Starting model comparison", model_count=len(models))

            comparisons = []
            model_names = list(models.keys())

            # Compare each pair of models
            for i in range(len(model_names)):
                for j in range(i + 1, len(model_names)):
                    model1_name = model_names[i]
                    model2_name = model_names[j]

                    # Evaluate both models
                    metrics1 = await self.evaluate_model_performance(
                        models[model1_name], training_data, test_data
                    )
                    metrics2 = await self.evaluate_model_performance(
                        models[model2_name], training_data, test_data
                    )

                    # Calculate comparison metrics
                    comparison_metrics = {
                        'accuracy_diff': metrics1.accuracy - metrics2.accuracy,
                        'f1_diff': metrics1.f1_score - metrics2.f1_score,
                        'cv_score_diff': metrics1.cross_validation_score - metrics2.cross_validation_score,
                        'prediction_time_diff': metrics1.prediction_time - metrics2.prediction_time,
                        'model_size_diff': metrics1.model_size - metrics2.model_size
                    }

                    # Statistical significance test (simplified)
                    statistical_significance = abs(comparison_metrics['accuracy_diff']) > Decimal('0.05')
                    p_value = Decimal('0.05') if statistical_significance else Decimal('0.1')
                    effect_size = abs(comparison_metrics['accuracy_diff'])

                    # Determine recommendation
                    if metrics1.accuracy > metrics2.accuracy:
                        recommendation = f"Model {model1_name} performs better"
                    elif metrics2.accuracy > metrics1.accuracy:
                        recommendation = f"Model {model2_name} performs better"
                    else:
                        recommendation = "Models perform similarly"

                    comparison = ModelComparison(
                        model_1_id=model1_name,
                        model_2_id=model2_name,
                        comparison_metrics=comparison_metrics,
                        statistical_significance=statistical_significance,
                        p_value=p_value,
                        effect_size=effect_size,
                        recommendation=recommendation
                    )

                    comparisons.append(comparison)
                    self.model_comparisons.append(comparison)

            self.logger.info(
                "Model comparison completed",
                comparisons=len(comparisons)
            )

            return comparisons

        except Exception as e:
            self.logger.error(f"Error comparing models: {e}")
            raise

    async def evaluate_model_robustness(
        self,
        model: Any,
        training_data: TrainingData,
        noise_levels: List[Decimal] = [Decimal('0.01'), Decimal('0.05'), Decimal('0.1'), Decimal('0.2')]
    ) -> Dict[str, Any]:
        """
        Evaluate model robustness to noise.

        Args:
            model: Model to evaluate
            training_data: Training data
            noise_levels: List of noise levels to test

        Returns:
            Robustness evaluation results
        """
        try:
            self.logger.info("Starting model robustness evaluation")

            robustness_results = {}

            for noise_level in noise_levels:
                # Add noise to test data
                noisy_features = training_data.features + np.random.normal(
                    0, noise_level, training_data.features.shape
                )

                # Make predictions on noisy data
                y_pred = model.predict(noisy_features)

                # Calculate accuracy
                accuracy = accuracy_score(training_data.labels, y_pred)

                robustness_results[f'noise_{noise_level}'] = {
                    'accuracy': accuracy,
                    'noise_level': noise_level,
                    'degradation': Decimal('1.0') - accuracy
                }

            self.logger.info(
                "Model robustness evaluation completed",
                noise_levels=len(noise_levels)
            )

            return robustness_results

        except Exception as e:
            self.logger.error(f"Error evaluating model robustness: {e}")
            raise

    def _estimate_model_size(self, model: Any) -> Decimal:
        """Estimate model size in MB"""
        try:
            # This would contain actual model size estimation
            # For now, return a placeholder
            return Decimal('1.0')  # MB

        except ConfigurationError as e:
            self.logger.error(f"Error estimating model size: {e}")
            return Decimal('0.0')

    def _initialize_evaluation_config(self) -> Dict[str, Any]:
        """Initialize evaluation configuration"""
        return {
            'default_cv_folds': 5,
            'default_test_size': Decimal('0.2'),
            'scoring_metrics': ['accuracy', 'precision', 'recall', 'f1'],
            'robustness_noise_levels': [Decimal('0.01'), Decimal('0.05'), Decimal('0.1'), Decimal('0.2')],
            'significance_threshold': Decimal('0.05'),
            'effect_size_threshold': Decimal('0.05')
        }

    def _initialize_validation_strategies(self) -> Dict[str, Any]:
        """Initialize validation strategies"""
        return {
            'holdout': {
                'test_size': Decimal('0.2'),
                'random_state': 42,
                'stratify': True
            },
            'cross_validation': {
                'cv_folds': 5,
                'scoring': 'accuracy',
                'stratified': True
            },
            'time_series': {
                'test_size': Decimal('0.2'),
                'shuffle': False
            },
            'bootstrap': {
                'n_bootstrap': 100,
                'sample_size': Decimal('0.8')
            }
        }
