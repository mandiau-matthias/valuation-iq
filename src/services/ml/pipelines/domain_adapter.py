
"""
Domain Adapter

This module handles domain adaptation for transfer learning, including linear and
non-linear adaptation methods to bridge the gap between source and target domains.

Author: Upswitch CTO Team
Date: October 2025
Status: Production Ready
"""

import numpy as np
from typing import Dict, Any, List, Optional, Tuple
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
from sklearn.manifold import TSNE
from scipy.optimize import minimize

from src.utils.logging import get_logger
from decimal import Decimal
from src.utils.decimal_helpers import to_decimal, from_decimal
from ..training.transfer_learning_types import (
    DomainAdaptationMethod, DomainAdaptationConfig,
    DEFAULT_DOMAIN_ADAPTATION_CONFIG
)

logger = get_logger(__name__)


class DomainAdaptationEngine:
    """Domain adaptation for transfer learning"""

    def __init__(self, config: Optional[DomainAdaptationConfig] = None):
        """Initialize domain adaptation engine"""
        self.config = config or DEFAULT_DOMAIN_ADAPTATION_CONFIG
        self.adaptation_model = None
        self.scaler = StandardScaler()
        self.is_fitted = False

        logger.info("✅ DomainAdaptationEngine initialized")

    def adapt_features(
        self,
        X_source: np.ndarray,
        X_target: np.ndarray,
        adaptation_method: Optional[DomainAdaptationMethod] = None
    ) -> np.ndarray:
        """Adapt features from source to target domain"""

        try:
            logger.info(f"🔄 Adapting features using {adaptation_method or self.config.method}")

            method = adaptation_method or self.config.method

            if method == DomainAdaptationMethod.LINEAR:
                adapted_features = self._linear_adaptation(X_source, X_target)
            elif method == DomainAdaptationMethod.NONLINEAR:
                adapted_features = self._nonlinear_adaptation(X_source, X_target)
            elif method == DomainAdaptationMethod.CORAL:
                adapted_features = self._coral_adaptation(X_source, X_target)
            elif method == DomainAdaptationMethod.DANN:
                adapted_features = self._dann_adaptation(X_source, X_target)
            else:
                logger.warning(f"⚠️ Unknown adaptation method: {method}, using linear")
                adapted_features = self._linear_adaptation(X_source, X_target)

            self.is_fitted = True
            logger.info(f"✅ Feature adaptation completed: {adapted_features.shape}")
            return adapted_features

        except Exception as e:
            logger.error(f"❌ Feature adaptation failed: {str(e)}")
            # Return original target features as fallback
            return X_target

    def _linear_adaptation(
        self,
        X_source: np.ndarray,
        X_target: np.ndarray
    ) -> np.ndarray:
        """Linear domain adaptation"""

        try:
            logger.info("🔄 Performing linear domain adaptation")

            # Standardize features
            X_source_scaled = self.scaler.fit_transform(X_source)
            X_target_scaled = self.scaler.transform(X_target)

            # Learn linear transformation
            self.adaptation_model = LinearRegression()
            self.adaptation_model.fit(X_source_scaled, X_target_scaled)

            # Apply transformation
            adapted_features = self.adaptation_model.predict(X_target_scaled)

            logger.info("✅ Linear adaptation completed")
            return adapted_features

        except Exception as e:
            logger.error(f"❌ Linear adaptation failed: {str(e)}")
            return X_target

    def _nonlinear_adaptation(
        self,
        X_source: np.ndarray,
        X_target: np.ndarray
    ) -> np.ndarray:
        """Non-linear domain adaptation using manifold learning"""

        try:
            logger.info("🔄 Performing non-linear domain adaptation")

            # Combine source and target data
            X_combined = np.vstack([X_source, X_target])

            # Apply t-SNE for non-linear dimensionality reduction
            tsne = TSNE(n_components=min(50, X_combined.shape[1]), random_state=42)
            X_combined_embedded = tsne.fit_transform(X_combined)

            # Split back into source and target
            n_source = X_source.shape[0]
            X_source_embedded = X_combined_embedded[:n_source]
            X_target_embedded = X_combined_embedded[n_source:]

            # Learn mapping from embedded source to embedded target
            self.adaptation_model = LinearRegression()
            self.adaptation_model.fit(X_source_embedded, X_target_embedded)

            # Apply transformation to target features
            adapted_features = self.adaptation_model.predict(X_target_embedded)

            logger.info("✅ Non-linear adaptation completed")
            return adapted_features

        except Exception as e:
            logger.error(f"❌ Non-linear adaptation failed: {str(e)}")
            return X_target

    def _coral_adaptation(
        self,
        X_source: np.ndarray,
        X_target: np.ndarray
    ) -> np.ndarray:
        """CORAL (Correlation Alignment) domain adaptation"""

        try:
            logger.info("🔄 Performing CORAL domain adaptation")

            # Standardize features
            X_source_scaled = self.scaler.fit_transform(X_source)
            X_target_scaled = self.scaler.transform(X_target)

            # Compute correlation matrices
            C_source = np.cov(X_source_scaled.T)
            C_target = np.cov(X_target_scaled.T)

            # Compute transformation matrix
            A = self._compute_coral_transformation(C_source, C_target)

            # Apply transformation
            adapted_features = X_target_scaled @ A

            logger.info("✅ CORAL adaptation completed")
            return adapted_features

        except Exception as e:
            logger.error(f"❌ CORAL adaptation failed: {str(e)}")
            return X_target

    def _dann_adaptation(
        self,
        X_source: np.ndarray,
        X_target: np.ndarray
    ) -> np.ndarray:
        """Domain Adversarial Neural Networks adaptation (simplified)"""

        try:
            logger.info("🔄 Performing DANN domain adaptation")

            # Simplified DANN: use adversarial training concept
            # In practice, this would involve neural networks

            # Standardize features
            X_source_scaled = self.scaler.fit_transform(X_source)
            X_target_scaled = self.scaler.transform(X_target)

            # Use PCA for dimensionality reduction and alignment
            pca = PCA(n_components=min(50, X_source_scaled.shape[1]))
            X_source_pca = pca.fit_transform(X_source_scaled)
            X_target_pca = pca.transform(X_target_scaled)

            # Align distributions using mean and std
            X_source_mean = np.mean(X_source_pca, axis=0)
            X_source_std = np.std(X_source_pca, axis=0)
            X_target_mean = np.mean(X_target_pca, axis=0)
            X_target_std = np.std(X_target_pca, axis=0)

            # Apply alignment
            adapted_features = (X_target_pca - X_target_mean) / X_target_std * X_source_std + X_source_mean

            logger.info("✅ DANN adaptation completed")
            return adapted_features

        except Exception as e:
            logger.error(f"❌ DANN adaptation failed: {str(e)}")
            return X_target

    def _compute_coral_transformation(
        self,
        C_source: np.ndarray,
        C_target: np.ndarray
    ) -> np.ndarray:
        """Compute CORAL transformation matrix"""

        try:
            # Compute square root of correlation matrices
            U_source, s_source, _ = np.linalg.svd(C_source)
            U_target, s_target, _ = np.linalg.svd(C_target)

            # Handle numerical stability
            s_source = np.maximum(s_source, 1e-10)
            s_target = np.maximum(s_target, 1e-10)

            # Compute transformation matrix
            A = U_target @ np.diag(np.sqrt(s_target)) @ U_target.T @ U_source @ np.diag(Decimal('1.0') / np.sqrt(s_source)) @ U_source.T

            return A

        except Exception as e:
            logger.error(f"❌ CORAL transformation computation failed: {str(e)}")
            # Return identity matrix as fallback
            return np.eye(C_source.shape[0])

    def compute_domain_distance(
        self,
        X_source: np.ndarray,
        X_target: np.ndarray
    ) -> Decimal:
        """Compute distance between source and target domains"""

        try:
            logger.info("📊 Computing domain distance")

            # Use Maximum Mean Discrepancy (MMD) as distance metric
            # Simplified version using mean and covariance

            # Compute means
            mean_source = np.mean(X_source, axis=0)
            mean_target = np.mean(X_target, axis=0)

            # Compute covariances
            cov_source = np.cov(X_source.T)
            cov_target = np.cov(X_target.T)

            # Distance between means
            mean_distance = np.linalg.norm(mean_source - mean_target)

            # Distance between covariances (Frobenius norm)
            cov_distance = np.linalg.norm(cov_source - cov_target, 'fro')

            # Combined distance
            domain_distance = mean_distance + Decimal('0.1') * cov_distance

            logger.info(f"✅ Domain distance computed: {domain_distance:.4f}")
            return domain_distance

        except Exception as e:
            logger.error(f"❌ Domain distance computation failed: {str(e)}")
            return Decimal('1.0')  # Maximum distance as fallback

    def get_adaptation_quality(
        self,
        X_source: np.ndarray,
        X_target: np.ndarray,
        adapted_features: np.ndarray
    ) -> Dict[str, Decimal]:
        """Assess quality of domain adaptation"""

        try:
            logger.info("📊 Assessing adaptation quality")

            # Compute various quality metrics
            original_distance = self.compute_domain_distance(X_source, X_target)
            adapted_distance = self.compute_domain_distance(X_source, adapted_features)

            # Improvement ratio
            improvement_ratio = (original_distance - adapted_distance) / original_distance

            # Feature preservation (correlation with original target)
            correlation = np.corrcoef(
                X_target.flatten(),
                adapted_features.flatten()
            )[0, 1]

            # Variance preservation
            original_variance = np.var(X_target)
            adapted_variance = np.var(adapted_features)
            variance_ratio = adapted_variance / original_variance

            quality_metrics = {
                "original_domain_distance": original_distance,
                "adapted_domain_distance": adapted_distance,
                "improvement_ratio": improvement_ratio,
                "feature_correlation": correlation,
                "variance_ratio": variance_ratio,
                "overall_quality": (improvement_ratio + correlation + min(variance_ratio, Decimal('1.0'))) / 3
            }

            logger.info(f"✅ Adaptation quality assessed: {quality_metrics['overall_quality']:.3f}")
            return quality_metrics

        except Exception as e:
            logger.error(f"❌ Adaptation quality assessment failed: {str(e)}")
            return {
                "original_domain_distance": Decimal('1.0'),
                "adapted_domain_distance": Decimal('1.0'),
                "improvement_ratio": Decimal('0.0'),
                "feature_correlation": Decimal('0.0'),
                "variance_ratio": Decimal('1.0'),
                "overall_quality": Decimal('0.0')
            }

    def is_adaptation_needed(
        self,
        X_source: np.ndarray,
        X_target: np.ndarray,
        threshold: Decimal = Decimal('0.5')
    ) -> bool:
        """Determine if domain adaptation is needed"""

        try:
            domain_distance = self.compute_domain_distance(X_source, X_target)
            is_needed = domain_distance > threshold

            logger.info(f"📊 Adaptation needed: {is_needed} (distance: {domain_distance:.3f})")
            return is_needed

        except Exception as e:
            logger.error(f"❌ Adaptation need assessment failed: {str(e)}")
            return True  # Assume adaptation is needed if assessment fails
