from src.utils.exceptions import DataValidationError, MissingDataError

"""
Data Aggregator

This module handles data collection and aggregation from conversations
for report generation, including extraction, parsing, and validation.
"""

import re
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from src.utils.logging import get_logger
from decimal import Decimal
from src.utils.decimal_helpers import to_decimal, from_decimal
from .report_types import (
    DataExtractionResult, ReportConfiguration, DEFAULT_REPORT_CONFIG
)

logger = get_logger(__name__)


class DataAggregator:
    """
    Data aggregation service for conversation report generation

    Handles:
    - Extract key information from conversations
    - Parse financial values
    - Calculate key metrics
    - Aggregate conversation data
    - Data validation and normalization
    """

    def __init__(self, config: Optional[ReportConfiguration] = None):
        """Initialize the data aggregator"""
        self.logger = logger
        self.config = config or DEFAULT_REPORT_CONFIG

        self.logger.info("DataAggregator initialized")

    def extract_key_information(
        self,
        conversation_data: Dict[str, Any],
        collected_data: Dict[str, Any]
    ) -> DataExtractionResult:
        """
        Extract key information from conversation and collected data

        Args:
            conversation_data: Raw conversation data
            collected_data: Collected data from conversation

        Returns:
            DataExtractionResult with extracted information
        """
        try:
            self.logger.info("Extracting key information from conversation")

            # Extract basic company information
            company_name = self._extract_company_name(collected_data, conversation_data)
            revenue = self._parse_financial_value(collected_data.get("revenue"))
            ebitda = self._parse_financial_value(collected_data.get("ebitda"))
            industry = self._extract_industry(collected_data, conversation_data)
            business_type = self._extract_business_type(collected_data, conversation_data)
            employee_count = self._extract_employee_count(collected_data, conversation_data)

            # Extract key metrics
            key_metrics = self._extract_key_metrics(collected_data, conversation_data)

            # Calculate confidence and completeness
            confidence = self._calculate_extraction_confidence(
                revenue, ebitda, industry, business_type
            )
            completeness_score = self._calculate_completeness_score(
                revenue, ebitda, industry, business_type, employee_count
            )
            missing_fields = self._identify_missing_fields(
                revenue, ebitda, industry, business_type, employee_count
            )

            result = DataExtractionResult(
                company_name=company_name,
                revenue=revenue,
                ebitda=ebitda,
                industry=industry,
                business_type=business_type,
                employee_count=employee_count,
                key_metrics=key_metrics,
                confidence=confidence,
                completeness_score=completeness_score,
                missing_fields=missing_fields
            )

            self.logger.info(
                "Key information extracted",
                company_name=company_name,
                revenue=revenue,
                ebitda=ebitda,
                industry=industry,
                confidence=f"{confidence:.2%}",
                completeness=f"{completeness_score:.2%}"
            )

            return result

        except ValuationEngineError as e:
            self.logger.error(f"Key information extraction failed: {e}")
            raise

    def parse_financial_value(self, value: Any) -> Optional[Decimal]:
        """
        Parse financial value from various formats

        Args:
            value: Financial value in various formats

        Returns:
            Parsed float value or None if parsing fails
        """
        try:
            if value is None:
                return None

            if isinstance(value, (int, float)):
                return to_decimal(value)

            if isinstance(value, str):
                # Remove common currency symbols and formatting
                cleaned = re.sub(r'[€$£¥,\s]', '', value)

                # Handle different number formats
                if 'k' in cleaned.lower() or 'thousand' in cleaned.lower():
                    cleaned = cleaned.lower().replace('k', '').replace('thousand', '')
                    return to_decimal(cleaned) * 1000
                elif 'm' in cleaned.lower() or 'million' in cleaned.lower():
                    cleaned = cleaned.lower().replace('m', '').replace('million', '')
                    return to_decimal(cleaned) * 1000000
                elif 'b' in cleaned.lower() or 'billion' in cleaned.lower():
                    cleaned = cleaned.lower().replace('b', '').replace('billion', '')
                    return to_decimal(cleaned) * 1000000000
                else:
                    return to_decimal(cleaned)

            return None

        except (ValueError, TypeError) as e:
            self.logger.warning(f"Failed to parse financial value '{value}': {e}")
            return None

    def extract_key_metrics(
        self,
        collected_data: Dict[str, Any],
        conversation_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Extract key business metrics from conversation data

        Args:
            collected_data: Collected data from conversation
            conversation_data: Raw conversation data

        Returns:
            Dictionary of key metrics
        """
        try:
            metrics = {}

            # Financial metrics
            metrics["revenue"] = self._parse_financial_value(collected_data.get("revenue"))
            metrics["ebitda"] = self._parse_financial_value(collected_data.get("ebitda"))
            metrics["profit_margin"] = self._calculate_profit_margin(
                metrics["revenue"], metrics["ebitda"]
            )
            metrics["revenue_growth"] = self._extract_growth_rate(collected_data, "revenue")

            # Operational metrics
            metrics["employee_count"] = self._extract_employee_count(collected_data, conversation_data)
            metrics["years_in_business"] = self._extract_years_in_business(collected_data)
            metrics["customer_count"] = self._extract_customer_count(collected_data)

            # Industry-specific metrics
            industry = self._extract_industry(collected_data, conversation_data)
            if industry:
                metrics["industry"] = industry
                metrics["industry_benchmarks"] = self._get_industry_benchmarks(industry)

            # Market metrics
            metrics["market_share"] = self._extract_market_share(collected_data)
            metrics["competitive_position"] = self._extract_competitive_position(collected_data)

            # Remove None values
            metrics = {k: v for k, v in metrics.items() if v is not None}

            return metrics

        except MissingDataError as e:
            self.logger.error(f"Key metrics extraction failed: {e}")
            return {}

    def summarize_conversation(self, conversation_data: Dict[str, Any]) -> str:
        """
        Summarize conversation data for report context

        Args:
            conversation_data: Raw conversation data

        Returns:
            Conversation summary string
        """
        try:
            # Extract key points from conversation
            key_points = []

            # Extract messages or turns
            messages = conversation_data.get("messages", [])
            if not messages:
                messages = conversation_data.get("turns", [])

            # Summarize key discussion points
            for message in messages[-10:]:  # Last 10 messages
                content = message.get("content", "") or message.get("text", "")
                if content and len(content) > 20:  # Meaningful content
                    key_points.append(content[:100] + "..." if len(content) > 100 else content)

            # Create summary
            if key_points:
                summary = f"Key discussion points: {'; '.join(key_points[:3])}"
            else:
                summary = "Conversation focused on business valuation and company information gathering."

            return summary

        except DataValidationError as e:
            self.logger.error(f"Conversation summarization failed: {e}")
            return "Conversation data processed for valuation analysis."

    def validate_data_completeness(
        self,
        extraction_result: DataExtractionResult
    ) -> Tuple[bool, List[str]]:
        """
        Validate data completeness for valuation

        Args:
            extraction_result: Data extraction result

        Returns:
            Tuple of (is_complete, missing_critical_fields)
        """
        try:
            critical_fields = ["revenue", "industry"]
            missing_critical = []

            # Check critical fields
            if extraction_result.revenue is None:
                missing_critical.append("revenue")
            if not extraction_result.industry or extraction_result.industry == "unknown":
                missing_critical.append("industry")

            is_complete = len(missing_critical) == 0

            return is_complete, missing_critical

        except DataValidationError as e:
            self.logger.error(f"Data completeness validation failed: {e}")
            return False, ["validation_error"]

    def _extract_company_name(
        self,
        collected_data: Dict[str, Any],
        conversation_data: Dict[str, Any]
    ) -> str:
        """Extract company name from data"""
        # Try collected data first
        company_name = collected_data.get("company_name")
        if company_name and company_name != "unknown":
            return company_name

        # Try conversation data
        company_name = conversation_data.get("company_name")
        if company_name and company_name != "unknown":
            return company_name

        return "Unknown Company"

    def _extract_industry(
        self,
        collected_data: Dict[str, Any],
        conversation_data: Dict[str, Any]
    ) -> str:
        """Extract industry from data"""
        industry = collected_data.get("industry")
        if industry and industry != "unknown":
            return industry

        industry = conversation_data.get("industry")
        if industry and industry != "unknown":
            return industry

        return "unknown"

    def _extract_business_type(
        self,
        collected_data: Dict[str, Any],
        conversation_data: Dict[str, Any]
    ) -> str:
        """Extract business type from data"""
        business_type = collected_data.get("business_type")
        if business_type and business_type != "unknown":
            return business_type

        business_type = conversation_data.get("business_type")
        if business_type and business_type != "unknown":
            return business_type

        return "unknown"

    def _extract_employee_count(
        self,
        collected_data: Dict[str, Any],
        conversation_data: Dict[str, Any]
    ) -> str:
        """Extract employee count from data"""
        employee_count = collected_data.get("employee_count")
        if employee_count and employee_count != "unknown":
            return str(employee_count)

        employee_count = conversation_data.get("employee_count")
        if employee_count and employee_count != "unknown":
            return str(employee_count)

        return "unknown"

    def _calculate_extraction_confidence(
        self,
        revenue: Optional[Decimal],
        ebitda: Optional[Decimal],
        industry: str,
        business_type: str
    ) -> Decimal:
        """Calculate confidence in extracted data"""
        confidence = Decimal('0.0')

        # Revenue confidence
        if revenue and revenue > 0:
            confidence += Decimal('0.4')

        # EBITDA confidence
        if ebitda and ebitda > 0:
            confidence += Decimal('0.3')

        # Industry confidence
        if industry and industry != "unknown":
            confidence += Decimal('0.2')

        # Business type confidence
        if business_type and business_type != "unknown":
            confidence += Decimal('0.1')

        return min(Decimal('1.0'), confidence)

    def _calculate_completeness_score(
        self,
        revenue: Optional[Decimal],
        ebitda: Optional[Decimal],
        industry: str,
        business_type: str,
        employee_count: str
    ) -> Decimal:
        """Calculate data completeness score"""
        total_fields = 5
        completed_fields = 0

        if revenue and revenue > 0:
            completed_fields += 1
        if ebitda and ebitda > 0:
            completed_fields += 1
        if industry and industry != "unknown":
            completed_fields += 1
        if business_type and business_type != "unknown":
            completed_fields += 1
        if employee_count and employee_count != "unknown":
            completed_fields += 1

        return completed_fields / total_fields

    def _identify_missing_fields(
        self,
        revenue: Optional[Decimal],
        ebitda: Optional[Decimal],
        industry: str,
        business_type: str,
        employee_count: str
    ) -> List[str]:
        """Identify missing fields"""
        missing = []

        if not revenue or revenue <= 0:
            missing.append("revenue")
        if not ebitda or ebitda <= 0:
            missing.append("ebitda")
        if not industry or industry == "unknown":
            missing.append("industry")
        if not business_type or business_type == "unknown":
            missing.append("business_type")
        if not employee_count or employee_count == "unknown":
            missing.append("employee_count")

        return missing

    def _calculate_profit_margin(
        self,
        revenue: Optional[Decimal],
        ebitda: Optional[Decimal]
    ) -> Optional[Decimal]:
        """Calculate profit margin"""
        if revenue and ebitda and revenue > 0:
            return (ebitda / revenue) * 100
        return None

    def _extract_growth_rate(self, collected_data: Dict[str, Any], metric: str) -> Optional[Decimal]:
        """Extract growth rate for a metric"""
        growth_key = f"{metric}_growth"
        growth_value = collected_data.get(growth_key)

        if growth_value:
            return self.parse_financial_value(growth_value)

        return None

    def _extract_years_in_business(self, collected_data: Dict[str, Any]) -> Optional[int]:
        """Extract years in business"""
        years = collected_data.get("years_in_business")
        if years:
            try:
                return int(years)
            except (ValueError, TypeError):
                pass
        return None

    def _extract_customer_count(self, collected_data: Dict[str, Any]) -> Optional[int]:
        """Extract customer count"""
        customers = collected_data.get("customer_count")
        if customers:
            try:
                return int(customers)
            except (ValueError, TypeError):
                pass
        return None

    def _get_industry_benchmarks(self, industry: str) -> Dict[str, Any]:
        """Get industry benchmarks"""
        # Simplified industry benchmarks
        benchmarks = {
            "technology": {"revenue_multiple": Decimal('3.2'), "ebitda_multiple": 11.0},
            "services": {"revenue_multiple": Decimal('2.7'), "ebitda_multiple": 9.0},
            "manufacturing": {"revenue_multiple": Decimal('2.0'), "ebitda_multiple": 6.0},
            "retail": {"revenue_multiple": Decimal('1.5'), "ebitda_multiple": 4.5},
            "healthcare": {"revenue_multiple": Decimal('2.8'), "ebitda_multiple": 9.0},
            "construction": {"revenue_multiple": Decimal('1.6'), "ebitda_multiple": 4.5},
            "hospitality": {"revenue_multiple": Decimal('1.4'), "ebitda_multiple": 4.0}
        }

        return benchmarks.get(industry, {})

    def _extract_market_share(self, collected_data: Dict[str, Any]) -> Optional[Decimal]:
        """Extract market share"""
        market_share = collected_data.get("market_share")
        if market_share:
            return self.parse_financial_value(market_share)
        return None

    def _extract_competitive_position(self, collected_data: Dict[str, Any]) -> Optional[str]:
        """Extract competitive position"""
        return collected_data.get("competitive_position")
