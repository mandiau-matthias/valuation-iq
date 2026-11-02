from src.utils.exceptions import DataQualityError, ExternalServiceError

"""
Pattern Detector

This module handles pattern detection algorithms including
statistical analysis, clustering, and anomaly detection for MCP pattern analysis.
"""

import asyncio
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np

from src.utils.decimal_helpers import from_decimal, to_decimal
from src.utils.logging import get_logger

from .industry_grouping import group_by_industry
from .pattern_types import (
    PATTERN_THRESHOLDS,
    ClusteringResult,
    ConfidenceLevel,
    InsightType,
    PatternInsight,
    PatternType,
    StatisticalAnalysis,
    TemporalPattern,
    ValuationData,
)

# Pandas for data processing (with fallback)
try:
    import pandas as pd

    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False

# Scikit-learn for ML (with fallback)
try:
    from sklearn.cluster import DBSCAN, KMeans
    from sklearn.ensemble import IsolationForest
    from sklearn.metrics import silhouette_score
    from sklearn.preprocessing import StandardScaler

    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

logger = get_logger(__name__)


class PatternDetector:
    """
    Pattern detection service for MCP analysis

    Handles:
    - Statistical pattern detection
    - Clustering analysis
    - Anomaly detection
    - Correlation analysis
    - Trend detection
    """

    def __init__(self):
        """Initialize the pattern detector"""
        self.logger = logger
        self.patterns_cache = {}
        self.clustering_models = {}

        self.logger.info("PatternDetector initialized")

    async def detect_business_type_patterns(
        self, valuations: List[ValuationData]
    ) -> List[PatternInsight]:
        """
        Detect patterns in business type data

        Args:
            valuations: List of valuation data

        Returns:
            List of business type pattern insights
        """
        try:
            self.logger.info("Detecting business type patterns", valuations_count=len(valuations))

            insights = []

            # Group by business type
            business_type_groups = self._group_by_business_type(valuations)

            # Analyze each business type
            for business_type, type_valuations in business_type_groups.items():
                if len(type_valuations) < 3:  # Need minimum data points
                    continue

                # Statistical analysis
                stats = await self._analyze_business_type_statistics(type_valuations)

                # Pattern detection
                patterns = await self._detect_business_type_patterns(type_valuations, stats)
                insights.extend(patterns)

            # Cross-business type patterns
            cross_patterns = await self._detect_cross_business_type_patterns(valuations)
            insights.extend(cross_patterns)

            self.logger.info(
                "Business type pattern detection completed", patterns_found=len(insights)
            )

            return insights

        except ExternalServiceError as e:
            self.logger.error(f"Business type pattern detection failed: {e}")
            return []

    async def detect_industry_patterns(
        self, valuations: List[ValuationData]
    ) -> List[PatternInsight]:
        """
        Detect patterns in industry data

        Args:
            valuations: List of valuation data

        Returns:
            List of industry pattern insights
        """
        try:
            self.logger.info("Detecting industry patterns", valuations_count=len(valuations))

            insights = []

            # Group by industry
            industry_groups = group_by_industry(valuations)

            # Analyze each industry
            for industry, industry_valuations in industry_groups.items():
                if len(industry_valuations) < 3:
                    continue

                # Industry-specific analysis
                industry_patterns = await self._detect_industry_specific_patterns(
                    industry, industry_valuations
                )
                insights.extend(industry_patterns)

            # Cross-industry patterns
            cross_patterns = await self._detect_cross_industry_patterns(valuations)
            insights.extend(cross_patterns)

            self.logger.info("Industry pattern detection completed", patterns_found=len(insights))

            return insights

        except Exception as e:
            self.logger.error(f"Industry pattern detection failed: {e}")
            return []

    async def detect_financial_patterns(
        self, valuations: List[ValuationData]
    ) -> List[PatternInsight]:
        """
        Detect patterns in financial data

        Args:
            valuations: List of valuation data

        Returns:
            List of financial pattern insights
        """
        try:
            self.logger.info("Detecting financial patterns", valuations_count=len(valuations))

            insights = []

            # Revenue patterns
            revenue_patterns = await self._detect_revenue_patterns(valuations)
            insights.extend(revenue_patterns)

            # EBITDA patterns
            ebitda_patterns = await self._detect_ebitda_patterns(valuations)
            insights.extend(ebitda_patterns)

            # Equity value patterns
            equity_patterns = await self._detect_equity_value_patterns(valuations)
            insights.extend(equity_patterns)

            # Financial ratio patterns
            ratio_patterns = await self._detect_financial_ratio_patterns(valuations)
            insights.extend(ratio_patterns)

            self.logger.info("Financial pattern detection completed", patterns_found=len(insights))

            return insights

        except Exception as e:
            self.logger.error(f"Financial pattern detection failed: {e}")
            return []

    async def detect_temporal_patterns(
        self, valuations: List[ValuationData]
    ) -> List[TemporalPattern]:
        """
        Detect temporal patterns in valuation data

        Args:
            valuations: List of valuation data

        Returns:
            List of temporal patterns
        """
        try:
            self.logger.info("Detecting temporal patterns", valuations_count=len(valuations))

            patterns = []

            # Sort by date
            sorted_valuations = sorted(valuations, key=lambda x: x.valuation_date)

            # Time series analysis
            time_series_patterns = await self._analyze_time_series(sorted_valuations)
            patterns.extend(time_series_patterns)

            # Seasonal patterns
            seasonal_patterns = await self._detect_seasonal_patterns(sorted_valuations)
            patterns.extend(seasonal_patterns)

            # Cyclical patterns
            cyclical_patterns = await self._detect_cyclical_patterns(sorted_valuations)
            patterns.extend(cyclical_patterns)

            # Trend analysis
            trend_patterns = await self._detect_trend_patterns(sorted_valuations)
            patterns.extend(trend_patterns)

            self.logger.info("Temporal pattern detection completed", patterns_found=len(patterns))

            return patterns

        except Exception as e:
            self.logger.error(f"Temporal pattern detection failed: {e}")
            return []

    async def perform_clustering_analysis(
        self,
        valuations: List[ValuationData],
        algorithm: str = "kmeans",
        n_clusters: Optional[int] = None,
    ) -> ClusteringResult:
        """
        Perform clustering analysis on valuation data

        Args:
            valuations: List of valuation data
            algorithm: Clustering algorithm to use
            n_clusters: Number of clusters (optional)

        Returns:
            Clustering result
        """
        try:
            self.logger.info(
                "Performing clustering analysis", algorithm=algorithm, data_points=len(valuations)
            )

            if not SKLEARN_AVAILABLE:
                self.logger.warning("Scikit-learn not available, skipping clustering")
                return ClusteringResult(
                    algorithm=algorithm,
                    n_clusters=0,
                    silhouette_score=0.0,
                    cluster_labels=[],
                    cluster_centers=[],
                    cluster_sizes=[],
                    cluster_characteristics={},
                )

            # Prepare data for clustering
            features = self._prepare_clustering_features(valuations)

            if len(features) < 3:
                self.logger.warning("Insufficient data for clustering")
                return ClusteringResult(
                    algorithm=algorithm,
                    n_clusters=0,
                    silhouette_score=0.0,
                    cluster_labels=[0] * len(valuations),
                    cluster_centers=[],
                    cluster_sizes=[],
                    cluster_characteristics={},
                )

            # Standardize features
            scaler = StandardScaler()
            features_scaled = scaler.fit_transform(features)

            # Perform clustering
            if algorithm == "kmeans":
                if n_clusters is None:
                    n_clusters = min(8, len(valuations) // 3)

                clusterer = KMeans(n_clusters=n_clusters, random_state=42)
                cluster_labels = clusterer.fit_predict(features_scaled)
                cluster_centers = clusterer.cluster_centers_

            elif algorithm == "dbscan":
                clusterer = DBSCAN(eps=0.5, min_samples=3)
                cluster_labels = clusterer.fit_predict(features_scaled)
                cluster_centers = []

            else:
                raise ValueError(f"Unsupported clustering algorithm: {algorithm}")

            # Calculate silhouette score
            if len(set(cluster_labels)) > 1:
                silhouette_avg = silhouette_score(features_scaled, cluster_labels)
            else:
                silhouette_avg = 0.0

            # Analyze clusters
            cluster_sizes = [list(cluster_labels).count(i) for i in set(cluster_labels)]
            cluster_characteristics = self._analyze_cluster_characteristics(
                valuations, cluster_labels, features
            )

            result = ClusteringResult(
                algorithm=algorithm,
                n_clusters=len(set(cluster_labels)),
                silhouette_score=silhouette_avg,
                cluster_labels=cluster_labels.tolist(),
                cluster_centers=cluster_centers.tolist() if len(cluster_centers) > 0 else [],
                cluster_sizes=cluster_sizes,
                cluster_characteristics=cluster_characteristics,
            )

            self.logger.info(
                "Clustering analysis completed",
                n_clusters=result.n_clusters,
                silhouette_score=result.silhouette_score,
            )

            return result

        except Exception as e:
            self.logger.error(f"Clustering analysis failed: {e}")
            return ClusteringResult(
                algorithm=algorithm,
                n_clusters=0,
                silhouette_score=0.0,
                cluster_labels=[],
                cluster_centers=[],
                cluster_sizes=[],
                cluster_characteristics={},
            )

    async def detect_anomalies(self, valuations: List[ValuationData]) -> List[PatternInsight]:
        """
        Detect anomalies in valuation data

        Args:
            valuations: List of valuation data

        Returns:
            List of anomaly insights
        """
        try:
            self.logger.info("Detecting anomalies", valuations_count=len(valuations))

            insights = []

            if not SKLEARN_AVAILABLE or len(valuations) < 4:
                self.logger.warning(
                    "Insufficient data or sklearn not available for anomaly detection"
                )
                return insights

            # Prepare features
            features = self._prepare_clustering_features(valuations)

            # Use Isolation Forest for anomaly detection
            iso_forest = IsolationForest(contamination=0.1, random_state=42)
            anomaly_labels = iso_forest.fit_predict(features)

            # Identify anomalies
            anomalies = [valuations[i] for i, label in enumerate(anomaly_labels) if label == -1]

            if anomalies:
                insight = PatternInsight(
                    insight_id=f"anomaly_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
                    insight_type=InsightType.FINANCIAL,
                    pattern_type=PatternType.ANOMALY,
                    description=f"Detected {len(anomalies)} anomalous valuations",
                    confidence=ConfidenceLevel.MEDIUM,
                    significance_score=0.8,
                    affected_companies=[v.company_id for v in anomalies],
                    timeframe=(
                        min(v.valuation_date for v in anomalies),
                        max(v.valuation_date for v in anomalies),
                    ),
                    supporting_data={
                        "anomaly_count": len(anomalies),
                        "total_valuations": len(valuations),
                        "anomaly_rate": len(anomalies) / len(valuations),
                    },
                    recommendations=["Investigate anomalous valuations for data quality issues"],
                )
                insights.append(insight)

            self.logger.info("Anomaly detection completed", anomalies_found=len(anomalies))

            return insights

        except DataQualityError as e:
            self.logger.error(f"Anomaly detection failed: {e}")
            return []

    def _group_by_business_type(
        self, valuations: List[ValuationData]
    ) -> Dict[str, List[ValuationData]]:
        """Group valuations by business type"""
        groups = {}
        for valuation in valuations:
            business_type = valuation.business_type
            if business_type not in groups:
                groups[business_type] = []
            groups[business_type].append(valuation)
        return groups

    def _prepare_clustering_features(self, valuations: List[ValuationData]) -> List[List[Decimal]]:
        """Prepare features for clustering analysis"""
        features = []
        for valuation in valuations:
            feature_vector = [
                valuation.revenue,
                valuation.ebitda,
                valuation.equity_value,
                valuation.confidence_score,
                # Add more features as needed
            ]
            features.append(feature_vector)
        return features

    def _analyze_cluster_characteristics(
        self,
        valuations: List[ValuationData],
        cluster_labels: List[int],
        features: List[List[Decimal]],
    ) -> Dict[int, Dict[str, Any]]:
        """Analyze characteristics of each cluster"""
        characteristics = {}

        for cluster_id in set(cluster_labels):
            cluster_valuations = [
                valuations[i] for i, label in enumerate(cluster_labels) if label == cluster_id
            ]
            cluster_features = [
                features[i] for i, label in enumerate(cluster_labels) if label == cluster_id
            ]

            if not cluster_valuations:
                continue

            # Calculate cluster statistics
            avg_revenue = np.mean([v.revenue for v in cluster_valuations])
            avg_ebitda = np.mean([v.ebitda for v in cluster_valuations])
            avg_equity_value = np.mean([v.equity_value for v in cluster_valuations])

            # Business type distribution
            business_types = [v.business_type for v in cluster_valuations]
            business_type_dist = {bt: business_types.count(bt) for bt in set(business_types)}

            # Industry distribution
            industries = [v.industry for v in cluster_valuations]
            industry_dist = {ind: industries.count(ind) for ind in set(industries)}

            characteristics[cluster_id] = {
                "size": len(cluster_valuations),
                "avg_revenue": avg_revenue,
                "avg_ebitda": avg_ebitda,
                "avg_equity_value": avg_equity_value,
                "business_type_distribution": business_type_dist,
                "industry_distribution": industry_dist,
                "companies": [v.company_id for v in cluster_valuations],
            }

        return characteristics

    async def _analyze_business_type_statistics(
        self, valuations: List[ValuationData]
    ) -> StatisticalAnalysis:
        """Analyze statistics for a business type"""
        revenues = [v.revenue for v in valuations]
        ebitdas = [v.ebitda for v in valuations]
        equity_values = [v.equity_value for v in valuations]

        return StatisticalAnalysis(
            analysis_type="business_type",
            sample_size=len(valuations),
            mean=np.mean(revenues),
            median=np.median(revenues),
            std_dev=np.std(revenues),
            variance=np.var(revenues),
            skewness=0.0,  # Would need scipy for proper calculation
            kurtosis=0.0,  # Would need scipy for proper calculation
            correlation_matrix={},
            significance_tests={},
        )

    async def _detect_business_type_patterns(
        self, valuations: List[ValuationData], stats: StatisticalAnalysis
    ) -> List[PatternInsight]:
        """Detect patterns specific to a business type"""
        insights = []

        # Example pattern detection logic
        if stats.std_dev > stats.mean * 0.5:  # High variance
            insight = PatternInsight(
                insight_id=f"business_type_variance_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
                insight_type=InsightType.BUSINESS_TYPE,
                pattern_type=PatternType.ANOMALY,
                description="High variance in business type valuations",
                confidence=ConfidenceLevel.MEDIUM,
                significance_score=0.6,
                affected_companies=[v.company_id for v in valuations],
                timeframe=(
                    min(v.valuation_date for v in valuations),
                    max(v.valuation_date for v in valuations),
                ),
                supporting_data={"variance": stats.variance, "std_dev": stats.std_dev},
            )
            insights.append(insight)

        return insights

    async def _detect_cross_business_type_patterns(
        self, valuations: List[ValuationData]
    ) -> List[PatternInsight]:
        """Detect patterns across business types"""
        # Implementation for cross-business type pattern detection
        return []

    async def _detect_industry_specific_patterns(
        self, industry: str, valuations: List[ValuationData]
    ) -> List[PatternInsight]:
        """Detect patterns specific to an industry"""
        # Implementation for industry-specific pattern detection
        return []

    async def _detect_cross_industry_patterns(
        self, valuations: List[ValuationData]
    ) -> List[PatternInsight]:
        """Detect patterns across industries"""
        # Implementation for cross-industry pattern detection
        return []

    async def _detect_revenue_patterns(
        self, valuations: List[ValuationData]
    ) -> List[PatternInsight]:
        """Detect revenue patterns"""
        # Implementation for revenue pattern detection
        return []

    async def _detect_ebitda_patterns(
        self, valuations: List[ValuationData]
    ) -> List[PatternInsight]:
        """Detect EBITDA patterns"""
        # Implementation for EBITDA pattern detection
        return []

    async def _detect_equity_value_patterns(
        self, valuations: List[ValuationData]
    ) -> List[PatternInsight]:
        """Detect equity value patterns"""
        # Implementation for equity value pattern detection
        return []

    async def _detect_financial_ratio_patterns(
        self, valuations: List[ValuationData]
    ) -> List[PatternInsight]:
        """Detect financial ratio patterns"""
        # Implementation for financial ratio pattern detection
        return []

    async def _analyze_time_series(self, valuations: List[ValuationData]) -> List[TemporalPattern]:
        """Analyze time series patterns"""
        # Implementation for time series analysis
        return []

    async def _detect_seasonal_patterns(
        self, valuations: List[ValuationData]
    ) -> List[TemporalPattern]:
        """Detect seasonal patterns"""
        # Implementation for seasonal pattern detection
        return []

    async def _detect_cyclical_patterns(
        self, valuations: List[ValuationData]
    ) -> List[TemporalPattern]:
        """Detect cyclical patterns"""
        # Implementation for cyclical pattern detection
        return []

    async def _detect_trend_patterns(
        self, valuations: List[ValuationData]
    ) -> List[TemporalPattern]:
        """Detect trend patterns"""
        # Implementation for trend pattern detection
        return []
