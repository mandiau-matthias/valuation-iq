from src.utils.exceptions import ConfigurationError

"""
Generic external-service cost monitoring.

ValuationIQ no longer owns provider-model usage; Titan tracks model spend.
This helper remains for non-model service budgets and legacy callers.
"""

import logging
from decimal import Decimal
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
import asyncio
from src.utils.decimal_helpers import to_decimal, from_decimal

logger = logging.getLogger(__name__)

class CostMonitor:
    """
    Monitor generic external service costs and usage.
    """

    def __init__(self):
        self.daily_limit = Decimal('50.0')  # $50/day for MVP
        self.alert_threshold = Decimal('0.8')  # Alert at 80%
        self.usage_data: Dict[str, Any] = {}
        self.alerts_sent: Dict[str, bool] = {}

        logger.info("✅ CostMonitor initialized", extra={
                   'daily_limit': from_decimal(self.daily_limit),
                   'alert_threshold': from_decimal(self.alert_threshold)
        })

    async def track_usage(self, session_id: str, cost: Decimal, tokens_used: int = 0) -> Dict[str, Any]:
        """
        Track API usage and costs

        Args:
            session_id: Unique session identifier
            cost: Cost in USD for this request
            tokens_used: Number of tokens used

        Returns:
            Dict with usage summary and alerts
        """
        try:
            current_date = datetime.now().strftime("%Y-%m-%d")

            # Initialize daily tracking if not exists
            if current_date not in self.usage_data:
                self.usage_data[current_date] = {
                    "total_cost": Decimal('0.0'),
                    "total_tokens": 0,
                    "request_count": 0,
                    "sessions": set()
                }

            # Update usage data using Decimal
            cost_decimal = to_decimal(cost)
            self.usage_data[current_date]["total_cost"] += cost_decimal
            self.usage_data[current_date]["total_tokens"] += tokens_used
            self.usage_data[current_date]["request_count"] += 1
            self.usage_data[current_date]["sessions"].add(session_id)

            # Check if we need to send alerts using Decimal
            total_cost_decimal = self.usage_data[current_date]["total_cost"]
            usage_percentage_decimal = (total_cost_decimal / self.daily_limit) * Decimal('100')
            usage_percentage = from_decimal(usage_percentage_decimal)
            total_cost = from_decimal(total_cost_decimal)

            alerts = []

            # Check for daily limit alert using Decimal
            alert_threshold_pct_decimal = self.alert_threshold * Decimal('100')
            if usage_percentage_decimal >= alert_threshold_pct_decimal:
                alert_key = f"daily_limit_{current_date}"
                if not self.alerts_sent.get(alert_key, False):
                    daily_limit_float = from_decimal(self.daily_limit)
                    alerts.append({
                        "type": "daily_limit_warning",
                        "message": f"Daily cost limit warning: ${total_cost:.2f} / ${daily_limit_float} ({usage_percentage:.1f}%)",
                        "severity": "high" if usage_percentage >= 90 else "medium"
                    })
                    self.alerts_sent[alert_key] = True

            # Check for limit exceeded using Decimal
            if total_cost_decimal >= self.daily_limit:
                alert_key = f"daily_limit_exceeded_{current_date}"
                if not self.alerts_sent.get(alert_key, False):
                    daily_limit_float = from_decimal(self.daily_limit)
                    alerts.append({
                        "type": "daily_limit_exceeded",
                        "message": f"Daily cost limit exceeded: ${total_cost:.2f} / ${daily_limit_float}",
                        "severity": "critical"
                    })
                    self.alerts_sent[alert_key] = True

            logger.info(
                "Cost tracking updated",
                extra={
                    'session_id': session_id,
                    'cost': cost,
                    'total_cost': total_cost,
                    'usage_percentage': usage_percentage,
                    'alerts_count': len(alerts)
                }
            )

            return {
                "session_id": session_id,
                "cost": cost,
                "total_cost": total_cost,
                "usage_percentage": usage_percentage,
                "alerts": alerts,
                "status": "ok" if total_cost_decimal < self.daily_limit else "limit_exceeded"
            }

        except Exception as e:
            logger.error("Error tracking usage", extra={'error': str(e), 'session_id': session_id})
            return {
                "session_id": session_id,
                "cost": cost,
                "error": str(e),
                "status": "error"
            }

    def get_daily_usage(self, date: Optional[str] = None) -> Dict[str, Any]:
        """
        Get daily usage statistics

        Args:
            date: Date string (YYYY-MM-DD), defaults to today

        Returns:
            Dict with usage statistics
        """
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")

        if date not in self.usage_data:
            return {
                "date": date,
                "total_cost": Decimal('0.0'),
                "total_tokens": 0,
                "request_count": 0,
                "unique_sessions": 0,
                "usage_percentage": Decimal('0.0'),
                "status": "no_data"
            }

        data = self.usage_data[date]
        total_cost_decimal = data["total_cost"]
        usage_percentage_decimal = (total_cost_decimal / self.daily_limit) * Decimal('100')
        usage_percentage = from_decimal(usage_percentage_decimal)
        total_cost_float = from_decimal(total_cost_decimal)

        return {
            "date": date,
            "total_cost": total_cost_float,
            "total_tokens": data["total_tokens"],
            "request_count": data["request_count"],
            "unique_sessions": len(data["sessions"]),
            "usage_percentage": usage_percentage,
            "status": "ok" if total_cost_decimal < self.daily_limit else "limit_exceeded"
        }

    def get_weekly_usage(self) -> Dict[str, Any]:
        """
        Get weekly usage statistics

        Returns:
            Dict with weekly usage statistics
        """
        end_date = datetime.now()
        start_date = end_date - timedelta(days=7)

        total_cost_decimal = Decimal('0.0')
        total_tokens = 0
        total_requests = 0
        unique_sessions = set()

        for i in range(7):
            date = (start_date + timedelta(days=i)).strftime("%Y-%m-%d")
            if date in self.usage_data:
                data = self.usage_data[date]
                total_cost_decimal += data["total_cost"]
                total_tokens += data["total_tokens"]
                total_requests += data["request_count"]
                unique_sessions.update(data["sessions"])

        average_daily_cost_decimal = total_cost_decimal / Decimal('7')
        
        return {
            "period": "7_days",
            "total_cost": from_decimal(total_cost_decimal),
            "total_tokens": total_tokens,
            "total_requests": total_requests,
            "unique_sessions": len(unique_sessions),
            "average_daily_cost": from_decimal(average_daily_cost_decimal),
            "status": "ok"
        }

    def reset_daily_usage(self, date: Optional[str] = None) -> bool:
        """
        Reset daily usage data

        Args:
            date: Date string (YYYY-MM-DD), defaults to today

        Returns:
            True if reset successful
        """
        try:
            if date is None:
                date = datetime.now().strftime("%Y-%m-%d")

            if date in self.usage_data:
                del self.usage_data[date]
                logger.info("Daily usage data reset", extra={'date': date})
                return True
            else:
                logger.warning("No data found for date", extra={'date': date})
                return False

        except ConfigurationError as e:
            logger.error("Error resetting daily usage", extra={'error': str(e), 'date': date})
            return False

    def set_daily_limit(self, limit: Decimal) -> bool:
        """
        Update daily cost limit

        Args:
            limit: New daily limit in USD

        Returns:
            True if update successful
        """
        try:
            limit_decimal = to_decimal(limit)
            if limit_decimal <= Decimal('0'):
                raise ValueError("Daily limit must be positive")

            self.daily_limit = limit_decimal
            logger.info("Daily limit updated", extra={'new_limit': limit})
            return True

        except Exception as e:
            logger.error("Error updating daily limit", extra={'error': str(e), 'limit': limit})
            return False
