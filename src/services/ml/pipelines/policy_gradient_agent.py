from src.utils.exceptions import CalculationError, ConfigurationError, InvalidDiscountError

"""
Policy Gradient Agent

This module implements policy gradient algorithms for reinforcement learning
in valuation optimization. Includes policy network, action probability calculation,
and gradient updates with baseline estimation.

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
    RLAction, RLState, RLExperience, PolicyGradientConfig,
    DEFAULT_PG_CONFIG, ACTION_TO_INDEX, INDEX_TO_ACTION
)

logger = get_logger(__name__)


class PolicyGradientAgent:
    """Policy gradient agent for valuation optimization"""

    def __init__(self, config: Optional[PolicyGradientConfig] = None):
        """Initialize policy gradient agent"""
        self.config = config or DEFAULT_PG_CONFIG
        self.policy_table = defaultdict(lambda: defaultdict(float))
        self.baseline = defaultdict(float)
        self.baseline_decay = self.config.baseline_decay
        self.learning_rate = self.config.learning_rate
        self.entropy_coefficient = self.config.entropy_coefficient
        self.episode_count = 0
        self.step_count = 0
        self.total_reward = Decimal('0.0')

        logger.info("✅ PolicyGradientAgent initialized")

    def get_action_probabilities(self, state: RLState) -> Dict[RLAction, Decimal]:
        """Get action probabilities from policy"""

        try:
            logger.info(f"🎯 Getting action probabilities for state: {state.business_type}")

            state_key = self._state_to_key(state)
            policy_logits = self.policy_table[state_key]

            if not policy_logits:
                # No policy for this state, return uniform probabilities
                uniform_prob = Decimal('1.0') / len(RLAction)
                return {action: uniform_prob for action in RLAction}

            # Convert logits to probabilities using softmax
            logits = np.array([policy_logits.get(action, Decimal('0.0')) for action in RLAction])

            # Apply softmax with temperature
            exp_logits = np.exp(logits - np.max(logits))  # Numerical stability
            probabilities = exp_logits / np.sum(exp_logits)

            # Ensure minimum probability
            probabilities = np.maximum(probabilities, self.config.min_probability)
            probabilities = probabilities / np.sum(probabilities)  # Renormalize

            # Convert to dictionary
            action_probs = {action: to_decimal(prob) for action, prob in zip(RLAction, probabilities)}

            logger.info(f"✅ Action probabilities computed: {len(action_probs)} actions")
            return action_probs

        except ConfigurationError as e:
            logger.error(f"❌ Action probability computation failed: {str(e)}")
            # Return uniform probabilities as fallback
            uniform_prob = Decimal('1.0') / len(RLAction)
            return {action: uniform_prob for action in RLAction}

    def get_action(self, state: RLState) -> RLAction:
        """Get action by sampling from policy"""

        try:
            action_probs = self.get_action_probabilities(state)

            # Sample action from probability distribution
            actions = list(action_probs.keys())
            probabilities = list(action_probs.values())

            action = np.random.choice(actions, p=probabilities)

            self.step_count += 1
            logger.info(f"🎲 Sampled action: {action}")
            return action

        except ValuationEngineError as e:
            logger.error(f"❌ Action sampling failed: {str(e)}")
            return random.choice(list(RLAction))

    def update_policy(self, experiences: List[RLExperience]):
        """Update policy using policy gradient"""

        try:
            logger.info(f"🔄 Updating policy with {len(experiences)} experiences")

            if not experiences:
                logger.warning("⚠️ No experiences provided for policy update")
                return

            # Calculate returns and advantages
            returns = self._calculate_returns(experiences)
            advantages = self._calculate_advantages(experiences, returns)

            # Update policy for each experience
            for i, experience in enumerate(experiences):
                state_key = self._state_to_key(experience.state)
                action = experience.action
                advantage = advantages[i]

                # Get current policy logits
                current_logits = self.policy_table[state_key]

                # Calculate policy gradient
                action_probs = self.get_action_probabilities(experience.state)
                action_prob = action_probs[action]

                # Policy gradient: ∇log π(a|s) * A(s,a)
                policy_gradient = advantage / max(action_prob, self.config.min_probability)

                # Update policy logits
                current_logits[action] += self.learning_rate * policy_gradient

                # Apply entropy regularization
                entropy_bonus = self.entropy_coefficient * np.log(action_prob)
                current_logits[action] += entropy_bonus

                # Update baseline
                self.baseline[state_key] = (
                    self.baseline_decay * self.baseline[state_key] +
                    (1 - self.baseline_decay) * returns[i]
                )

            # Update statistics
            self.total_reward += sum(exp.reward for exp in experiences)

            logger.info(f"✅ Policy updated with {len(experiences)} experiences")

        except InvalidDiscountError as e:
            logger.error(f"❌ Policy update failed: {str(e)}")

    def _calculate_returns(self, experiences: List[RLExperience]) -> List[Decimal]:
        """Calculate discounted returns for experiences"""

        try:
            returns = []
            discount_factor = Decimal('0.99')  # Can be made configurable

            # Calculate returns in reverse order
            running_return = Decimal('0.0')
            for experience in reversed(experiences):
                running_return = experience.reward + discount_factor * running_return
                returns.insert(0, running_return)

            return returns

        except InvalidDiscountError as e:
            logger.error(f"❌ Return calculation failed: {str(e)}")
            return [exp.reward for exp in experiences]

    def _calculate_advantages(self, experiences: List[RLExperience], returns: List[Decimal]) -> List[Decimal]:
        """Calculate advantages using baseline"""

        try:
            advantages = []

            for i, experience in enumerate(experiences):
                state_key = self._state_to_key(experience.state)
                baseline_value = self.baseline[state_key]
                advantage = returns[i] - baseline_value
                advantages.append(advantage)

            return advantages

        except CalculationError as e:
            logger.error(f"❌ Advantage calculation failed: {str(e)}")
            return returns  # Fallback to returns

    def _state_to_key(self, state: RLState) -> str:
        """Convert state to string key for policy table"""

        try:
            # Create a hashable key from state
            state_vector = state.to_vector()
            # Round to avoid floating point precision issues
            rounded_vector = np.round(state_vector, 3)
            return str(tuple(rounded_vector))

        except ValuationEngineError as e:
            logger.error(f"❌ State key conversion failed: {str(e)}")
            return "default_state"

    def get_policy_entropy(self, state: RLState) -> Decimal:
        """Calculate policy entropy for a state"""

        try:
            action_probs = self.get_action_probabilities(state)
            probabilities = list(action_probs.values())

            # Calculate entropy: -Σ p(a) * log p(a)
            entropy = -sum(p * np.log(max(p, self.config.min_probability)) for p in probabilities)

            return to_decimal(entropy)

        except ConfigurationError as e:
            logger.error(f"❌ Policy entropy calculation failed: {str(e)}")
            return Decimal('0.0')

    def get_policy_value(self, state: RLState, action: RLAction) -> Decimal:
        """Get policy value for state-action pair"""

        try:
            state_key = self._state_to_key(state)
            return self.policy_table[state_key][action]

        except ValuationEngineError as e:
            logger.error(f"❌ Policy value retrieval failed: {str(e)}")
            return Decimal('0.0')

    def get_baseline_value(self, state: RLState) -> Decimal:
        """Get baseline value for a state"""

        try:
            state_key = self._state_to_key(state)
            return self.baseline[state_key]

        except ValuationEngineError as e:
            logger.error(f"❌ Baseline value retrieval failed: {str(e)}")
            return Decimal('0.0')

    def get_agent_statistics(self) -> Dict[str, Any]:
        """Get agent performance statistics"""

        try:
            # Calculate policy statistics
            all_policy_values = []
            all_baseline_values = []
            all_entropies = []

            for state_key, policy_logits in self.policy_table.items():
                all_policy_values.extend(policy_logits.values())
                all_baseline_values.append(self.baseline[state_key])

                # Calculate entropy for this state
                if policy_logits:
                    probs = list(policy_logits.values())
                    exp_probs = np.exp(probs - np.max(probs))
                    exp_probs = exp_probs / np.sum(exp_probs)
                    entropy = -sum(p * np.log(max(p, self.config.min_probability)) for p in exp_probs)
                    all_entropies.append(entropy)

            # Calculate statistics
            policy_mean = np.mean(all_policy_values) if all_policy_values else Decimal('0.0')
            policy_std = np.std(all_policy_values) if all_policy_values else Decimal('0.0')
            baseline_mean = np.mean(all_baseline_values) if all_baseline_values else Decimal('0.0')
            entropy_mean = np.mean(all_entropies) if all_entropies else Decimal('0.0')

            # Calculate average reward
            avg_reward = self.total_reward / max(self.step_count, 1)

            statistics = {
                "episode_count": self.episode_count,
                "step_count": self.step_count,
                "total_reward": self.total_reward,
                "average_reward": avg_reward,
                "learning_rate": self.learning_rate,
                "entropy_coefficient": self.entropy_coefficient,
                "policy_table_size": len(self.policy_table),
                "policy_value_mean": policy_mean,
                "policy_value_std": policy_std,
                "baseline_mean": baseline_mean,
                "entropy_mean": entropy_mean,
                "baseline_decay": self.baseline_decay
            }

            logger.info(f"📊 Agent statistics computed: {len(self.policy_table)} states")
            return statistics

        except ValuationEngineError as e:
            logger.error(f"❌ Statistics computation failed: {str(e)}")
            return {
                "episode_count": 0,
                "step_count": 0,
                "total_reward": Decimal('0.0'),
                "average_reward": Decimal('0.0'),
                "learning_rate": self.learning_rate,
                "entropy_coefficient": self.entropy_coefficient,
                "policy_table_size": 0,
                "policy_value_mean": Decimal('0.0'),
                "policy_value_std": Decimal('0.0'),
                "baseline_mean": Decimal('0.0'),
                "entropy_mean": Decimal('0.0'),
                "baseline_decay": self.baseline_decay
            }

    def reset_agent(self):
        """Reset agent to initial state"""

        try:
            logger.info("🔄 Resetting policy gradient agent")

            self.policy_table.clear()
            self.baseline.clear()
            self.episode_count = 0
            self.step_count = 0
            self.total_reward = Decimal('0.0')

            logger.info("✅ Policy gradient agent reset")

        except ConfigurationError as e:
            logger.error(f"❌ Agent reset failed: {str(e)}")

    def save_policy(self, filepath: str) -> bool:
        """Save policy to file"""

        try:
            import json

            # Convert policy table to serializable format
            serializable_policy = {}
            for state_key, policy_logits in self.policy_table.items():
                serializable_policy[state_key] = {action.value: logit for action, logit in policy_logits.items()}

            # Include baseline values
            serializable_baseline = {state_key: value for state_key, value in self.baseline.items()}

            policy_data = {
                "policy_table": serializable_policy,
                "baseline": serializable_baseline,
                "config": {
                    "learning_rate": self.learning_rate,
                    "entropy_coefficient": self.entropy_coefficient,
                    "baseline_decay": self.baseline_decay
                }
            }

            with open(filepath, 'w') as f:
                json.dump(policy_data, f, indent=2)

            logger.info(f"💾 Policy saved: {filepath}")
            return True

        except ValuationEngineError as e:
            logger.error(f"❌ Policy saving failed: {str(e)}")
            return False

    def load_policy(self, filepath: str) -> bool:
        """Load policy from file"""

        try:
            import json

            with open(filepath, 'r') as f:
                policy_data = json.load(f)

            # Load policy table
            self.policy_table.clear()
            for state_key, policy_logits in policy_data["policy_table"].items():
                for action_str, logit in policy_logits.items():
                    action = RLAction(action_str)
                    self.policy_table[state_key][action] = logit

            # Load baseline
            self.baseline.clear()
            for state_key, value in policy_data["baseline"].items():
                self.baseline[state_key] = value

            # Load config if available
            if "config" in policy_data:
                config = policy_data["config"]
                self.learning_rate = config.get("learning_rate", self.learning_rate)
                self.entropy_coefficient = config.get("entropy_coefficient", self.entropy_coefficient)
                self.baseline_decay = config.get("baseline_decay", self.baseline_decay)

            logger.info(f"📂 Policy loaded: {filepath}")
            return True

        except ConfigurationError as e:
            logger.error(f"❌ Policy loading failed: {str(e)}")
            return False

    def update_learning_rate(self, new_rate: Decimal):
        """Update learning rate"""

        try:
            old_rate = self.learning_rate
            self.learning_rate = max(Decimal('0.001'), min(Decimal('1.0'), new_rate))

            if old_rate != self.learning_rate:
                logger.info(f"📈 Learning rate updated: {old_rate:.3f} → {self.learning_rate:.3f}")

        except ValuationEngineError as e:
            logger.error(f"❌ Learning rate update failed: {str(e)}")

    def get_policy_info(self, state: RLState) -> Dict[str, Any]:
        """Get detailed policy information for a state"""

        try:
            action_probs = self.get_action_probabilities(state)
            entropy = self.get_policy_entropy(state)
            baseline = self.get_baseline_value(state)

            return {
                "action_probabilities": action_probs,
                "entropy": entropy,
                "baseline": baseline,
                "state_key": self._state_to_key(state),
                "policy_logits": dict(self.policy_table[self._state_to_key(state)])
            }

        except ValuationEngineError as e:
            logger.error(f"❌ Policy info retrieval failed: {str(e)}")
            return {
                "action_probabilities": {},
                "entropy": Decimal('0.0'),
                "baseline": Decimal('0.0'),
                "state_key": "error",
                "policy_logits": {}
            }
