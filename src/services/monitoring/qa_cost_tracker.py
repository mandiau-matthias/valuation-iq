"""
Q&A Cost Tracker

Tracks generic Q&A costs with budget management and alerts.
ValuationIQ no longer owns external AI provider spend; Titan tracks that.

Features:
- Real-time cost tracking
- Daily/weekly/monthly budget limits
- Cost alerts and warnings
- Cost optimization recommendations
- ROI tracking (cost vs. user satisfaction)

Author: Upswitch Engineering Team
Date: December 2024
"""

from dataclasses import dataclass
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum

from src.utils.logging import get_logger

logger = get_logger(__name__)


class AlertLevel(str, Enum):
    """Cost alert levels"""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class CostAlert:
    """Cost alert notification."""
    level: AlertLevel
    message: str
    timestamp: datetime
    current_cost: Decimal
    budget_limit: Decimal
    utilization_pct: float


class QACostTracker:
    """
    Tracks Q&A costs with budget management.
    
    Usage:
        tracker = QACostTracker(daily_budget=5.00, monthly_budget=100.00)
        
        # Track cost
        tracker.track_cost(
            session_id="abc123",
            cost=Decimal('0.01'),
            source="ai"
        )
        
        # Check budget
        if tracker.is_over_budget():
            print("Warning: Over budget!")
        
        # Get stats
        stats = tracker.get_stats()
        print(f"Today: ${stats['today_cost']:.2f}")
    """
    
    def __init__(
        self,
        daily_budget: float = 5.00,
        weekly_budget: float = 30.00,
        monthly_budget: float = 100.00,
        warning_threshold: float = 0.8  # Warn at 80% of budget
    ):
        self.logger = logger
        
        # Budget limits
        self.daily_budget = Decimal(str(daily_budget))
        self.weekly_budget = Decimal(str(weekly_budget))
        self.monthly_budget = Decimal(str(monthly_budget))
        self.warning_threshold = warning_threshold
        
        # Cost tracking
        self._costs: List[Dict] = []
        
        # Alerts
        self._alerts: List[CostAlert] = []
        
        self.logger.info(f"✅ QACostTracker initialized (daily: ${daily_budget}, monthly: ${monthly_budget})")
    
    def track_cost(
        self,
        session_id: str,
        cost: Decimal,
        source: str = "ai"
    ):
        """
        Track a cost event.
        
        Args:
            session_id: Session identifier
            cost: Cost in USD
            source: Cost source (ai, other)
        """
        self._costs.append({
            'timestamp': datetime.utcnow(),
            'session_id': session_id,
            'cost': cost,
            'source': source
        })
        
        # Check budget limits
        self._check_budget_limits()
        
        self.logger.debug(f"Tracked cost: ${float(cost):.4f}", extra={
            'session_id': session_id,
            'source': source
        })
    
    def get_stats(self) -> Dict[str, any]:
        """
        Get cost statistics.
        
        Returns:
            Dictionary with cost stats
        """
        now = datetime.utcnow()
        
        # Calculate costs for different time periods
        today_cost = self._get_cost_for_period(days=1)
        week_cost = self._get_cost_for_period(days=7)
        month_cost = self._get_cost_for_period(days=30)
        total_cost = sum(c['cost'] for c in self._costs)
        
        # Budget utilization
        daily_utilization = (today_cost / self.daily_budget) if self.daily_budget > 0 else 0
        weekly_utilization = (week_cost / self.weekly_budget) if self.weekly_budget > 0 else 0
        monthly_utilization = (month_cost / self.monthly_budget) if self.monthly_budget > 0 else 0
        
        # Cost breakdown by source
        ai_cost = sum(c['cost'] for c in self._costs if c['source'] == 'ai')
        
        # Calculate savings from local sources
        # Assume each AI call costs $0.01, local calls cost $0
        total_queries = len(self._costs)
        ai_queries = sum(1 for c in self._costs if c['source'] == 'ai')
        local_queries = total_queries - ai_queries
        estimated_savings = local_queries * Decimal('0.01')
        
        return {
            'today_cost': float(today_cost),
            'week_cost': float(week_cost),
            'month_cost': float(month_cost),
            'total_cost': float(total_cost),
            
            'daily_budget': float(self.daily_budget),
            'weekly_budget': float(self.weekly_budget),
            'monthly_budget': float(self.monthly_budget),
            
            'daily_utilization_pct': float(daily_utilization),
            'weekly_utilization_pct': float(weekly_utilization),
            'monthly_utilization_pct': float(monthly_utilization),
            
            'is_over_daily_budget': today_cost > self.daily_budget,
            'is_over_weekly_budget': week_cost > self.weekly_budget,
            'is_over_monthly_budget': month_cost > self.monthly_budget,
            
            'cost_by_source': {
                'ai': float(ai_cost)
            },
            
            'queries': {
                'total': total_queries,
                'ai': ai_queries,
                'local': local_queries
            },
            
            'estimated_savings': float(estimated_savings),
            
            'recent_alerts': len([a for a in self._alerts if a.timestamp > now - timedelta(hours=24)])
        }
    
    def is_over_budget(self) -> bool:
        """Check if over any budget limit."""
        today_cost = self._get_cost_for_period(days=1)
        week_cost = self._get_cost_for_period(days=7)
        month_cost = self._get_cost_for_period(days=30)
        
        return (
            today_cost > self.daily_budget or
            week_cost > self.weekly_budget or
            month_cost > self.monthly_budget
        )
    
    def get_budget_status(self) -> Dict[str, any]:
        """
        Get detailed budget status.
        
        Returns:
            Budget status with warnings
        """
        today_cost = self._get_cost_for_period(days=1)
        week_cost = self._get_cost_for_period(days=7)
        month_cost = self._get_cost_for_period(days=30)
        
        daily_util = (today_cost / self.daily_budget) if self.daily_budget > 0 else 0
        weekly_util = (week_cost / self.weekly_budget) if self.weekly_budget > 0 else 0
        monthly_util = (month_cost / self.monthly_budget) if self.monthly_budget > 0 else 0
        
        status = {
            'daily': {
                'cost': float(today_cost),
                'budget': float(self.daily_budget),
                'remaining': float(self.daily_budget - today_cost),
                'utilization_pct': float(daily_util),
                'status': self._get_status_level(daily_util)
            },
            'weekly': {
                'cost': float(week_cost),
                'budget': float(self.weekly_budget),
                'remaining': float(self.weekly_budget - week_cost),
                'utilization_pct': float(weekly_util),
                'status': self._get_status_level(weekly_util)
            },
            'monthly': {
                'cost': float(month_cost),
                'budget': float(self.monthly_budget),
                'remaining': float(self.monthly_budget - month_cost),
                'utilization_pct': float(monthly_util),
                'status': self._get_status_level(monthly_util)
            }
        }
        
        return status
    
    def get_recent_alerts(self, hours: int = 24) -> List[CostAlert]:
        """Get recent alerts."""
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        return [a for a in self._alerts if a.timestamp >= cutoff]
    
    def _get_cost_for_period(self, days: int) -> Decimal:
        """Get total cost for a time period."""
        cutoff = datetime.utcnow() - timedelta(days=days)
        return sum(
            c['cost'] for c in self._costs
            if c['timestamp'] >= cutoff
        )
    
    def _check_budget_limits(self):
        """Check budget limits and create alerts if needed."""
        today_cost = self._get_cost_for_period(days=1)
        week_cost = self._get_cost_for_period(days=7)
        month_cost = self._get_cost_for_period(days=30)
        
        # Check daily budget
        daily_util = (today_cost / self.daily_budget) if self.daily_budget > 0 else 0
        if daily_util >= 1.0:
            self._create_alert(
                AlertLevel.CRITICAL,
                f"Daily budget exceeded: ${float(today_cost):.2f} / ${float(self.daily_budget):.2f}",
                today_cost,
                self.daily_budget,
                daily_util
            )
        elif daily_util >= self.warning_threshold:
            self._create_alert(
                AlertLevel.WARNING,
                f"Daily budget at {daily_util*100:.0f}%: ${float(today_cost):.2f} / ${float(self.daily_budget):.2f}",
                today_cost,
                self.daily_budget,
                daily_util
            )
        
        # Check monthly budget
        monthly_util = (month_cost / self.monthly_budget) if self.monthly_budget > 0 else 0
        if monthly_util >= 1.0:
            self._create_alert(
                AlertLevel.CRITICAL,
                f"Monthly budget exceeded: ${float(month_cost):.2f} / ${float(self.monthly_budget):.2f}",
                month_cost,
                self.monthly_budget,
                monthly_util
            )
        elif monthly_util >= self.warning_threshold:
            self._create_alert(
                AlertLevel.WARNING,
                f"Monthly budget at {monthly_util*100:.0f}%: ${float(month_cost):.2f} / ${float(self.monthly_budget):.2f}",
                month_cost,
                self.monthly_budget,
                monthly_util
            )
    
    def _create_alert(
        self,
        level: AlertLevel,
        message: str,
        current_cost: Decimal,
        budget_limit: Decimal,
        utilization_pct: float
    ):
        """Create a cost alert."""
        alert = CostAlert(
            level=level,
            message=message,
            timestamp=datetime.utcnow(),
            current_cost=current_cost,
            budget_limit=budget_limit,
            utilization_pct=utilization_pct
        )
        
        self._alerts.append(alert)
        
        # Log alert
        if level == AlertLevel.CRITICAL:
            self.logger.error(f"🚨 {message}")
        elif level == AlertLevel.WARNING:
            self.logger.warning(f"⚠️ {message}")
        else:
            self.logger.info(f"ℹ️ {message}")
    
    def _get_status_level(self, utilization: float) -> str:
        """Get status level based on utilization."""
        if utilization >= 1.0:
            return "over_budget"
        elif utilization >= self.warning_threshold:
            return "warning"
        elif utilization >= 0.5:
            return "moderate"
        else:
            return "healthy"
    
    def reset_stats(self):
        """Reset all statistics and alerts."""
        self._costs.clear()
        self._alerts.clear()
        self.logger.info("Reset Q&A cost tracking")
