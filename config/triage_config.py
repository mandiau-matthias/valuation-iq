"""
Triage Engine Configuration

This module provides configuration settings for the refactored triage engine.
"""

import os
from typing import Dict, Any, Optional
from src.utils.logging import get_logger

logger = get_logger(__name__)


class TriageConfig:
    """Configuration class for triage engine"""
    
    def __init__(self):
        """Initialize configuration with environment variables"""
        self.enable_ai_enhancement = self._get_bool_env("ENABLE_AI_ENHANCEMENT", True)
        self.enable_owner_profiling = self._get_bool_env("ENABLE_OWNER_PROFILING", True)
        self.enable_data_lineage = self._get_bool_env("ENABLE_DATA_LINEAGE", True)
        self.enable_metrics = self._get_bool_env("ENABLE_METRICS", True)
        self.enable_streaming = self._get_bool_env("ENABLE_STREAMING", True)
        
        # Performance settings
        self.max_conversation_length = int(os.getenv("MAX_CONVERSATION_LENGTH", "50"))
        self.timeout_seconds = int(os.getenv("TIMEOUT_SECONDS", "300"))
        
        # AI settings
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        self.openai_model = os.getenv("OPENAI_MODEL", "gpt-4")
        
        # Database settings
        self.database_url = os.getenv("DATABASE_URL")
        
        # Metrics settings
        self.metrics_retention_days = int(os.getenv("METRICS_RETENTION_DAYS", "90"))
        
        # Feature flags
        self.feature_flags = {
            "ai_enhancement": self.enable_ai_enhancement,
            "owner_profiling": self.enable_owner_profiling,
            "data_lineage": self.enable_data_lineage,
            "metrics": self.enable_metrics,
            "streaming": self.enable_streaming
        }
        
        logger.info("Triage configuration initialized", 
                   ai_enhancement=self.enable_ai_enhancement,
                   owner_profiling=self.enable_owner_profiling,
                   data_lineage=self.enable_data_lineage,
                   metrics=self.enable_metrics,
                   streaming=self.enable_streaming)
    
    def _get_bool_env(self, key: str, default: bool) -> bool:
        """Get boolean environment variable"""
        value = os.getenv(key, str(default)).lower()
        return value in ("true", "1", "yes", "on")
    
    def get_config_dict(self) -> Dict[str, Any]:
        """Get configuration as dictionary"""
        return {
            "enable_ai_enhancement": self.enable_ai_enhancement,
            "enable_owner_profiling": self.enable_owner_profiling,
            "enable_data_lineage": self.enable_data_lineage,
            "enable_metrics": self.enable_metrics,
            "enable_streaming": self.enable_streaming,
            "max_conversation_length": self.max_conversation_length,
            "timeout_seconds": self.timeout_seconds,
            "openai_model": self.openai_model,
            "metrics_retention_days": self.metrics_retention_days
        }
    
    def validate_config(self) -> bool:
        """Validate configuration settings"""
        try:
            # Validate required settings
            if self.enable_ai_enhancement and not self.openai_api_key:
                logger.warning("AI enhancement enabled but OpenAI API key not provided")
                return False
            
            if self.enable_data_lineage and not self.database_url:
                logger.warning("Data lineage enabled but database URL not provided")
                return False
            
            # Validate numeric settings
            if self.max_conversation_length <= 0:
                logger.error("Invalid max_conversation_length: must be positive")
                return False
            
            if self.timeout_seconds <= 0:
                logger.error("Invalid timeout_seconds: must be positive")
                return False
            
            if self.metrics_retention_days <= 0:
                logger.error("Invalid metrics_retention_days: must be positive")
                return False
            
            logger.info("Configuration validation passed")
            return True
            
        except Exception as e:
            logger.error(f"Configuration validation failed: {e}")
            return False


# Global configuration instance
triage_config = TriageConfig()


def get_triage_config() -> TriageConfig:
    """Get the global triage configuration instance"""
    return triage_config


def get_feature_flags() -> Dict[str, bool]:
    """Get feature flags"""
    return triage_config.feature_flags


def is_feature_enabled(feature: str) -> bool:
    """Check if a feature is enabled"""
    return triage_config.feature_flags.get(feature, False)


# Configuration constants
DEFAULT_CONFIG = {
    "enable_ai_enhancement": True,
    "enable_owner_profiling": True,
    "enable_data_lineage": True,
    "enable_metrics": True,
    "enable_streaming": True,
    "max_conversation_length": 50,
    "timeout_seconds": 300,
    "openai_model": "gpt-4",
    "metrics_retention_days": 90
}

# Environment variable documentation
ENV_VARS_DOC = {
    "ENABLE_AI_ENHANCEMENT": "Enable AI-powered question generation (default: true)",
    "ENABLE_OWNER_PROFILING": "Enable owner profiling integration (default: true)",
    "ENABLE_DATA_LINEAGE": "Enable data lineage tracking (default: true)",
    "ENABLE_METRICS": "Enable metrics collection (default: true)",
    "ENABLE_STREAMING": "Enable streaming responses (default: true)",
    "MAX_CONVERSATION_LENGTH": "Maximum number of questions per conversation (default: 50)",
    "TIMEOUT_SECONDS": "Request timeout in seconds (default: 300)",
    "OPENAI_API_KEY": "OpenAI API key for AI enhancement",
    "OPENAI_MODEL": "OpenAI model to use (default: gpt-4)",
    "DATABASE_URL": "Database connection URL for data persistence",
    "METRICS_RETENTION_DAYS": "Number of days to retain metrics data (default: 90)"
}
