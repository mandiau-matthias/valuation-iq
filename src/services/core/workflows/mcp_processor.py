from src.utils.exceptions import DataQualityError, MultiplesCalculationError

"""
MCP Processor

This module handles data processing, feature engineering, and pattern analysis
for the Valuation MCP Service refactoring.
"""

from typing import Dict, Any, List, Optional, Union
from decimal import Decimal
from datetime import datetime, timedelta
import numpy as np

from src.utils.logging import get_logger
from src.utils.decimal_helpers import to_decimal, from_decimal
from .mcp_types import (
    ProcessedValuationRecord, IndustryPattern, SeasonalPattern,
    ValuationBenchmark, QualityInsight, MCPInsights, TrendDirection,
    ValuationCategory, GrowthCategory, VALUATION_THRESHOLDS, GROWTH_THRESHOLDS,
    QUALITY_WEIGHTS
)

# Pandas for data processing (with fallback)
try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False

logger = get_logger(__name__)


class MCPProcessor:
    """
    MCP Processor for data processing and analysis

    Handles:
    - Feature engineering
    - Pattern analysis
    - Statistical calculations
    - Trend analysis
    """

    def __init__(self):
        """Initialize MCP processor"""
        self.logger = logger
        self.logger.info("MCPProcessor initialized")

    def process_valuation_features(self, df: "pd.DataFrame") -> "pd.DataFrame":
        """
        Process valuation features and engineering

        Args:
            df: Raw valuation data

        Returns:
            DataFrame with engineered features
        """
        self.logger.info("Processing valuation features",
                        records=len(df) if df is not None else 0)

        if not PANDAS_AVAILABLE or df is None or df.empty:
            self.logger.warning("Pandas not available or empty data")
            return df

        try:
            processed_df = df.copy()

            # 1. Calculate valuation multiples
            processed_df['revenue_multiple'] = (
                processed_df['equity_value_mid'] / processed_df['revenue'].replace(0, np.nan)
            )
            processed_df['ebitda_multiple'] = (
                processed_df['equity_value_mid'] / processed_df['ebitda'].replace(0, np.nan)
            )

            # 2. Calculate financial ratios
            processed_df['ebitda_margin'] = (
                processed_df['ebitda'] / processed_df['revenue'].replace(0, np.nan)
            )
            processed_df['debt_to_equity'] = (
                processed_df['total_debt'] / 
                (processed_df['equity_value_mid'] - processed_df['total_debt']).replace(0, np.nan)
            )

            # 3. Categorize valuations by size
            processed_df['valuation_category'] = pd.cut(
                processed_df['equity_value_mid'],
                bins=[0, VALUATION_THRESHOLDS['micro'], VALUATION_THRESHOLDS['small'], 
                      VALUATION_THRESHOLDS['medium'], VALUATION_THRESHOLDS['large']],
                labels=['micro', 'small', 'medium', 'large']
            )

            # 4. Time-based features
            processed_df['created_at'] = pd.to_datetime(processed_df['created_at'])
            processed_df['year'] = processed_df['created_at'].dt.year
            processed_df['quarter'] = processed_df['created_at'].dt.quarter
            processed_df['month'] = processed_df['created_at'].dt.month

            # 5. Growth indicators
            if 'revenue_growth_rate' in processed_df.columns:
                processed_df['growth_category'] = pd.cut(
                    processed_df['revenue_growth_rate'],
                    bins=[GROWTH_THRESHOLDS['declining'], GROWTH_THRESHOLDS['stable'],
                          GROWTH_THRESHOLDS['growing'], GROWTH_THRESHOLDS['high_growth']],
                    labels=['declining', 'stable', 'growing', 'high_growth']
                )

            # 6. Quality scoring
            processed_df['data_quality_score'] = 0
            processed_df.loc[processed_df['confidence_score'] >= 80, 'data_quality_score'] += QUALITY_WEIGHTS['confidence_high']
            processed_df.loc[processed_df['confidence_score'] >= 70, 'data_quality_score'] += QUALITY_WEIGHTS['confidence_medium']
            processed_df.loc[processed_df['total_assets'].notna(), 'data_quality_score'] += QUALITY_WEIGHTS['assets_available']
            processed_df.loc[processed_df['employees'].notna(), 'data_quality_score'] += QUALITY_WEIGHTS['employees_available']

            # 7. Premium exit identification (top 20% of multiples per industry)
            for industry in processed_df['industry'].unique():
                industry_mask = processed_df['industry'] == industry
                threshold = processed_df.loc[industry_mask, 'revenue_multiple'].quantile(Decimal('0.8'))
                processed_df.loc[
                    industry_mask & (processed_df['revenue_multiple'] > threshold),
                    'is_premium_exit'
                ] = True

            processed_df['is_premium_exit'] = processed_df['is_premium_exit'].fillna(False)

            # 8. Industry performance ranks
            processed_df['industry_performance_rank'] = (
                processed_df.groupby('industry')['revenue_multiple']
                .rank(pct=True, method='average')
            )

            self.logger.info("Feature engineering complete",
                           records=len(processed_df),
                           industries=processed_df['industry'].nunique(),
                           premium_exits=processed_df['is_premium_exit'].sum(),
                           avg_multiple=processed_df['revenue_multiple'].mean())

            return processed_df

        except MultiplesCalculationError as e:
            self.logger.error(f"Feature processing failed: {e}")
            return df

    def analyze_valuation_patterns(
        self,
        df: "pd.DataFrame",
        current_industry: Optional[str] = None
    ) -> MCPInsights:
        """
        Analyze valuation patterns

        Args:
            df: Processed valuation data
            current_industry: Focus industry for targeted insights

        Returns:
            MCP insights with pattern analysis
        """
        self.logger.info("Analyzing valuation patterns",
                        records=len(df) if df is not None else 0,
                        current_industry=current_industry)

        if not PANDAS_AVAILABLE or df is None or df.empty:
            return MCPInsights(
                data_summary={"total_valuations": 0, "status": "no_data"},
                industry_patterns={},
                seasonal_patterns={},
                valuation_benchmarks={},
                quality_insights=QualityInsight(0, 0, 0, Decimal('0.0'), Decimal('0.0')),
                trend_analysis={}
            )

        try:
            # Data summary
            data_summary = {
                "total_valuations": len(df),
                "date_range": {
                    "start": df['created_at'].min().isoformat() if not df.empty else None,
                    "end": df['created_at'].max().isoformat() if not df.empty else None
                },
                "industries_covered": df['industry'].nunique(),
                "avg_confidence_score": to_decimal(df['confidence_score'].mean())
            }

            # Industry patterns
            industry_patterns = self._analyze_industry_patterns(df)

            # Seasonal patterns
            seasonal_patterns = self._analyze_seasonal_patterns(df)

            # Valuation benchmarks
            valuation_benchmarks = self._analyze_valuation_benchmarks(df)

            # Quality insights
            quality_insights = self._analyze_quality_insights(df)

            # Trend analysis
            trend_analysis = self._analyze_trends(df)

            insights = MCPInsights(
                data_summary=data_summary,
                industry_patterns=industry_patterns,
                seasonal_patterns=seasonal_patterns,
                valuation_benchmarks=valuation_benchmarks,
                quality_insights=quality_insights,
                trend_analysis=trend_analysis
            )

            self.logger.info("Pattern analysis complete",
                           industries=len(industry_patterns),
                           seasonal_quarters=len(seasonal_patterns))

            return insights

        except MultiplesCalculationError as e:
            self.logger.error(f"Pattern analysis failed: {e}")
            return MCPInsights(
                data_summary={"total_valuations": 0, "status": "error", "error": str(e)},
                industry_patterns={},
                seasonal_patterns={},
                valuation_benchmarks={},
                quality_insights=QualityInsight(0, 0, 0, Decimal('0.0'), Decimal('0.0')),
                trend_analysis={}
            )

    def _analyze_industry_patterns(self, df: "pd.DataFrame") -> Dict[str, IndustryPattern]:
        """Analyze industry-specific patterns"""
        try:
            industry_stats = df.groupby('industry').agg({
                'revenue_multiple': ['median', 'mean', 'std', 'count'],
                'ebitda_multiple': ['median', 'mean'],
                'ebitda_margin': 'median',
                'is_premium_exit': 'sum'
            }).round(2)

            patterns = {}
            for industry, row in industry_stats.iterrows():
                patterns[industry] = IndustryPattern(
                    industry=industry,
                    median_revenue_multiple=to_decimal(row['revenue_multiple']['median']),
                    mean_revenue_multiple=to_decimal(row['revenue_multiple']['mean']),
                    std_revenue_multiple=to_decimal(row['revenue_multiple']['std']),
                    sample_size=int(row['revenue_multiple']['count']),
                    median_ebitda_multiple=to_decimal(row['ebitda_multiple']['median']),
                    median_ebitda_margin=to_decimal(row['ebitda_margin']['median']),
                    premium_exits=int(row['is_premium_exit']['sum'])
                )

            return patterns

        except MultiplesCalculationError as e:
            self.logger.error(f"Industry pattern analysis failed: {e}")
            return {}

    def _analyze_seasonal_patterns(self, df: "pd.DataFrame") -> Dict[str, SeasonalPattern]:
        """Analyze seasonal patterns"""
        try:
            seasonal_stats = df.groupby('quarter').agg({
                'revenue_multiple': 'mean',
                'confidence_score': 'mean'
            }).round(2)

            annual_avg = df['revenue_multiple'].mean()
            patterns = {}

            for quarter, row in seasonal_stats.iterrows():
                # Convert to Decimal for precision in percentage calculation
                row_multiple_decimal = to_decimal(row['revenue_multiple'])
                annual_avg_decimal = to_decimal(annual_avg)
                if annual_avg_decimal > Decimal('0'):
                    premium_vs_annual_decimal = ((row_multiple_decimal / annual_avg_decimal) - Decimal('1')) * Decimal('100')
                else:
                    premium_vs_annual_decimal = Decimal('0')
                
                patterns[f"Q{quarter}"] = SeasonalPattern(
                    quarter=f"Q{quarter}",
                    avg_multiple=to_decimal(row['revenue_multiple']),
                    premium_vs_annual=from_decimal(premium_vs_annual_decimal),
                    avg_confidence=to_decimal(row['confidence_score'])
                )

            return patterns

        except MultiplesCalculationError as e:
            self.logger.error(f"Seasonal pattern analysis failed: {e}")
            return {}

    def _analyze_valuation_benchmarks(self, df: "pd.DataFrame") -> Dict[str, ValuationBenchmark]:
        """Analyze valuation benchmarks by size"""
        try:
            size_benchmarks = df.groupby('valuation_category').agg({
                'revenue_multiple': ['median', 'quantile'],
                'ebitda_multiple': 'median',
                'confidence_score': 'mean'
            }).round(2)

            benchmarks = {}
            for category, row in size_benchmarks.iterrows():
                benchmarks[str(category)] = ValuationBenchmark(
                    category=str(category),
                    median_revenue_multiple=to_decimal(row['revenue_multiple']['median']),
                    median_ebitda_multiple=to_decimal(row['ebitda_multiple']['median']),
                    avg_confidence=to_decimal(row['confidence_score']['mean']),
                    sample_size=len(df[df['valuation_category'] == category])
                )

            return benchmarks

        except MultiplesCalculationError as e:
            self.logger.error(f"Valuation benchmark analysis failed: {e}")
            return {}

    def _analyze_quality_insights(self, df: "pd.DataFrame") -> QualityInsight:
        """Analyze data quality insights"""
        try:
            high_quality = len(df[df['data_quality_score'] >= 80])
            medium_quality = len(df[(df['data_quality_score'] >= 50) & (df['data_quality_score'] < 80)])
            low_quality = len(df[df['data_quality_score'] < 50])

            avg_confidence = df['confidence_score'].mean()
            completeness_score = df['data_quality_score'].mean()

            return QualityInsight(
                high_quality_count=high_quality,
                medium_quality_count=medium_quality,
                low_quality_count=low_quality,
                avg_confidence=to_decimal(avg_confidence),
                completeness_score=to_decimal(completeness_score)
            )

        except DataQualityError as e:
            self.logger.error(f"Quality insight analysis failed: {e}")
            return QualityInsight(0, 0, 0, Decimal('0.0'), Decimal('0.0'))

    def _analyze_trends(self, df: "pd.DataFrame") -> Dict[str, Any]:
        """Analyze valuation trends over time"""
        try:
            # Recent vs older data comparison
            recent_cutoff = df['created_at'].quantile(Decimal('0.7'))
            recent_data = df[df['created_at'] >= recent_cutoff]
            older_data = df[df['created_at'] < recent_cutoff]

            if len(recent_data) > 0 and len(older_data) > 0:
                recent_avg = recent_data['revenue_multiple'].mean()
                older_avg = older_data['revenue_multiple'].mean()

                # Convert to Decimal for precision in percentage calculation
                recent_avg_decimal = to_decimal(recent_avg)
                older_avg_decimal = to_decimal(older_avg)
                if older_avg_decimal > Decimal('0'):
                    change_decimal = ((recent_avg_decimal / older_avg_decimal) - Decimal('1')) * Decimal('100')
                else:
                    change_decimal = Decimal('0')
                change = from_decimal(change_decimal)

                if change > 10:
                    trend_direction = TrendDirection.STRONGLY_INCREASING
                elif change > 3:
                    trend_direction = TrendDirection.INCREASING
                elif change < -10:
                    trend_direction = TrendDirection.STRONGLY_DECREASING
                elif change < -3:
                    trend_direction = TrendDirection.DECREASING
                else:
                    trend_direction = TrendDirection.STABLE

                return {
                    "trend_direction": trend_direction.value,
                    "change_percentage": change,
                    "recent_avg_multiple": to_decimal(recent_avg),
                    "older_avg_multiple": to_decimal(older_avg),
                    "recent_sample_size": len(recent_data),
                    "older_sample_size": len(older_data)
                }
            else:
                return {"trend_direction": "insufficient_data"}

        except MultiplesCalculationError as e:
            self.logger.error(f"Trend analysis failed: {e}")
            return {"trend_direction": "error", "error": str(e)}

    def get_processor_status(self) -> Dict[str, Any]:
        """Get processor status"""
        return {
            "pandas_available": PANDAS_AVAILABLE,
            "processor_ready": True,
            "last_updated": datetime.utcnow().isoformat()
        }
