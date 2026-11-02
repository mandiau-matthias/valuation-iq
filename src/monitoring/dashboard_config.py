from src.utils.exceptions import APIError

"""
Monitoring Dashboard Configuration

This module provides configuration for monitoring dashboards
including metrics collection and alerting rules.
"""

import os
import time
from typing import Dict, Any, List
from datetime import datetime, timedelta
from prometheus_client import Counter, Histogram, Gauge, Summary, start_http_server
from src.utils.logging import get_logger

logger = get_logger(__name__)

# Prometheus Metrics
class ValuationMetrics:
    """Metrics collection for valuation engine."""

    def __init__(self):
        # Request metrics
        self.request_count = Counter(
            'valuation_requests_total',
            'Total number of valuation requests',
            ['method', 'endpoint', 'status']
        )

        self.request_duration = Histogram(
            'valuation_request_duration_seconds',
            'Request duration in seconds',
            ['method', 'endpoint']
        )

        # Valuation metrics
        self.valuation_count = Counter(
            'valuations_total',
            'Total number of valuations performed',
            ['method', 'industry', 'country']
        )

        self.valuation_duration = Histogram(
            'valuation_duration_seconds',
            'Valuation calculation duration',
            ['method']
        )

        # AI conversation metrics
        self.conversation_count = Counter(
            'conversations_total',
            'Total number of AI conversations',
            ['status']
        )

        self.conversation_duration = Histogram(
            'conversation_duration_seconds',
            'Conversation duration',
            ['status']
        )

        # Registry search metrics
        self.registry_search_count = Counter(
            'registry_searches_total',
            'Total number of registry searches',
            ['country', 'status']
        )

        self.registry_search_duration = Histogram(
            'registry_search_duration_seconds',
            'Registry search duration'
        )

        # Error metrics
        self.error_count = Counter(
            'errors_total',
            'Total number of errors',
            ['error_type', 'component']
        )

        # System metrics
        self.active_sessions = Gauge(
            'active_sessions',
            'Number of active user sessions'
        )

        self.database_connections = Gauge(
            'database_connections_active',
            'Number of active database connections'
        )

        self.cache_hit_ratio = Gauge(
            'cache_hit_ratio',
            'Cache hit ratio'
        )

        # AI metrics
        self.ai_requests = Counter(
            'ai_requests_total',
            'Total AI requests',
            ['model', 'status']
        )

        self.ai_cost = Counter(
            'ai_cost_total',
            'Total AI cost in USD',
            ['model']
        )

        self.ai_tokens = Counter(
            'ai_tokens_total',
            'Total AI tokens used',
            ['model', 'type']
        )

# Global metrics instance
metrics = ValuationMetrics()

class MonitoringDashboard:
    """Monitoring dashboard configuration."""

    def __init__(self):
        self.metrics_port = int(os.getenv("METRICS_PORT", "9090"))
        self.start_time = time.time()

    def start_metrics_server(self):
        """Start Prometheus metrics server."""
        try:
            start_http_server(self.metrics_port)
            logger.info(f"📊 Metrics server started on port {self.metrics_port}")
            return True
        except APIError as e:
            logger.error(f"❌ Failed to start metrics server: {e}")
            return False

    def get_system_metrics(self) -> Dict[str, Any]:
        """Get current system metrics."""
        import psutil

        return {
            "cpu_percent": psutil.cpu_percent(),
            "memory_percent": psutil.virtual_memory().percent,
            "disk_percent": psutil.disk_usage('/').percent,
            "uptime_seconds": time.time() - self.start_time,
            "timestamp": datetime.now().isoformat()
        }

    def get_application_metrics(self) -> Dict[str, Any]:
        """Get application-specific metrics."""
        return {
            "active_sessions": metrics.active_sessions._value.get(),
            "database_connections": metrics.database_connections._value.get(),
            "cache_hit_ratio": metrics.cache_hit_ratio._value.get(),
            "total_valuations": sum([
                metrics.valuation_count._value.get((method, industry, country), 0)
                for method in ['dcf', 'multiples', 'quick']
                for industry in ['technology', 'manufacturing', 'services']
                for country in ['BE', 'NL', 'DE', 'FR']
            ]),
            "total_conversations": sum([
                metrics.conversation_count._value.get((status,), 0)
                for status in ['started', 'completed', 'failed']
            ]),
            "total_errors": sum([
                metrics.error_count._value.get((error_type, component), 0)
                for error_type in ['validation', 'calculation', 'ai', 'database']
                for component in ['api', 'valuation', 'conversation', 'registry']
            ])
        }

    def get_health_status(self) -> Dict[str, Any]:
        """Get health status for monitoring."""
        system_metrics = self.get_system_metrics()
        app_metrics = self.get_application_metrics()

        # Determine health status
        health_status = "healthy"
        issues = []

        # Check system resources
        if system_metrics["cpu_percent"] > 80:
            health_status = "degraded"
            issues.append("High CPU usage")

        if system_metrics["memory_percent"] > 85:
            health_status = "degraded"
            issues.append("High memory usage")

        if system_metrics["disk_percent"] > 90:
            health_status = "critical"
            issues.append("High disk usage")

        # Check application metrics
        if app_metrics["total_errors"] > 100:  # Threshold for errors
            health_status = "degraded"
            issues.append("High error rate")

        return {
            "status": health_status,
            "issues": issues,
            "system": system_metrics,
            "application": app_metrics,
            "timestamp": datetime.now().isoformat()
        }

# Dashboard configuration
dashboard = MonitoringDashboard()

# Alerting rules
ALERTING_RULES = {
    "high_cpu": {
        "metric": "cpu_percent",
        "threshold": 80,
        "severity": "warning",
        "message": "High CPU usage detected"
    },
    "high_memory": {
        "metric": "memory_percent", 
        "threshold": 85,
        "severity": "warning",
        "message": "High memory usage detected"
    },
    "high_disk": {
        "metric": "disk_percent",
        "threshold": 90,
        "severity": "critical",
        "message": "High disk usage detected"
    },
    "high_error_rate": {
        "metric": "error_rate",
        "threshold": 0.1,  # 10% error rate
        "severity": "critical",
        "message": "High error rate detected"
    },
    "slow_response": {
        "metric": "response_time",
        "threshold": 5.0,  # 5 seconds
        "severity": "warning",
        "message": "Slow response time detected"
    }
}

def check_alerts() -> List[Dict[str, Any]]:
    """Check for alerting conditions."""
    alerts = []
    health = dashboard.get_health_status()

    for rule_name, rule in ALERTING_RULES.items():
        metric_name = rule["metric"]
        threshold = rule["threshold"]

        if metric_name in health["system"]:
            value = health["system"][metric_name]
            if value > threshold:
                alerts.append({
                    "rule": rule_name,
                    "severity": rule["severity"],
                    "message": rule["message"],
                    "value": value,
                    "threshold": threshold,
                    "timestamp": datetime.now().isoformat()
                })

    return alerts

def get_dashboard_data() -> Dict[str, Any]:
    """Get complete dashboard data."""
    return {
        "health": dashboard.get_health_status(),
        "alerts": check_alerts(),
        "metrics": {
            "system": dashboard.get_system_metrics(),
            "application": dashboard.get_application_metrics()
        },
        "timestamp": datetime.now().isoformat()
    }

# Initialize monitoring
def initialize_monitoring():
    """Initialize monitoring system."""
    logger.info("🔧 Initializing monitoring system...")

    # Start metrics server
    if dashboard.start_metrics_server():
        logger.info("✅ Metrics server started")
    else:
        logger.warning("⚠️ Metrics server failed to start")

    # Log initial health status
    health = dashboard.get_health_status()
    logger.info(f"📊 Initial health status: {health['status']}")

    if health["issues"]:
        logger.warning(f"⚠️ Health issues: {', '.join(health['issues'])}")

    return True
