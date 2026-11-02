"""
Reinforcement Learning Types

This module defines all data structures, enums, and types for the reinforcement
learning system. It centralizes type definitions to improve maintainability
and type safety.

BRAIN & MUSCLE ARCHITECTURE:
ValuationIQ (The Muscle) provides ML calculations.
Titan (The Brain) manages conversation context and state.

Author: Upswitch CTO Team
Date: October 2025
Status: Production Ready
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Protocol, Tuple, Union

if TYPE_CHECKING:
    import numpy as np


class BusinessType(str, Enum):
    """Business type enum for RL context"""

    SOLE_PROPRIETOR = "sole_proprietor"
    PARTNERSHIP = "partnership"
    LLC = "llc"
    CORPORATION = "corporation"


class IndustryCategory(str, Enum):
    """Industry category enum for RL context"""

    CONSTRUCTION = "construction"
    MANUFACTURING = "manufacturing"
    RETAIL = "retail"
    SERVICES = "services"
    TECHNOLOGY = "technology"
    HEALTHCARE = "healthcare"
    OTHER = "other"


class ConversationContext(Protocol):
    """Protocol for conversation context (actual implementation in Titan)"""

    business_type: BusinessType
    industry: IndustryCategory
    data_completeness: Dict[str, Any]


class RLAction(str, Enum):
    """RL actions for methodology selection and question routing"""

    SELECT_DCF = "select_dcf"
    SELECT_MULTIPLES = "select_multiples"
    SELECT_ASSET_BASED = "select_asset_based"
    SELECT_HYBRID = "select_hybrid"
    ASK_FINANCIAL_QUESTION = "ask_financial_question"
    ASK_OWNER_QUESTION = "ask_owner_question"
    ASK_MARKET_QUESTION = "ask_market_question"
    COMPLETE_VALUATION = "complete_valuation"


class RLState:
    """RL state representation for valuation optimization"""

    def __init__(self, context: ConversationContext):
        """Initialize RL state from conversation context"""
        self.business_type = context.business_type
        self.industry = context.industry
        self.data_completeness = self._convert_data_completeness(context.data_completeness)
        self.conversation_step = 1  # Default step
        self.owner_dependency = getattr(context, "owner_dependency_score", Decimal("0.5"))
        self.financial_health = self._calculate_financial_health(context)
        self.market_context = self._calculate_market_context(context)
        self.timestamp = datetime.now()

    def _convert_data_completeness(self, data_completeness) -> Decimal:
        """Convert DataCompletenessLevel enum to float"""
        if hasattr(data_completeness, "value"):
            # Map enum values to float scores
            mapping = {
                "foundational": Decimal("0.2"),
                "basic": Decimal("0.4"),
                "intermediate": Decimal("0.6"),
                "advanced": Decimal("0.8"),
                "comprehensive": Decimal("1.0"),
            }
            return mapping.get(data_completeness.value, Decimal("0.5"))
        return Decimal("0.5")  # Default value

    def _calculate_financial_health(self, context: ConversationContext) -> Decimal:
        """Calculate financial health score from context"""
        # This would be more sophisticated in practice
        return min(self.data_completeness * Decimal("1.2"), Decimal("1.0"))

    def _calculate_market_context(self, context: ConversationContext) -> Decimal:
        """Calculate market context score from context"""
        # This would be more sophisticated in practice
        return Decimal("0.7")  # Placeholder for market context

    def to_vector(self) -> np.ndarray:
        """Convert state to vector representation for ML algorithms"""
        import numpy as np

        return np.array(
            [
                self.business_type.value if hasattr(self.business_type, "value") else 0,
                self.industry.value if hasattr(self.industry, "value") else 0,
                self.data_completeness,
                self.conversation_step,
                self.owner_dependency,
                self.financial_health,
                self.market_context,
            ]
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert state to dictionary for serialization"""
        return {
            "business_type": (
                self.business_type.value
                if hasattr(self.business_type, "value")
                else str(self.business_type)
            ),
            "industry": (
                self.industry.value if hasattr(self.industry, "value") else str(self.industry)
            ),
            "data_completeness": self.data_completeness,
            "conversation_step": self.conversation_step,
            "owner_dependency": self.owner_dependency,
            "financial_health": self.financial_health,
            "market_context": self.market_context,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class RLExperience:
    """RL experience for learning from user interactions"""

    state: RLState
    action: RLAction
    reward: Decimal
    next_state: Optional[RLState]
    done: bool
    timestamp: datetime
    metadata: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert experience to dictionary for serialization"""
        return {
            "state": self.state.to_dict(),
            "action": self.action.value,
            "reward": self.reward,
            "next_state": self.next_state.to_dict() if self.next_state else None,
            "done": self.done,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata or {},
        }


@dataclass
class QLearningConfig:
    """Configuration for Q-learning agent"""

    learning_rate: Decimal = Decimal("0.1")
    discount_factor: Decimal = Decimal("0.9")
    epsilon: Decimal = Decimal("0.1")
    epsilon_decay: Decimal = Decimal("0.995")
    epsilon_min: Decimal = Decimal("0.01")
    max_q_value: Decimal = Decimal("10.0")
    min_q_value: Decimal = -Decimal("10.0")


@dataclass
class PolicyGradientConfig:
    """Configuration for policy gradient agent"""

    learning_rate: Decimal = Decimal("0.01")
    baseline_decay: Decimal = Decimal("0.9")
    entropy_coefficient: Decimal = Decimal("0.01")
    max_gradient_norm: Decimal = Decimal("5.0")
    min_probability: Decimal = 1e-8


@dataclass
class MultiArmedBanditConfig:
    """Configuration for multi-armed bandit"""

    confidence_level: Decimal = Decimal("0.95")
    exploration_rate: Decimal = Decimal("0.1")
    min_samples: int = 10
    max_samples: int = 1000
    reward_scale: Decimal = Decimal("1.0")


@dataclass
class ContextualBanditConfig:
    """Configuration for contextual bandit"""

    feature_dim: int = 7
    num_arms: int = 8
    learning_rate: Decimal = Decimal("0.01")
    regularization: Decimal = Decimal("0.1")
    confidence_width: Decimal = Decimal("1.0")


@dataclass
class RLTrainingConfig:
    """Configuration for RL training"""

    batch_size: int = 32
    experience_buffer_size: int = 10000
    update_frequency: int = 100
    target_update_frequency: int = 1000
    max_episodes: int = 10000
    max_steps_per_episode: int = 100


@dataclass
class RLPerformanceMetrics:
    """Performance metrics for RL agents"""

    total_reward: Decimal = Decimal("0.0")
    average_reward: Decimal = Decimal("0.0")
    episode_count: int = 0
    step_count: int = 0
    convergence_rate: Decimal = Decimal("0.0")
    exploration_rate: Decimal = Decimal("0.0")
    q_value_range: Tuple[float, float] = (Decimal("0.0"), Decimal("0.0"))
    policy_entropy: Decimal = Decimal("0.0")
    bandit_regret: Decimal = Decimal("0.0")
    contextual_accuracy: Decimal = Decimal("0.0")


# Default configurations
DEFAULT_QL_CONFIG = QLearningConfig(
    learning_rate=Decimal("0.1"),
    discount_factor=Decimal("0.9"),
    epsilon=Decimal("0.1"),
    epsilon_decay=Decimal("0.995"),
    epsilon_min=Decimal("0.01"),
    max_q_value=Decimal("10.0"),
    min_q_value=-Decimal("10.0"),
)

DEFAULT_PG_CONFIG = PolicyGradientConfig(
    learning_rate=Decimal("0.01"),
    baseline_decay=Decimal("0.9"),
    entropy_coefficient=Decimal("0.01"),
    max_gradient_norm=Decimal("5.0"),
    min_probability=1e-8,
)

DEFAULT_MAB_CONFIG = MultiArmedBanditConfig(
    confidence_level=Decimal("0.95"),
    exploration_rate=Decimal("0.1"),
    min_samples=10,
    max_samples=1000,
    reward_scale=Decimal("1.0"),
)

DEFAULT_CB_CONFIG = ContextualBanditConfig(
    feature_dim=7,
    num_arms=8,
    learning_rate=Decimal("0.01"),
    regularization=Decimal("0.1"),
    confidence_width=Decimal("1.0"),
)

DEFAULT_TRAINING_CONFIG = RLTrainingConfig(
    batch_size=32,
    experience_buffer_size=10000,
    update_frequency=100,
    target_update_frequency=1000,
    max_episodes=10000,
    max_steps_per_episode=100,
)

# Action mappings
ACTION_TO_INDEX = {
    RLAction.SELECT_DCF: 0,
    RLAction.SELECT_MULTIPLES: 1,
    RLAction.SELECT_ASSET_BASED: 2,
    RLAction.SELECT_HYBRID: 3,
    RLAction.ASK_FINANCIAL_QUESTION: 4,
    RLAction.ASK_OWNER_QUESTION: 5,
    RLAction.ASK_MARKET_QUESTION: 6,
    RLAction.COMPLETE_VALUATION: 7,
}

INDEX_TO_ACTION = {v: k for k, v in ACTION_TO_INDEX.items()}

# Reward definitions
REWARD_DEFINITIONS = {
    "methodology_correct": Decimal("1.0"),
    "methodology_incorrect": -Decimal("0.5"),
    "question_relevant": Decimal("0.5"),
    "question_irrelevant": -Decimal("0.2"),
    "valuation_complete": Decimal("2.0"),
    "valuation_incomplete": -Decimal("1.0"),
    "user_satisfied": Decimal("1.5"),
    "user_dissatisfied": -Decimal("1.0"),
    "timeout": -Decimal("0.5"),
    "error": -Decimal("2.0"),
}

# State dimensions
STATE_DIMENSIONS = {
    "business_type": 1,
    "industry": 1,
    "data_completeness": 1,
    "conversation_step": 1,
    "owner_dependency": 1,
    "financial_health": 1,
    "market_context": 1,
    "total": 7,
}

# Action dimensions
ACTION_DIMENSIONS = {
    "total_actions": 8,
    "methodology_actions": 4,
    "question_actions": 3,
    "completion_actions": 1,
}

# Performance thresholds
PERFORMANCE_THRESHOLDS = {
    "min_average_reward": Decimal("0.5"),
    "min_convergence_rate": Decimal("0.8"),
    "max_exploration_rate": Decimal("0.3"),
    "min_policy_entropy": Decimal("0.1"),
    "max_bandit_regret": Decimal("0.2"),
    "min_contextual_accuracy": Decimal("0.7"),
}

# Learning schedules
LEARNING_SCHEDULES = {
    "epsilon_schedule": {"initial": Decimal("1.0"), "final": Decimal("0.01"), "decay_steps": 10000},
    "learning_rate_schedule": {
        "initial": Decimal("0.1"),
        "final": Decimal("0.001"),
        "decay_steps": 50000,
    },
    "exploration_schedule": {
        "initial": Decimal("0.3"),
        "final": Decimal("0.05"),
        "decay_steps": 20000,
    },
}
