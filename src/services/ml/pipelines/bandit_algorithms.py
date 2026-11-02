from src.utils.exceptions import CalculationError, ConfigurationError, ValuationRangeError

"""
Bandit Algorithms

This module implements multi-armed bandit and contextual bandit algorithms
for reinforcement learning in valuation optimization. Includes UCB, LinUCB,
and confidence interval calculations.

Author: Upswitch CTO Team
Date: October 2025
Status: Production Ready
"""

import numpy as np
from typing import Dict, Any, List, Optional, Tuple, Union
import random
import math

from src.utils.logging import get_logger
from decimal import Decimal
from src.utils.decimal_helpers import to_decimal, from_decimal
from .rl_types import (
    RLAction, RLState, MultiArmedBanditConfig, ContextualBanditConfig,
    DEFAULT_MAB_CONFIG, DEFAULT_CB_CONFIG, ACTION_TO_INDEX, INDEX_TO_ACTION
)

logger = get_logger(__name__)


class MultiArmedBandit:
    """Multi-armed bandit for A/B testing different approaches"""

    def __init__(self, arms: List[str], config: Optional[MultiArmedBanditConfig] = None):
        """Initialize multi-armed bandit"""
        self.arms = arms
        self.config = config or DEFAULT_MAB_CONFIG
        self.arm_counts = {arm: 0 for arm in arms}
        self.arm_rewards = {arm: [] for arm in arms}
        self.arm_means = {arm: Decimal('0.0') for arm in arms}
        self.total_pulls = 0
        self.confidence_level = self.config.confidence_level

        logger.info(f"✅ MultiArmedBandit initialized with {len(arms)} arms")

    def select_arm(self) -> str:
        """Select arm using UCB algorithm"""

        try:
            logger.info(f"🎯 Selecting arm from {len(self.arms)} options")

            # If any arm hasn't been pulled, select it
            for arm in self.arms:
                if self.arm_counts[arm] == 0:
                    logger.info(f"🔍 Exploring new arm: {arm}")
                    return arm

            # Calculate UCB values for all arms
            ucb_values = {}
            for arm in self.arms:
                ucb_value = self._calculate_ucb(arm)
                ucb_values[arm] = ucb_value

            # Select arm with highest UCB value
            best_arm = max(ucb_values.keys(), key=lambda a: ucb_values[a])

            # Handle ties by random selection
            max_ucb = ucb_values[best_arm]
            tied_arms = [a for a, ucb in ucb_values.items() if ucb == max_ucb]

            if len(tied_arms) > 1:
                best_arm = random.choice(tied_arms)

            logger.info(f"💡 Selected arm: {best_arm} (UCB: {ucb_values[best_arm]:.3f})")
            return best_arm

        except ValuationEngineError as e:
            logger.error(f"❌ Arm selection failed: {str(e)}")
            return random.choice(self.arms)

    def _calculate_ucb(self, arm: str) -> Decimal:
        """Calculate Upper Confidence Bound for an arm"""

        try:
            if self.arm_counts[arm] == 0:
                return to_decimal('inf')

            # UCB formula: mean + sqrt(2 * ln(total) / count)
            mean_reward = self.arm_means[arm]
            confidence_width = math.sqrt(2 * math.log(self.total_pulls) / self.arm_counts[arm])
            ucb_value = mean_reward + confidence_width

            return ucb_value

        except CalculationError as e:
            logger.error(f"❌ UCB calculation failed for arm {arm}: {str(e)}")
            return Decimal('0.0')

    def update_arm(self, arm: str, reward: Decimal):
        """Update arm statistics with new reward"""

        try:
            logger.info(f"🔄 Updating arm {arm} with reward {reward:.3f}")

            if arm not in self.arms:
                logger.error(f"❌ Unknown arm: {arm}")
                return

            # Update counts and rewards
            self.arm_counts[arm] += 1
            self.arm_rewards[arm].append(reward)
            self.total_pulls += 1

            # Update mean reward
            self.arm_means[arm] = np.mean(self.arm_rewards[arm])

            # Scale reward if needed
            if self.config.reward_scale != 1.0:
                scaled_reward = reward * self.config.reward_scale
                self.arm_rewards[arm][-1] = scaled_reward
                self.arm_means[arm] = np.mean(self.arm_rewards[arm])

            logger.info(f"✅ Arm {arm} updated: mean={self.arm_means[arm]:.3f}, count={self.arm_counts[arm]}")

        except ConfigurationError as e:
            logger.error(f"❌ Arm update failed: {str(e)}")

    def get_arm_statistics(self) -> Dict[str, Dict[str, Decimal]]:
        """Get statistics for all arms"""

        try:
            statistics = {}

            for arm in self.arms:
                arm_stats = {
                    "count": self.arm_counts[arm],
                    "mean_reward": self.arm_means[arm],
                    "total_reward": sum(self.arm_rewards[arm]),
                    "std_reward": np.std(self.arm_rewards[arm]) if len(self.arm_rewards[arm]) > 1 else Decimal('0.0'),
                    "ucb_value": self._calculate_ucb(arm),
                    "confidence_interval": self._calculate_confidence_interval(arm)
                }
                statistics[arm] = arm_stats

            logger.info(f"📊 Arm statistics computed for {len(self.arms)} arms")
            return statistics

        except ValuationRangeError as e:
            logger.error(f"❌ Statistics computation failed: {str(e)}")
            return {}

    def _calculate_confidence_interval(self, arm: str) -> Tuple[float, float]:
        """Calculate confidence interval for an arm"""

        try:
            if self.arm_counts[arm] < 2:
                return (Decimal('0.0'), Decimal('0.0'))

            rewards = self.arm_rewards[arm]
            mean_reward = np.mean(rewards)
            std_reward = np.std(rewards)

            # Calculate confidence interval
            n = len(rewards)
            t_value = Decimal('1.96')  # Approximate for 95% confidence
            margin_error = t_value * (std_reward / math.sqrt(n))

            lower_bound = mean_reward - margin_error
            upper_bound = mean_reward + margin_error

            return (lower_bound, upper_bound)

        except ValuationRangeError as e:
            logger.error(f"❌ Confidence interval calculation failed for arm {arm}: {str(e)}")
            return (Decimal('0.0'), Decimal('0.0'))

    def get_best_arm(self) -> str:
        """Get the best performing arm"""

        try:
            if not any(self.arm_counts.values()):
                return random.choice(self.arms)

            # Find arm with highest mean reward
            best_arm = max(self.arm_means.keys(), key=lambda a: self.arm_means[a])

            # Handle ties by selecting arm with more pulls
            max_mean = self.arm_means[best_arm]
            tied_arms = [a for a, mean in self.arm_means.items() if mean == max_mean]

            if len(tied_arms) > 1:
                best_arm = max(tied_arms, key=lambda a: self.arm_counts[a])

            return best_arm

        except ConfigurationError as e:
            logger.error(f"❌ Best arm selection failed: {str(e)}")
            return random.choice(self.arms)

    def reset_bandit(self):
        """Reset bandit to initial state"""

        try:
            logger.info("🔄 Resetting multi-armed bandit")

            self.arm_counts = {arm: 0 for arm in self.arms}
            self.arm_rewards = {arm: [] for arm in self.arms}
            self.arm_means = {arm: Decimal('0.0') for arm in self.arms}
            self.total_pulls = 0

            logger.info("✅ Multi-armed bandit reset")

        except ConfigurationError as e:
            logger.error(f"❌ Bandit reset failed: {str(e)}")


class ContextualBandit:
    """Contextual bandit for personalized optimization"""

    def __init__(self, feature_dim: int, num_arms: int, config: Optional[ContextualBanditConfig] = None):
        """Initialize contextual bandit"""
        self.feature_dim = feature_dim
        self.num_arms = num_arms
        self.config = config or DEFAULT_CB_CONFIG
        self.arm_features = {i: np.zeros(feature_dim) for i in range(num_arms)}
        self.arm_rewards = {i: [] for i in range(num_arms)}
        self.arm_counts = {i: 0 for i in range(num_arms)}
        self.learning_rate = self.config.learning_rate
        self.regularization = self.config.regularization
        self.confidence_width = self.config.confidence_width

        logger.info(f"✅ ContextualBandit initialized: {feature_dim}D features, {num_arms} arms")

    def select_arm(self, context: np.ndarray) -> int:
        """Select arm using LinUCB algorithm"""

        try:
            logger.info(f"🎯 Selecting arm for {len(context)}D context")

            if len(context) != self.feature_dim:
                logger.error(f"❌ Context dimension mismatch: expected {self.feature_dim}, got {len(context)}")
                return random.randint(0, self.num_arms - 1)

            # Calculate LinUCB values for all arms
            ucb_values = {}
            for arm in range(self.num_arms):
                ucb_value = self._calculate_linucb(arm, context)
                ucb_values[arm] = ucb_value

            # Select arm with highest UCB value
            best_arm = max(ucb_values.keys(), key=lambda a: ucb_values[a])

            # Handle ties by random selection
            max_ucb = ucb_values[best_arm]
            tied_arms = [a for a, ucb in ucb_values.items() if ucb == max_ucb]

            if len(tied_arms) > 1:
                best_arm = random.choice(tied_arms)

            logger.info(f"💡 Selected arm: {best_arm} (LinUCB: {ucb_values[best_arm]:.3f})")
            return best_arm

        except ValuationEngineError as e:
            logger.error(f"❌ Arm selection failed: {str(e)}")
            return random.randint(0, self.num_arms - 1)

    def _calculate_linucb(self, arm: int, context: np.ndarray) -> Decimal:
        """Calculate LinUCB value for an arm"""

        try:
            if self.arm_counts[arm] == 0:
                return to_decimal('inf')

            # Get arm features and rewards
            arm_features = self.arm_features[arm]
            arm_rewards = self.arm_rewards[arm]

            if len(arm_rewards) == 0:
                return Decimal('0.0')

            # Calculate mean reward
            mean_reward = np.mean(arm_rewards)

            # Calculate confidence width using ridge regression
            # Simplified version: use standard deviation
            if len(arm_rewards) > 1:
                std_reward = np.std(arm_rewards)
                confidence_width = self.confidence_width * std_reward / math.sqrt(len(arm_rewards))
            else:
                confidence_width = self.confidence_width

            # LinUCB: mean + confidence_width
            linucb_value = mean_reward + confidence_width

            return linucb_value

        except CalculationError as e:
            logger.error(f"❌ LinUCB calculation failed for arm {arm}: {str(e)}")
            return Decimal('0.0')

    def update_arm(self, arm: int, context: np.ndarray, reward: Decimal):
        """Update arm with new context and reward"""

        try:
            logger.info(f"🔄 Updating arm {arm} with reward {reward:.3f}")

            if arm < 0 or arm >= self.num_arms:
                logger.error(f"❌ Invalid arm: {arm}")
                return

            if len(context) != self.feature_dim:
                logger.error(f"❌ Context dimension mismatch: expected {self.feature_dim}, got {len(context)}")
                return

            # Update arm statistics
            self.arm_counts[arm] += 1
            self.arm_rewards[arm].append(reward)

            # Update arm features using exponential moving average
            alpha = self.learning_rate
            self.arm_features[arm] = (1 - alpha) * self.arm_features[arm] + alpha * context

            logger.info(f"✅ Arm {arm} updated: count={self.arm_counts[arm]}, mean={np.mean(self.arm_rewards[arm]):.3f}")

        except ValuationRangeError as e:
            logger.error(f"❌ Arm update failed: {str(e)}")

    def get_arm_statistics(self) -> Dict[int, Dict[str, Any]]:
        """Get statistics for all arms"""

        try:
            statistics = {}

            for arm in range(self.num_arms):
                arm_stats = {
                    "count": self.arm_counts[arm],
                    "mean_reward": np.mean(self.arm_rewards[arm]) if self.arm_rewards[arm] else Decimal('0.0'),
                    "total_reward": sum(self.arm_rewards[arm]),
                    "std_reward": np.std(self.arm_rewards[arm]) if len(self.arm_rewards[arm]) > 1 else Decimal('0.0'),
                    "feature_vector": self.arm_features[arm].tolist(),
                    "confidence_width": self.confidence_width
                }
                statistics[arm] = arm_stats

            logger.info(f"📊 Arm statistics computed for {self.num_arms} arms")
            return statistics

        except ValuationEngineError as e:
            logger.error(f"❌ Statistics computation failed: {str(e)}")
            return {}

    def get_best_arm(self) -> int:
        """Get the best performing arm"""

        try:
            if not any(self.arm_counts.values()):
                return random.randint(0, self.num_arms - 1)

            # Find arm with highest mean reward
            arm_means = {arm: np.mean(rewards) for arm, rewards in self.arm_rewards.items() if rewards}

            if not arm_means:
                return random.randint(0, self.num_arms - 1)

            best_arm = max(arm_means.keys(), key=lambda a: arm_means[a])

            # Handle ties by selecting arm with more pulls
            max_mean = arm_means[best_arm]
            tied_arms = [a for a, mean in arm_means.items() if mean == max_mean]

            if len(tied_arms) > 1:
                best_arm = max(tied_arms, key=lambda a: self.arm_counts[a])

            return best_arm

        except ValuationRangeError as e:
            logger.error(f"❌ Best arm selection failed: {str(e)}")
            return random.randint(0, self.num_arms - 1)

    def reset_bandit(self):
        """Reset contextual bandit to initial state"""

        try:
            logger.info("🔄 Resetting contextual bandit")

            self.arm_features = {i: np.zeros(self.feature_dim) for i in range(self.num_arms)}
            self.arm_rewards = {i: [] for i in range(self.num_arms)}
            self.arm_counts = {i: 0 for i in range(self.num_arms)}

            logger.info("✅ Contextual bandit reset")

        except ValuationRangeError as e:
            logger.error(f"❌ Bandit reset failed: {str(e)}")

    def get_arm_prediction(self, arm: int, context: np.ndarray) -> Decimal:
        """Get predicted reward for an arm given context"""

        try:
            if arm < 0 or arm >= self.num_arms:
                return Decimal('0.0')

            if len(context) != self.feature_dim:
                return Decimal('0.0')

            # Simple prediction: dot product of arm features and context
            arm_features = self.arm_features[arm]
            prediction = np.dot(arm_features, context)

            return to_decimal(prediction)

        except ValuationRangeError as e:
            logger.error(f"❌ Arm prediction failed: {str(e)}")
            return Decimal('0.0')

    def get_all_predictions(self, context: np.ndarray) -> Dict[int, Decimal]:
        """Get predicted rewards for all arms given context"""

        try:
            predictions = {}

            for arm in range(self.num_arms):
                prediction = self.get_arm_prediction(arm, context)
                predictions[arm] = prediction

            return predictions

        except ValuationRangeError as e:
            logger.error(f"❌ All predictions failed: {str(e)}")
            return {}
