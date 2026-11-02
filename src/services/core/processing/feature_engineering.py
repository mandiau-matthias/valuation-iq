"""
Feature Engineering Module for MCP Service

This module handles feature engineering and data transformation
for the MCP service pattern recognition and analysis.
"""

import asyncio
from typing import Dict, Any, List, Optional, Tuple, Union
import numpy as np
from src.utils.logging import get_logger
from decimal import Decimal
from src.utils.decimal_helpers import to_decimal, from_decimal
from ..workflows.mcp_types import (
    ValuationData, FeatureEngineeringConfig, DEFAULT_FEATURE_ENGINEERING_CONFIG
)

# Pandas for data processing (with fallback)
try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False

logger = get_logger(__name__)


class FeatureEngineeringService:
    """
    Service for feature engineering and data transformation
    for MCP pattern recognition and analysis.
    """

    def __init__(self, config: Optional[FeatureEngineeringConfig] = None):
        """Initialize feature engineering service"""
        self.config = config or DEFAULT_FEATURE_ENGINEERING_CONFIG
        self.logger = logger
        self.scaler = None
        self.feature_importance_scores = {}

    async def prepare_training_data(
        self,
        valuations: List[ValuationData],
        target_column: str = "equity_value"
    ) -> Tuple[np.ndarray, np.ndarray, List[str]]:
        """
        Prepare training data for ML models

        Args:
            valuations: List of ValuationData objects
            target_column: Target column for prediction

        Returns:
            Tuple of (features, targets, feature_names)
        """
        try:
            self.logger.info(
                "Starting feature engineering for training data",
                records_count=len(valuations),
                target_column=target_column
            )

            if not PANDAS_AVAILABLE:
                self.logger.warning("Pandas not available, using fallback feature engineering")
                return self._prepare_training_data_fallback(valuations, target_column)

            # Convert to DataFrame
            df = self._convert_valuations_to_dataframe(valuations)

            # Extract features
            features_df = self._extract_features(df)

            # Extract target
            targets = self._extract_targets(df, target_column)

            # Feature scaling
            if self.config.enable_feature_scaling:
                features_df = self._scale_features(features_df)

            # Feature selection
            if self.config.enable_feature_selection:
                features_df, selected_features = self._select_features(features_df, targets)
            else:
                selected_features = features_df.columns.tolist()

            # Convert to numpy arrays
            features = features_df.values
            targets = targets.values if hasattr(targets, 'values') else np.array(targets)

            self.logger.info(
                "Feature engineering completed",
                features_shape=features.shape,
                targets_shape=targets.shape,
                selected_features_count=len(selected_features)
            )

            return features, targets, selected_features

        except Exception as e:
            self.logger.error(
                "Failed to prepare training data",
                error=str(e),
                records_count=len(valuations)
            )
            raise

    async def extract_pattern_features(
        self,
        valuations: List[ValuationData]
    ) -> Dict[str, Any]:
        """
        Extract features for pattern recognition

        Args:
            valuations: List of ValuationData objects

        Returns:
            Dictionary of pattern features
        """
        try:
            self.logger.info(
                "Starting pattern feature extraction",
                records_count=len(valuations)
            )

            if not PANDAS_AVAILABLE:
                return self._extract_pattern_features_fallback(valuations)

            # Convert to DataFrame
            df = self._convert_valuations_to_dataframe(valuations)

            # Extract pattern features
            pattern_features = {}

            # Business type patterns
            pattern_features["business_type_patterns"] = self._extract_business_type_patterns(df)

            # Industry patterns
            pattern_features["industry_patterns"] = self._extract_industry_patterns(df)

            # Financial patterns
            pattern_features["financial_patterns"] = self._extract_financial_patterns(df)

            # Valuation method patterns
            pattern_features["valuation_method_patterns"] = self._extract_valuation_method_patterns(df)

            # Temporal patterns
            pattern_features["temporal_patterns"] = self._extract_temporal_patterns(df)

            # Correlation patterns
            pattern_features["correlation_patterns"] = self._extract_correlation_patterns(df)

            self.logger.info(
                "Pattern feature extraction completed",
                pattern_types=len(pattern_features)
            )

            return pattern_features

        except Exception as e:
            self.logger.error(
                "Failed to extract pattern features",
                error=str(e),
                records_count=len(valuations)
            )
            raise

    async def create_derived_features(
        self,
        valuations: List[ValuationData]
    ) -> List[Dict[str, Any]]:
        """
        Create derived features from valuation data

        Args:
            valuations: List of ValuationData objects

        Returns:
            List of derived feature dictionaries
        """
        try:
            self.logger.info(
                "Starting derived feature creation",
                records_count=len(valuations)
            )

            derived_features = []

            for valuation in valuations:
                features = {}

                # Financial ratios
                if valuation.revenue and valuation.revenue > 0:
                    features["revenue_to_equity_ratio"] = valuation.equity_value / valuation.revenue

                if valuation.ebitda and valuation.ebitda != 0:
                    features["ebitda_margin"] = valuation.ebitda / valuation.revenue if valuation.revenue else 0
                    features["equity_to_ebitda_ratio"] = valuation.equity_value / valuation.ebitda

                # Growth indicators
                features["revenue_growth_indicator"] = 1 if valuation.revenue > 1000000 else 0
                features["ebitda_growth_indicator"] = 1 if valuation.ebitda > 100000 else 0

                # Valuation method indicators
                features["dcf_method"] = 1 if "dcf" in valuation.valuation_method.lower() else 0
                features["multiples_method"] = 1 if "multiple" in valuation.valuation_method.lower() else 0
                features["asset_method"] = 1 if "asset" in valuation.valuation_method.lower() else 0

                # Confidence indicators
                features["high_confidence"] = 1 if valuation.confidence_score > 0.8 else 0
                features["medium_confidence"] = 1 if 0.5 <= valuation.confidence_score <= 0.8 else 0
                features["low_confidence"] = 1 if valuation.confidence_score < 0.5 else 0

                # Business type indicators
                features["corporation"] = 1 if valuation.business_type.lower() == "corporation" else 0
                features["llc"] = 1 if valuation.business_type.lower() == "llc" else 0
                features["partnership"] = 1 if valuation.business_type.lower() == "partnership" else 0

                # Industry indicators
                features["technology"] = 1 if "tech" in valuation.industry.lower() else 0
                features["healthcare"] = 1 if "health" in valuation.industry.lower() else 0
                features["finance"] = 1 if "fin" in valuation.industry.lower() else 0

                derived_features.append(features)

            self.logger.info(
                "Derived feature creation completed",
                features_created=len(derived_features)
            )

            return derived_features

        except Exception as e:
            self.logger.error(
                "Failed to create derived features",
                error=str(e),
                records_count=len(valuations)
            )
            raise

    def _convert_valuations_to_dataframe(self, valuations: List[ValuationData]) -> pd.DataFrame:
        """Convert ValuationData objects to pandas DataFrame"""
        data = []
        for valuation in valuations:
            data.append({
                "id": valuation.id,
                "business_type": valuation.business_type,
                "industry": valuation.industry,
                "revenue": valuation.revenue,
                "ebitda": valuation.ebitda,
                "equity_value": valuation.equity_value,
                "valuation_method": valuation.valuation_method,
                "confidence_score": valuation.confidence_score,
                "created_at": valuation.created_at,
                "updated_at": valuation.updated_at
            })
        return pd.DataFrame(data)

    def _extract_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Extract features from DataFrame"""
        features_df = df.copy()

        # Convert categorical variables to numerical
        features_df["business_type_encoded"] = pd.Categorical(features_df["business_type"]).codes
        features_df["industry_encoded"] = pd.Categorical(features_df["industry"]).codes
        features_df["valuation_method_encoded"] = pd.Categorical(features_df["valuation_method"]).codes

        # Create derived features
        features_df["revenue_to_equity_ratio"] = features_df["equity_value"] / features_df["revenue"]
        features_df["ebitda_margin"] = features_df["ebitda"] / features_df["revenue"]
        features_df["equity_to_ebitda_ratio"] = features_df["equity_value"] / features_df["ebitda"]

        # Select numerical features
        numerical_features = [
            "revenue", "ebitda", "equity_value", "confidence_score",
            "business_type_encoded", "industry_encoded", "valuation_method_encoded",
            "revenue_to_equity_ratio", "ebitda_margin", "equity_to_ebitda_ratio"
        ]

        return features_df[numerical_features]

    def _extract_targets(self, df: pd.DataFrame, target_column: str) -> pd.Series:
        """Extract target values from DataFrame"""
        return df[target_column]

    def _scale_features(self, features_df: pd.DataFrame) -> pd.DataFrame:
        """Scale features using specified method"""
        from sklearn.preprocessing import StandardScaler, MinMaxScaler, RobustScaler

        if self.config.scaling_method == "standard":
            scaler = StandardScaler()
        elif self.config.scaling_method == "minmax":
            scaler = MinMaxScaler()
        elif self.config.scaling_method == "robust":
            scaler = RobustScaler()
        else:
            scaler = StandardScaler()

        # Fit and transform features
        scaled_features = scaler.fit_transform(features_df)
        self.scaler = scaler

        # Convert back to DataFrame
        scaled_df = pd.DataFrame(scaled_features, columns=features_df.columns)

        return scaled_df

    def _select_features(self, features_df: pd.DataFrame, targets: pd.Series) -> Tuple[pd.DataFrame, List[str]]:
        """Select most important features"""
        from sklearn.feature_selection import SelectKBest, f_regression, mutual_info_regression

        if self.config.feature_selection_method == "correlation":
            # Select features based on correlation with target
            correlations = features_df.corrwith(targets).abs()
            selected_features = correlations.nlargest(self.config.max_features).index.tolist()
        elif self.config.feature_selection_method == "mutual_info":
            # Select features based on mutual information
            selector = SelectKBest(score_func=mutual_info_regression, k=self.config.max_features)
            selector.fit(features_df, targets)
            selected_features = features_df.columns[selector.get_support()].tolist()
        else:
            # Select all features
            selected_features = features_df.columns.tolist()

        # Store feature importance scores
        self.feature_importance_scores = dict(zip(selected_features, [1.0] * len(selected_features)))

        return features_df[selected_features], selected_features

    def _extract_business_type_patterns(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Extract business type patterns"""
        patterns = {}

        for business_type in df["business_type"].unique():
            subset = df[df["business_type"] == business_type]
            patterns[business_type] = {
                "count": len(subset),
                "avg_revenue": subset["revenue"].mean(),
                "avg_ebitda": subset["ebitda"].mean(),
                "avg_equity_value": subset["equity_value"].mean(),
                "avg_confidence": subset["confidence_score"].mean()
            }

        return patterns

    def _extract_industry_patterns(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Extract industry patterns"""
        patterns = {}

        for industry in df["industry"].unique():
            subset = df[df["industry"] == industry]
            patterns[industry] = {
                "count": len(subset),
                "avg_revenue": subset["revenue"].mean(),
                "avg_ebitda": subset["ebitda"].mean(),
                "avg_equity_value": subset["equity_value"].mean(),
                "avg_confidence": subset["confidence_score"].mean()
            }

        return patterns

    def _extract_financial_patterns(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Extract financial patterns"""
        patterns = {
            "revenue_distribution": {
                "mean": df["revenue"].mean(),
                "std": df["revenue"].std(),
                "min": df["revenue"].min(),
                "max": df["revenue"].max(),
                "median": df["revenue"].median()
            },
            "ebitda_distribution": {
                "mean": df["ebitda"].mean(),
                "std": df["ebitda"].std(),
                "min": df["ebitda"].min(),
                "max": df["ebitda"].max(),
                "median": df["ebitda"].median()
            },
            "equity_value_distribution": {
                "mean": df["equity_value"].mean(),
                "std": df["equity_value"].std(),
                "min": df["equity_value"].min(),
                "max": df["equity_value"].max(),
                "median": df["equity_value"].median()
            }
        }

        return patterns

    def _extract_valuation_method_patterns(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Extract valuation method patterns"""
        patterns = {}

        for method in df["valuation_method"].unique():
            subset = df[df["valuation_method"] == method]
            patterns[method] = {
                "count": len(subset),
                "avg_confidence": subset["confidence_score"].mean(),
                "avg_equity_value": subset["equity_value"].mean()
            }

        return patterns

    def _extract_temporal_patterns(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Extract temporal patterns"""
        patterns = {
            "monthly_distribution": df["created_at"].dt.month.value_counts().to_dict(),
            "yearly_distribution": df["created_at"].dt.year.value_counts().to_dict(),
            "recent_trend": {
                "last_6_months": len(df[df["created_at"] >= df["created_at"].max() - pd.Timedelta(days=180)]),
                "last_year": len(df[df["created_at"] >= df["created_at"].max() - pd.Timedelta(days=365)])
            }
        }

        return patterns

    def _extract_correlation_patterns(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Extract correlation patterns"""
        numerical_columns = df.select_dtypes(include=[np.number]).columns
        correlation_matrix = df[numerical_columns].corr()

        patterns = {
            "correlation_matrix": correlation_matrix.to_dict(),
            "strong_correlations": correlation_matrix[abs(correlation_matrix) > 0.7].to_dict(),
            "weak_correlations": correlation_matrix[abs(correlation_matrix) < 0.3].to_dict()
        }

        return patterns

    def _prepare_training_data_fallback(
        self,
        valuations: List[ValuationData],
        target_column: str
    ) -> Tuple[np.ndarray, np.ndarray, List[str]]:
        """Fallback feature engineering without pandas"""
        features = []
        targets = []
        feature_names = []

        for valuation in valuations:
            feature_vector = [
                valuation.revenue,
                valuation.ebitda,
                valuation.equity_value,
                valuation.confidence_score,
                hash(valuation.business_type) % 1000,  # Simple encoding
                hash(valuation.industry) % 1000,
                hash(valuation.valuation_method) % 1000
            ]

            features.append(feature_vector)

            if target_column == "equity_value":
                targets.append(valuation.equity_value)
            elif target_column == "revenue":
                targets.append(valuation.revenue)
            elif target_column == "ebitda":
                targets.append(valuation.ebitda)
            else:
                targets.append(valuation.equity_value)

        feature_names = [
            "revenue", "ebitda", "equity_value", "confidence_score",
            "business_type_encoded", "industry_encoded", "valuation_method_encoded"
        ]

        return np.array(features), np.array(targets), feature_names

    def _extract_pattern_features_fallback(self, valuations: List[ValuationData]) -> Dict[str, Any]:
        """Fallback pattern feature extraction without pandas"""
        patterns = {
            "business_type_patterns": {},
            "industry_patterns": {},
            "financial_patterns": {},
            "valuation_method_patterns": {}
        }

        # Simple pattern extraction
        business_types = {}
        industries = {}
        methods = {}

        for valuation in valuations:
            # Business type patterns
            if valuation.business_type not in business_types:
                business_types[valuation.business_type] = []
            business_types[valuation.business_type].append(valuation.equity_value)

            # Industry patterns
            if valuation.industry not in industries:
                industries[valuation.industry] = []
            industries[valuation.industry].append(valuation.equity_value)

            # Method patterns
            if valuation.valuation_method not in methods:
                methods[valuation.valuation_method] = []
            methods[valuation.valuation_method].append(valuation.equity_value)

        # Calculate averages
        for business_type, values in business_types.items():
            patterns["business_type_patterns"][business_type] = {
                "count": len(values),
                "avg_equity_value": sum(values) / len(values)
            }

        for industry, values in industries.items():
            patterns["industry_patterns"][industry] = {
                "count": len(values),
                "avg_equity_value": sum(values) / len(values)
            }

        for method, values in methods.items():
            patterns["valuation_method_patterns"][method] = {
                "count": len(values),
                "avg_equity_value": sum(values) / len(values)
            }

        return patterns
