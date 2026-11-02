"""
RL Orchestrator

This module orchestrates multiple reinforcement learning agents for
valuation optimization. Includes ensemble decision making, experience
collection, reward calculation, and performance tracking.

Author: Upswitch CTO Team
Date: October 2025
Status: Production Ready
"""

import random
from collections import deque
from decimal import Decimal
from typing import Any, Dict, Optional

from src.utils.logging import get_logger

from .bandit_algorithms import ContextualBandit, MultiArmedBandit
from .policy_gradient_agent import PolicyGradientAgent
from .q_learning_agent import QLearningAgent
from .rl_reward_policy import calculate_rl_reward
from .rl_types import (
    ACTION_TO_INDEX,
    INDEX_TO_ACTION,
    RLAction,
    RLExperience,
    RLPerformanceMetrics,
    RLState,
)

logger = get_logger(__name__)


class RLOrchestrator:
    """Orchestrates multiple RL agents for ensemble decision making"""

    def __init__(
        self,
        q_learning_agent: Optional[QLearningAgent] = None,
        policy_gradient_agent: Optional[PolicyGradientAgent] = None,
        multi_armed_bandit: Optional[MultiArmedBandit] = None,
        contextual_bandit: Optional[ContextualBandit] = None,
    ):
        """Initialize RL orchestrator"""
        self.q_learning_agent = q_learning_agent or QLearningAgent()
        self.policy_gradient_agent = policy_gradient_agent or PolicyGradientAgent()
        self.multi_armed_bandit = multi_armed_bandit or MultiArmedBandit(
            arms=[action.value for action in RLAction]
        )
        self.contextual_bandit = contextual_bandit or ContextualBandit(feature_dim=7, num_arms=8)

        # Experience management
        self.experience_buffer = deque(maxlen=10000)
        self.episode_experiences = []
        self.performance_metrics = RLPerformanceMetrics()

        # Ensemble weights (can be learned)
        self.ensemble_weights = {
            "q_learning": Decimal("0.3"),
            "policy_gradient": Decimal("0.3"),
            "multi_armed_bandit": Decimal("0.2"),
            "contextual_bandit": Decimal("0.2"),
        }

        logger.info("✅ RLOrchestrator initialized")

    def get_action(self, state: RLState) -> RLAction:
        """Get ensemble action from all agents"""

        try:
            logger.info(f"🎯 Getting ensemble action for state: {state.business_type}")

            # Get actions from all agents
            actions = {}

            # Q-learning action
            ql_action = self.q_learning_agent.get_action(state)
            actions["q_learning"] = ql_action

            # Policy gradient action
            pg_action = self.policy_gradient_agent.get_action(state)
            actions["policy_gradient"] = pg_action

            # Multi-armed bandit action
            mab_arm = self.multi_armed_bandit.select_arm()
            mab_action = RLAction(mab_arm)
            actions["multi_armed_bandit"] = mab_action

            # Contextual bandit action
            context_vector = state.to_vector()
            cb_arm = self.contextual_bandit.select_arm(context_vector)
            cb_action = INDEX_TO_ACTION.get(cb_arm, random.choice(list(RLAction)))
            actions["contextual_bandit"] = cb_action

            # Ensemble decision
            ensemble_action = self._ensemble_decision(actions, state)

            logger.info(f"✅ Ensemble action selected: {ensemble_action}")
            return ensemble_action

        except Exception as e:
            logger.error(f"❌ Ensemble action selection failed: {str(e)}")
            return random.choice(list(RLAction))

    def _ensemble_decision(self, actions: Dict[str, RLAction], state: RLState) -> RLAction:
        """Make ensemble decision from multiple agent actions"""

        try:
            # Count votes for each action
            action_votes = {}
            for agent_name, action in actions.items():
                weight = self.ensemble_weights.get(agent_name, Decimal("0.25"))
                if action not in action_votes:
                    action_votes[action] = Decimal("0.0")
                action_votes[action] += weight

            # Select action with highest weighted vote
            best_action = max(action_votes.keys(), key=lambda a: action_votes[a])

            # Handle ties by random selection
            max_votes = action_votes[best_action]
            tied_actions = [a for a, votes in action_votes.items() if votes == max_votes]

            if len(tied_actions) > 1:
                best_action = random.choice(tied_actions)

            logger.info(f"🗳️ Ensemble decision: {best_action} (votes: {action_votes})")
            return best_action

        except Exception as e:
            logger.error(f"❌ Ensemble decision failed: {str(e)}")
            return random.choice(list(RLAction))

    def update_agents(self, experience: RLExperience):
        """Update all agents with new experience"""

        try:
            logger.info(f"🔄 Updating agents with experience: {experience.action}")

            # Add to experience buffer
            self.experience_buffer.append(experience)
            self.episode_experiences.append(experience)

            # Update Q-learning agent
            self.q_learning_agent.update_q_value(experience)

            # Update policy gradient agent (batch update)
            if len(self.episode_experiences) >= 10:  # Batch size
                self.policy_gradient_agent.update_policy(self.episode_experiences)
                self.episode_experiences.clear()

            # Update multi-armed bandit
            arm_name = experience.action.value
            self.multi_armed_bandit.update_arm(arm_name, experience.reward)

            # Update contextual bandit
            context_vector = experience.state.to_vector()
            arm_index = ACTION_TO_INDEX.get(experience.action, 0)
            self.contextual_bandit.update_arm(arm_index, context_vector, experience.reward)

            # Update performance metrics
            self._update_performance_metrics(experience)

            logger.info("✅ All agents updated")

        except Exception as e:
            logger.error(f"❌ Agent update failed: {str(e)}")

    def _update_performance_metrics(self, experience: RLExperience):
        """Update performance metrics"""

        try:
            self.performance_metrics.total_reward += experience.reward
            self.performance_metrics.step_count += 1
            self.performance_metrics.average_reward = (
                self.performance_metrics.total_reward / self.performance_metrics.step_count
            )

            # Update episode count if episode ended
            if experience.done:
                self.performance_metrics.episode_count += 1

                # Decay exploration rates
                self.q_learning_agent.decay_epsilon()

        except Exception as e:
            logger.error(f"❌ Performance metrics update failed: {str(e)}")

    def calculate_reward(
        self,
        action: RLAction,
        state: RLState,
        next_state: Optional[RLState],
        user_feedback: Optional[Dict[str, Any]] = None,
    ) -> Decimal:
        """Calculate reward for action"""

        try:
            logger.info(f"💰 Calculating reward for action: {action}")

            base_reward = calculate_rl_reward(action, state, user_feedback)

            logger.info(f"✅ Reward calculated: {base_reward:.3f}")
            return base_reward

        except Exception as e:
            logger.error(f"❌ Reward calculation failed: {str(e)}")
            return Decimal("0.0")

    def get_agent_statistics(self) -> Dict[str, Any]:
        """Get statistics from all agents"""

        try:
            logger.info("📊 Computing agent statistics")

            # Get individual agent statistics
            ql_stats = self.q_learning_agent.get_agent_statistics()
            pg_stats = self.policy_gradient_agent.get_agent_statistics()
            mab_stats = self.multi_armed_bandit.get_arm_statistics()
            cb_stats = self.contextual_bandit.get_arm_statistics()

            # Calculate ensemble statistics
            ensemble_stats = {
                "total_experiences": len(self.experience_buffer),
                "episode_count": self.performance_metrics.episode_count,
                "step_count": self.performance_metrics.step_count,
                "total_reward": self.performance_metrics.total_reward,
                "average_reward": self.performance_metrics.average_reward,
                "ensemble_weights": self.ensemble_weights,
                "performance_metrics": {
                    "total_reward": self.performance_metrics.total_reward,
                    "average_reward": self.performance_metrics.average_reward,
                    "episode_count": self.performance_metrics.episode_count,
                    "step_count": self.performance_metrics.step_count,
                },
            }

            statistics = {
                "q_learning": ql_stats,
                "policy_gradient": pg_stats,
                "multi_armed_bandit": mab_stats,
                "contextual_bandit": cb_stats,
                "ensemble": ensemble_stats,
            }

            logger.info("✅ Agent statistics computed")
            return statistics

        except Exception as e:
            logger.error(f"❌ Statistics computation failed: {str(e)}")
            return {
                "q_learning": {},
                "policy_gradient": {},
                "multi_armed_bandit": {},
                "contextual_bandit": {},
                "ensemble": {},
            }

    def update_ensemble_weights(self, new_weights: Dict[str, Decimal]):
        """Update ensemble weights"""

        try:
            logger.info(f"🔄 Updating ensemble weights: {new_weights}")

            # Validate weights
            total_weight = sum(new_weights.values())
            if abs(total_weight - Decimal("1.0")) > 0.01:
                logger.warning(f"⚠️ Weights don't sum to 1.0: {total_weight}")
                # Normalize weights
                for agent in new_weights:
                    new_weights[agent] /= total_weight

            self.ensemble_weights.update(new_weights)

            logger.info(f"✅ Ensemble weights updated: {self.ensemble_weights}")

        except Exception as e:
            logger.error(f"❌ Ensemble weights update failed: {str(e)}")

    def reset_orchestrator(self):
        """Reset all agents and orchestrator"""

        try:
            logger.info("🔄 Resetting RL orchestrator")

            # Reset individual agents
            self.q_learning_agent.reset_agent()
            self.policy_gradient_agent.reset_agent()
            self.multi_armed_bandit.reset_bandit()
            self.contextual_bandit.reset_bandit()

            # Reset orchestrator state
            self.experience_buffer.clear()
            self.episode_experiences.clear()
            self.performance_metrics = RLPerformanceMetrics()

            logger.info("✅ RL orchestrator reset")

        except Exception as e:
            logger.error(f"❌ Orchestrator reset failed: {str(e)}")

    def get_best_agent(self) -> str:
        """Get the best performing agent"""

        try:
            # Get performance from each agent
            ql_stats = self.q_learning_agent.get_agent_statistics()
            pg_stats = self.policy_gradient_agent.get_agent_statistics()

            # Compare average rewards
            ql_reward = ql_stats.get("average_reward", Decimal("0.0"))
            pg_reward = pg_stats.get("average_reward", Decimal("0.0"))

            if ql_reward > pg_reward:
                return "q_learning"
            else:
                return "policy_gradient"

        except Exception as e:
            logger.error(f"❌ Best agent selection failed: {str(e)}")
            return "q_learning"

    def get_exploration_info(self) -> Dict[str, Any]:
        """Get exploration information from all agents"""

        try:
            ql_exploration = self.q_learning_agent.get_exploration_info()

            exploration_info = {
                "q_learning": ql_exploration,
                "policy_gradient": {
                    "entropy_coefficient": self.policy_gradient_agent.entropy_coefficient,
                    "learning_rate": self.policy_gradient_agent.learning_rate,
                },
                "multi_armed_bandit": {
                    "exploration_rate": self.multi_armed_bandit.config.exploration_rate,
                    "confidence_level": self.multi_armed_bandit.config.confidence_level,
                },
                "contextual_bandit": {
                    "confidence_width": self.contextual_bandit.confidence_width,
                    "learning_rate": self.contextual_bandit.learning_rate,
                },
            }

            return exploration_info

        except Exception as e:
            logger.error(f"❌ Exploration info retrieval failed: {str(e)}")
            return {}

    def save_models(self, base_path: str) -> bool:
        """Save all agent models"""

        try:
            logger.info(f"💾 Saving models to: {base_path}")

            # Save individual models
            ql_success = self.q_learning_agent.save_q_table(f"{base_path}_ql.json")
            pg_success = self.policy_gradient_agent.save_policy(f"{base_path}_pg.json")

            # Save ensemble weights
            import json

            with open(f"{base_path}_ensemble.json", "w") as f:
                json.dump(self.ensemble_weights, f, indent=2)

            success = ql_success and pg_success

            if success:
                logger.info("✅ All models saved successfully")
            else:
                logger.warning("⚠️ Some models failed to save")

            return success

        except Exception as e:
            logger.error(f"❌ Model saving failed: {str(e)}")
            return False

    def load_models(self, base_path: str) -> bool:
        """Load all agent models"""

        try:
            logger.info(f"📂 Loading models from: {base_path}")

            # Load individual models
            ql_success = self.q_learning_agent.load_q_table(f"{base_path}_ql.json")
            pg_success = self.policy_gradient_agent.load_policy(f"{base_path}_pg.json")

            # Load ensemble weights
            import json

            try:
                with open(f"{base_path}_ensemble.json", "r") as f:
                    self.ensemble_weights = json.load(f)
            except FileNotFoundError:
                logger.warning("⚠️ Ensemble weights file not found, using defaults")

            success = ql_success and pg_success

            if success:
                logger.info("✅ All models loaded successfully")
            else:
                logger.warning("⚠️ Some models failed to load")

            return success

        except Exception as e:
            logger.error(f"❌ Model loading failed: {str(e)}")
            return False
