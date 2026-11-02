"""
Config Loader Module

Loads valuation configuration including business rules, quality standards, etc.

RESPONSIBILITIES:
- Load business rules
- Load quality standards
- Load valuation service configurations

REFACTORING NOTE:
Extracted from valuation_orchestrator.py to isolate config loading.
"""

from typing import Any, Dict

# Built-in exceptions (AttributeError, ValueError, TypeError, KeyError, FileNotFoundError) are imported directly

from src.utils.exceptions import (
    ConfigurationError,
)
from src.utils.logging import get_logger

logger = get_logger(__name__)


class ConfigLoader:
    """
    Loads valuation configuration

    Features:
    - Business rules loading
    - Quality standards loading
    - Service configuration
    """

    def __init__(self):
        """Initialize config loader"""
        self.logger = logger
        self.logger.debug("✅ ConfigLoader initialized")

    def load_valuation_services(self) -> Dict[str, Any]:
        """Load valuation services configuration"""
        try:
            self.logger.debug("⚙️ Loading valuation services config")

            services = {
                "dcf_service": True,
                "multiples_service": True,
                "asset_based_service": True,
                "market_service": True,
                "monte_carlo_service": True,
            }

            self.logger.debug(f"✅ Loaded {len(services)} service configs")
            return services

        except (

            ConfigurationError,
            FileNotFoundError,
            ValueError,
            TypeError,
            AttributeError,
            KeyError,
        ) as e:
            self.logger.error(
                f"❌ Failed to load services config: {e}",
                extra={"error_type": type(e).__name__},
                exc_info=True,
            )
            return {}

    def load_business_rules(self) -> Dict[str, Any]:
        """Load business rules configuration"""
        try:
            self.logger.debug("📋 Loading business rules")

            rules = {
                "industry_multiples": {
                    "Technology": {"ebitda_multiple": 12.0, "revenue_multiple": 3.0},
                    "Manufacturing": {"ebitda_multiple": 8.0, "revenue_multiple": 1.5},
                    "Services": {"ebitda_multiple": 6.0, "revenue_multiple": 1.0},
                    "Retail": {"ebitda_multiple": 7.0, "revenue_multiple": 0.8},
                },
                "business_type_adjustments": {
                    "CORPORATION": 1.0,
                    "LLC": 0.95,
                    "SOLE_PROPRIETORSHIP": 0.85,
                    "PARTNERSHIP": 0.9,
                },
                "industry_adjustments": {
                    "Technology": 1.2,
                    "Healthcare": 1.15,
                    "Manufacturing": 1.0,
                    "Retail": 0.9,
                },
                "value_range_factors": {
                    "CORPORATION": 0.2,
                    "LLC": 0.25,
                    "SOLE_PROPRIETORSHIP": 0.3,
                    "Technology": 0.25,
                    "Manufacturing": 0.2,
                },
                "confidence_factors": {
                    "Technology": 0.05,
                    "Healthcare": 0.05,
                    "Manufacturing": 0.0,
                    "Retail": -0.05,
                },
            }

            self.logger.debug(
                f"✅ Loaded business rules",
                extra={
                    "industries": len(rules["industry_multiples"]),
                    "business_types": len(rules["business_type_adjustments"]),
                },
            )

            return rules

        except (

            ConfigurationError,
            FileNotFoundError,
            ValueError,
            TypeError,
            AttributeError,
            KeyError,
        ) as e:
            self.logger.error(
                f"❌ Failed to load business rules: {e}",
                extra={"error_type": type(e).__name__},
                exc_info=True,
            )
            return {}

    def load_quality_standards(self) -> Dict[str, Any]:
        """Load quality standards configuration"""
        try:
            self.logger.debug("⭐ Loading quality standards")

            standards = {
                "minimum_data_points": 5,
                "confidence_thresholds": {"high": 0.8, "medium": 0.6, "low": 0.4},
                "quality_thresholds": {"HIGH": 0.8, "MEDIUM": 0.6, "LOW": 0.4},
            }

            self.logger.debug("✅ Loaded quality standards")
            return standards

        except (

            ConfigurationError,
            FileNotFoundError,
            ValueError,
            TypeError,
            AttributeError,
            KeyError,
        ) as e:
            self.logger.error(
                f"❌ Failed to load quality standards: {e}",
                extra={"error_type": type(e).__name__},
                exc_info=True,
            )
            return {}
