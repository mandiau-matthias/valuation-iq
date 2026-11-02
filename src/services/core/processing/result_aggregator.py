from src.utils.exceptions import MethodologyError

"""
Result Aggregator

This module handles multi-methodology result aggregation, weighted averaging,
confidence scoring, and outlier detection for valuation results.
"""

from typing import Dict, Any, List, Optional, Tuple
from decimal import Decimal
from src.utils.logging import get_logger
from src.utils.decimal_helpers import to_decimal, from_decimal
from ..orchestration.orchestrator_types import (
    ValuationResult, AggregationWeights, DEFAULT_AGGREGATION_WEIGHTS,
    ValuationMethodology
)

logger = get_logger(__name__)


class ResultAggregator:
    """
    Result aggregation service for valuation processing

    Handles:
    - Multi-methodology result aggregation
    - Weighted averaging
    - Confidence scoring
    - Outlier detection
    """

    def __init__(self, weights: Optional[AggregationWeights] = None):
        """Initialize the result aggregator"""
        self.logger = logger
        self.weights = weights or DEFAULT_AGGREGATION_WEIGHTS

        self.logger.info("ResultAggregator initialized")

    def aggregate_valuations(
        self,
        dcf_result: Optional[Dict[str, Any]],
        multiples_result: Optional[Dict[str, Any]],
        context: Optional[Dict[str, Any]] = None
    ) -> ValuationResult:
        """
        Aggregate multiple valuation results

        Args:
            dcf_result: DCF valuation result
            multiples_result: Multiples valuation result
            context: Additional context

        Returns:
            Aggregated valuation result
        """
        try:
            self.logger.info("Aggregating valuation results")

            # Extract equity values
            dcf_equity_decimal = to_decimal(dcf_result.get('equity_value', 0)) if dcf_result else Decimal('0')
            multiples_equity_decimal = to_decimal(multiples_result.get('equity_value', 0)) if multiples_result else Decimal('0')

            # Calculate weighted average
            if dcf_result and multiples_result:
                dcf_weight_decimal = to_decimal(self.weights.dcf_weight) if hasattr(self.weights, 'dcf_weight') else Decimal('0.5')
                multiples_weight_decimal = to_decimal(self.weights.multiples_weight) if hasattr(self.weights, 'multiples_weight') else Decimal('0.5')
                equity_value_decimal = (
                    dcf_equity_decimal * dcf_weight_decimal +
                    multiples_equity_decimal * multiples_weight_decimal
                )
                equity_value = from_decimal(equity_value_decimal)
                methodology = ValuationMethodology.HYBRID.value
                confidence_base_decimal = Decimal('0.85')
            elif dcf_result:
                equity_value = from_decimal(dcf_equity_decimal)
                methodology = ValuationMethodology.DCF.value
                confidence_base_decimal = Decimal('0.75')
            elif multiples_result:
                equity_value = from_decimal(multiples_equity_decimal)
                methodology = ValuationMethodology.MULTIPLES.value
                confidence_base_decimal = Decimal('0.70')
            else:
                raise ValueError("No valuation results provided")

            # Calculate enterprise value
            enterprise_value = self._calculate_enterprise_value(equity_value, dcf_result, multiples_result)

            # Aggregate value drivers and risk factors
            value_drivers = self._aggregate_value_drivers(dcf_result, multiples_result)
            risk_factors = self._aggregate_risk_factors(dcf_result, multiples_result)

            # Calculate confidence score
            confidence_score = self._calculate_confidence_score(
                dcf_result, multiples_result, from_decimal(confidence_base_decimal)
            )

            # Aggregate sensitivity analysis
            sensitivity_analysis = self._aggregate_sensitivity_analysis(dcf_result, multiples_result)

            # Aggregate market comparables
            market_comparables = self._aggregate_market_comparables(dcf_result, multiples_result)

            # Aggregate financial metrics
            financial_metrics = self._aggregate_financial_metrics(dcf_result, multiples_result)

            result = ValuationResult(
                equity_value=equity_value,
                enterprise_value=enterprise_value,
                valuation_methodology=methodology,
                confidence_score=confidence_score,
                value_drivers=value_drivers,
                risk_factors=risk_factors,
                sensitivity_analysis=sensitivity_analysis,
                market_comparables=market_comparables,
                financial_metrics=financial_metrics
            )

            self.logger.info(
                "Valuation aggregation completed",
                equity_value=equity_value,
                methodology=methodology,
                confidence=confidence_score
            )

            return result

        except MethodologyError as e:
            self.logger.error(f"Valuation aggregation failed: {e}")
            raise

    def detect_outliers(
        self,
        values: List[Decimal],
        threshold: Decimal = Decimal('2.0')
    ) -> List[int]:
        """
        Detect outliers in valuation results

        Args:
            values: List of valuation values
            threshold: Standard deviation threshold

        Returns:
            List of outlier indices
        """
        if len(values) < 3:
            return []

        # Convert to Decimal for precision
        values_decimal = [to_decimal(v) for v in values]
        threshold_decimal = to_decimal(threshold)
        count_decimal = Decimal(str(len(values_decimal)))

        # Calculate mean and standard deviation
        mean_decimal = sum(values_decimal) / count_decimal
        variance_decimal = sum((x - mean_decimal) ** Decimal('2') for x in values_decimal) / count_decimal
        std_dev_decimal = variance_decimal ** Decimal('0.5')

        # Identify outliers
        outliers = []
        for i, value_decimal in enumerate(values_decimal):
            if std_dev_decimal > Decimal('0'):
                z_score_decimal = abs((value_decimal - mean_decimal) / std_dev_decimal)
            else:
                z_score_decimal = Decimal('0')
            if z_score_decimal > threshold_decimal:
                outliers.append(i)

        return outliers

    def _calculate_enterprise_value(
        self,
        equity_value: Decimal,
        dcf_result: Optional[Dict[str, Any]],
        multiples_result: Optional[Dict[str, Any]]
    ) -> Decimal:
        """Calculate enterprise value"""
        # Try to get from results
        if dcf_result and 'enterprise_value' in dcf_result:
            return from_decimal(to_decimal(dcf_result['enterprise_value']))
        elif multiples_result and 'enterprise_value' in multiples_result:
            return from_decimal(to_decimal(multiples_result['enterprise_value']))

        # Estimate from equity value (simplified)
        equity_value_decimal = to_decimal(equity_value)
        return from_decimal(equity_value_decimal * Decimal('1.1'))

    def _aggregate_value_drivers(
        self,
        dcf_result: Optional[Dict[str, Any]],
        multiples_result: Optional[Dict[str, Any]]
    ) -> List[str]:
        """Aggregate value drivers from multiple results"""
        drivers = []

        if dcf_result and 'value_drivers' in dcf_result:
            drivers.extend(dcf_result['value_drivers'])

        if multiples_result and 'value_drivers' in multiples_result:
            drivers.extend(multiples_result['value_drivers'])

        # Remove duplicates while preserving order
        return list(dict.fromkeys(drivers))

    def _aggregate_risk_factors(
        self,
        dcf_result: Optional[Dict[str, Any]],
        multiples_result: Optional[Dict[str, Any]]
    ) -> List[str]:
        """Aggregate risk factors from multiple results"""
        risks = []

        if dcf_result and 'risk_factors' in dcf_result:
            risks.extend(dcf_result['risk_factors'])

        if multiples_result and 'risk_factors' in multiples_result:
            risks.extend(multiples_result['risk_factors'])

        # Remove duplicates while preserving order
        return list(dict.fromkeys(risks))

    def _calculate_confidence_score(
        self,
        dcf_result: Optional[Dict[str, Any]],
        multiples_result: Optional[Dict[str, Any]],
        base_confidence: Decimal
    ) -> Decimal:
        """Calculate overall confidence score"""
        confidence_decimal = to_decimal(base_confidence)

        # Adjust based on data quality
        if dcf_result and 'data_quality' in dcf_result:
            data_quality_decimal = to_decimal(dcf_result['data_quality'])
            confidence_decimal *= data_quality_decimal

        if multiples_result and 'data_quality' in multiples_result:
            data_quality_decimal = to_decimal(multiples_result['data_quality'])
            confidence_decimal *= data_quality_decimal

        # Apply confidence adjustment
        confidence_adjustment_decimal = to_decimal(self.weights.confidence_adjustment) if hasattr(self.weights, 'confidence_adjustment') else Decimal('1.0')
        confidence_decimal *= confidence_adjustment_decimal

        # Ensure within bounds
        return from_decimal(max(Decimal('0.1'), min(Decimal('1.0'), confidence_decimal)))

    def _aggregate_sensitivity_analysis(
        self,
        dcf_result: Optional[Dict[str, Any]],
        multiples_result: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Aggregate sensitivity analysis"""
        sensitivity = {}

        if dcf_result and 'sensitivity_analysis' in dcf_result:
            sensitivity.update(dcf_result['sensitivity_analysis'])

        if multiples_result and 'sensitivity_analysis' in multiples_result:
            sensitivity.update(multiples_result['sensitivity_analysis'])

        return sensitivity

    def _aggregate_market_comparables(
        self,
        dcf_result: Optional[Dict[str, Any]],
        multiples_result: Optional[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Aggregate market comparables"""
        comparables = []

        if multiples_result and 'market_comparables' in multiples_result:
            comparables.extend(multiples_result['market_comparables'])

        return comparables

    def _aggregate_financial_metrics(
        self,
        dcf_result: Optional[Dict[str, Any]],
        multiples_result: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Aggregate financial metrics"""
        metrics = {}

        if dcf_result and 'financial_metrics' in dcf_result:
            metrics.update(dcf_result['financial_metrics'])

        if multiples_result and 'financial_metrics' in multiples_result:
            metrics.update(multiples_result['financial_metrics'])

        return metrics
