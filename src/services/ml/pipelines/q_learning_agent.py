from src.utils.exceptions import ConfigurationError

"""
Q-Learning Agent

This module implements Q-learning algorithm for reinforcement learning in
valuation optimization. Includes epsilon-greedy exploration, Q-table management,
and Bellman equation updates.

Author: Upswitch CTO Team
Date: October 2025
Status: Production Ready
"""

import numpy as np
from typing import Dict, Any, List, Optional, Tuple
from collections import defaultdict
import random
import math

from src.utils.logging import get_logger
from decimal import Decimal
from src.utils.decimal_helpers import to_decimal, from_decimal
from .rl_types import (
    RLAction, RLState, RLExperience, QLearningConfig,
    DEFAULT_QL_CONFIG, ACTION_TO_INDEX, INDEX_TO_ACTION
)

logger = get_logger(__name__)


class QLearningAgent:
    """Q-learning agent for valuation optimization"""

    def __init__(self, config: Optional[QLearningConfig] = None):
        """Initialize Q-learning agent"""
        self.config = config or DEFAULT_QL_CONFIG
        self.q_table = defaultdict(lambda: defaultdict(float))
        self.epsilon = self.config.epsilon
        self.learning_rate = self.config.learning_rate
        self.discount_factor = self.config.discount_factor
        self.episode_count = 0
        self.step_count = 0
        self.total_reward = Decimal('0.0')

        logger.info("✅ QLearningAgent initialized")

    def get_action(self, state: RLState) -> RLAction:
        """Get action using epsilon-greedy policy"""

        try:
            logger.info(f"🎯 Getting action for state: {state.business_type}")

            # Epsilon-greedy exploration
            if random.random() < self.epsilon:
                # Explore: random action
                action = random.choice(list(RLAction))
                logger.info(f"🔍 Exploring with random action: {action}")
            else:
                # Exploit: best action
                action = self._get_best_action(state)
                logger.info(f"💡 Exploiting with best action: {action}")

            self.step_count += 1
            return action

        except ValuationEngineError as e:
            logger.error(f"❌ Action selection failed: {str(e)}")
            # Fallback to random action
            return random.choice(list(RLAction))

    def _get_best_action(self, state: RLState) -> RLAction:
        """Get best action based on Q-values"""

        try:
            state_key = self._state_to_key(state)
            q_values = self.q_table[state_key]

            if not q_values:
                # No Q-values for this state, return random action
                return random.choice(list(RLAction))

            # Find action with highest Q-value
            best_action = max(q_values.keys(), key=lambda a: q_values[a])

            # Handle ties by random selection
            max_q_value = q_values[best_action]
            tied_actions = [a for a, q in q_values.items() if q == max_q_value]

            if len(tied_actions) > 1:
                best_action = random.choice(tied_actions)

            return best_action

        except ValuationEngineError as e:
            logger.error(f"❌ Best action selection failed: {str(e)}")
            return random.choice(list(RLAction))

    def update_q_value(self, experience: RLExperience):
        """Update Q-value using Bellman equation"""

        try:
            logger.info(f"🔄 Updating Q-value for action: {experience.action}")

            state_key = self._state_to_key(experience.state)
            action = experience.action
            reward = experience.reward
            next_state = experience.next_state
            done = experience.done

            # Get current Q-value
            current_q = self.q_table[state_key][action]

            if done:
                # Terminal state: Q(s,a) = r
                new_q = reward
            else:
                # Non-terminal state: Q(s,a) = r + γ * max Q(s',a')
                next_state_key = self._state_to_key(next_state)
                next_q_values = self.q_table[next_state_key]

                if next_q_values:
                    max_next_q = max(next_q_values.values())
                else:
                    max_next_q = Decimal('0.0')

                # Bellman equation: Q(s,a) = Q(s,a) + α[r + γ * max Q(s',a') - Q(s,a)]
                new_q = current_q + self.learning_rate * (reward + self.discount_factor * max_next_q - current_q)

            # Update Q-table
            self.q_table[state_key][action] = new_q

            # Clip Q-values to prevent explosion
            self.q_table[state_key][action] = np.clip(
                self.q_table[state_key][action],
                self.config.min_q_value,
                self.config.max_q_value
            )

            # Update statistics
            self.total_reward += reward

            logger.info(f"✅ Q-value updated: {current_q:.3f} → {new_q:.3f}")

        except ConfigurationError as e:
            logger.error(f"❌ Q-value update failed: {str(e)}")

    def _state_to_key(self, state: RLState) -> str:
        """Convert state to string key for Q-table"""

        try:
            # Create a hashable key from state
            state_vector = state.to_vector()
            # Round to avoid floating point precision issues
            rounded_vector = np.round(state_vector, 3)
            return str(tuple(rounded_vector))

        except ConfigurationError as e:
            logger.error(f"❌ State key conversion failed: {str(e)}")
            return "default_state"

    def decay_epsilon(self):
        """Decay exploration rate"""

        try:
            old_epsilon = self.epsilon
            self.epsilon = max(
                self.epsilon * self.config.epsilon_decay,
                self.config.epsilon_min
            )

            if old_epsilon != self.epsilon:
                logger.info(f"📉 Epsilon decayed: {old_epsilon:.3f} → {self.epsilon:.3f}")

        except ConfigurationError as e:
            logger.error(f"❌ Epsilon decay failed: {str(e)}")

    def get_q_value(self, state: RLState, action: RLAction) -> Decimal:
        """Get Q-value for state-action pair"""

        try:
            state_key = self._state_to_key(state)
            return self.q_table[state_key][action]

        except ValuationEngineError as e:
            logger.error(f"❌ Q-value retrieval failed: {str(e)}")
            return Decimal('0.0')

    def get_state_values(self, state: RLState) -> Dict[RLAction, Decimal]:
        """Get all Q-values for a state"""

        try:
            state_key = self._state_to_key(state)
            return dict(self.q_table[state_key])

        except ValuationEngineError as e:
            logger.error(f"❌ State values retrieval failed: {str(e)}")
            return {}

    def get_best_action_value(self, state: RLState) -> Tuple[RLAction, float]:
        """Get best action and its Q-value for a state"""

        try:
            state_values = self.get_state_values(state)

            if not state_values:
                return random.choice(list(RLAction)), Decimal('0.0')

            best_action = max(state_values.keys(), key=lambda a: state_values[a])
            best_value = state_values[best_action]

            return best_action, best_value

        except ValuationEngineError as e:
            logger.error(f"❌ Best action value retrieval failed: {str(e)}")
            return random.choice(list(RLAction)), Decimal('0.0')

    def get_agent_statistics(self) -> Dict[str, Any]:
        """Get agent performance statistics"""

        try:
            # Calculate Q-table statistics
            all_q_values = []
            for state_q in self.q_table.values():
                all_q_values.extend(state_q.values())

            if all_q_values:
                q_mean = np.mean(all_q_values)
                q_std = np.std(all_q_values)
                q_min = np.min(all_q_values)
                q_max = np.max(all_q_values)
            else:
                q_mean = q_std = q_min = q_max = Decimal('0.0')

            # Calculate average reward
            avg_reward = self.total_reward / max(self.step_count, 1)

            statistics = {
                "episode_count": self.episode_count,
                "step_count": self.step_count,
                "total_reward": self.total_reward,
                "average_reward": avg_reward,
                "epsilon": self.epsilon,
                "learning_rate": self.learning_rate,
                "q_table_size": len(self.q_table),
                "q_value_mean": q_mean,
                "q_value_std": q_std,
                "q_value_min": q_min,
                "q_value_max": q_max,
                "exploration_rate": self.epsilon,
                "exploitation_rate": Decimal('1.0') - self.epsilon
            }

            logger.info(f"📊 Agent statistics computed: {len(self.q_table)} states")
            return statistics

        except ValuationEngineError as e:
            logger.error(f"❌ Statistics computation failed: {str(e)}")
            return {
                "episode_count": 0,
                "step_count": 0,
                "total_reward": Decimal('0.0'),
                "average_reward": Decimal('0.0'),
                "epsilon": self.epsilon,
                "learning_rate": self.learning_rate,
                "q_table_size": 0,
                "q_value_mean": Decimal('0.0'),
                "q_value_std": Decimal('0.0'),
                "q_value_min": Decimal('0.0'),
                "q_value_max": Decimal('0.0'),
                "exploration_rate": self.epsilon,
                "exploitation_rate": Decimal('1.0') - self.epsilon
            }

    def reset_agent(self):
        """Reset agent to initial state"""

        try:
            logger.info("🔄 Resetting Q-learning agent")

            self.q_table.clear()
            self.epsilon = self.config.epsilon
            self.episode_count = 0
            self.step_count = 0
            self.total_reward = Decimal('0.0')

            logger.info("✅ Q-learning agent reset")

        except ConfigurationError as e:
            logger.error(f"❌ Agent reset failed: {str(e)}")

    def save_q_table(self, filepath: str) -> bool:
        """Save Q-table to file"""

        try:
            import json

            # Convert Q-table to serializable format
            serializable_q_table = {}
            for state_key, actions in self.q_table.items():
                serializable_q_table[state_key] = dict(actions)

            with open(filepath, 'w') as f:
                json.dump(serializable_q_table, f, indent=2)

            logger.info(f"💾 Q-table saved: {filepath}")
            return True

        except ValuationEngineError as e:
            logger.error(f"❌ Q-table saving failed: {str(e)}")
            return False

    def load_q_table(self, filepath: str) -> bool:
        """Load Q-table from file"""

        try:
            import json

            with open(filepath, 'r') as f:
                serializable_q_table = json.load(f)

            # Convert back to Q-table format
            self.q_table.clear()
            for state_key, actions in serializable_q_table.items():
                for action_str, q_value in actions.items():
                    action = RLAction(action_str)
                    self.q_table[state_key][action] = q_value

            logger.info(f"📂 Q-table loaded: {filepath}")
            return True

        except ValuationEngineError as e:
            logger.error(f"❌ Q-table loading failed: {str(e)}")
            return False

    def update_learning_rate(self, new_rate: Decimal):
        """Update learning rate"""

        try:
            old_rate = self.learning_rate
            self.learning_rate = max(Decimal('0.001'), min(Decimal('1.0'), new_rate))

            if old_rate != self.learning_rate:
                logger.info(f"📈 Learning rate updated: {old_rate:.3f} → {self.learning_rate:.3f}")

        except ConfigurationError as e:
            logger.error(f"❌ Learning rate update failed: {str(e)}")

    def get_exploration_info(self) -> Dict[str, Decimal]:
        """Get exploration information"""

        try:
            return {
                "current_epsilon": self.epsilon,
                "min_epsilon": self.config.epsilon_min,
                "decay_rate": self.config.epsilon_decay,
                "exploration_rate": self.epsilon,
                "exploitation_rate": Decimal('1.0') - self.epsilon,
                "steps_until_min": math.ceil(math.log(self.config.epsilon_min / self.epsilon) / math.log(self.config.epsilon_decay)) if self.epsilon > self.config.epsilon_min else 0
            }

        except ConfigurationError as e:
            logger.error(f"❌ Exploration info retrieval failed: {str(e)}")
            return {
                "current_epsilon": self.epsilon,
                "min_epsilon": self.config.epsilon_min,
                "decay_rate": self.config.epsilon_decay,
                "exploration_rate": self.epsilon,
                "exploitation_rate": Decimal('1.0') - self.epsilon,
                "steps_until_min": 0
            }
