from src.utils.exceptions import DCFCalculationError, DataValidationError, InvalidDiscountError, MethodologyError, MultiplesCalculationError

"""
Reinforcement Learning for ML Valuation Engine

This module provides reinforcement learning capabilities for
adaptive methodology selection and continuous learning from
valuation outcomes and user feedback.
"""

from typing import Dict, Any, List, Optional, Tuple, Union
import numpy as np
import pandas as pd
from datetime import datetime
import random
import json

from src.utils.logging import get_logger
from decimal import Decimal
from src.utils.decimal_helpers import to_decimal, from_decimal
from src.services.ml.ml_types import (
    MLModelType, ValuationMethodology, ReinforcementLearningState,
    ModelMetrics, TrainingData, ModelConfiguration
)

logger = get_logger(__name__)


class QLearningAgent:
    """
    Q-Learning agent for valuation methodology selection.

    Implements Q-learning algorithm to learn optimal methodology
    selection based on valuation outcomes and user feedback.
    """

    def __init__(self, state_size: int, action_size: int, learning_rate: Decimal = Decimal('0.1'), 
                 discount_factor: Decimal = Decimal('0.9'), epsilon: Decimal = Decimal('0.1')):
        """
        Initialize Q-Learning agent.

        Args:
            state_size: Number of state features
            action_size: Number of possible actions (methodologies)
            learning_rate: Learning rate for Q-value updates
            discount_factor: Discount factor for future rewards
            epsilon: Exploration rate
        """
        self.state_size = state_size
        self.action_size = action_size
        self.learning_rate = learning_rate
        self.discount_factor = discount_factor
        self.epsilon = epsilon

        # Q-table
        self.q_table = np.zeros((state_size, action_size))

        # Experience replay buffer
        self.experience_buffer = []
        self.buffer_size = 10000

        # Performance tracking
        self.episode_rewards = []
        self.episode_lengths = []
        self.learning_history = []

        self.logger = logger

    def get_action(self, state: int, training: bool = True) -> int:
        """
        Get action using epsilon-greedy policy.

        Args:
            state: Current state
            training: Whether in training mode

        Returns:
            Selected action
        """
        try:
            if training and random.random() < self.epsilon:
                # Exploration
                action = random.randint(0, self.action_size - 1)
            else:
                # Exploitation
                action = np.argmax(self.q_table[state])

            return action

        except DataValidationError as e:
            self.logger.error(f"Error getting action: {e}")
            return 0

    def update_q_value(self, state: int, action: int, reward: Decimal, next_state: int):
        """
        Update Q-value using Q-learning update rule.

        Args:
            state: Current state
            action: Action taken
            reward: Reward received
            next_state: Next state
        """
        try:
            # Q-learning update rule
            current_q = self.q_table[state, action]
            max_next_q = np.max(self.q_table[next_state])

            new_q = current_q + self.learning_rate * (
                reward + self.discount_factor * max_next_q - current_q
            )

            self.q_table[state, action] = new_q

        except InvalidDiscountError as e:
            self.logger.error(f"Error updating Q-value: {e}")

    def store_experience(self, state: int, action: int, reward: Decimal, next_state: int, done: bool):
        """
        Store experience in replay buffer.

        Args:
            state: Current state
            action: Action taken
            reward: Reward received
            next_state: Next state
            done: Whether episode is done
        """
        try:
            experience = {
                'state': state,
                'action': action,
                'reward': reward,
                'next_state': next_state,
                'done': done,
                'timestamp': datetime.utcnow()
            }

            self.experience_buffer.append(experience)

            # Maintain buffer size
            if len(self.experience_buffer) > self.buffer_size:
                self.experience_buffer.pop(0)

        except ValuationEngineError as e:
            self.logger.error(f"Error storing experience: {e}")

    def decay_epsilon(self, decay_rate: Decimal = Decimal('0.995'), min_epsilon: Decimal = Decimal('0.01')):
        """Decay exploration rate"""
        self.epsilon = max(min_epsilon, self.epsilon * decay_rate)

    def get_q_values(self, state: int) -> np.ndarray:
        """Get Q-values for a state"""
        return self.q_table[state]


class ReinforcementLearningEngine:
    """
    Reinforcement learning engine for valuation methodology selection.

    Provides RL capabilities including:
    - Q-learning for methodology selection
    - Experience replay for learning
    - Reward shaping for valuation outcomes
    - Continuous learning from feedback
    """

    def __init__(self):
        """Initialize the reinforcement learning engine"""
        self.logger = logger

        # RL agents
        self.q_learning_agent = None
        self.state_encoder = None
        self.reward_calculator = None

        # Learning configuration
        self.learning_config = self._initialize_learning_config()

        # Performance tracking
        self.learning_history = []
        self.performance_metrics = []

        # State and action mappings
        self.state_mapping = {}
        self.action_mapping = {
            0: ValuationMethodology.DCF,
            1: ValuationMethodology.MULTIPLES,
            2: ValuationMethodology.ASSET_BASED,
            3: ValuationMethodology.HYBRID
        }

    async def initialize_learning(
        self,
        state_features: List[str],
        learning_rate: Decimal = Decimal('0.1'),
        discount_factor: Decimal = Decimal('0.9'),
        epsilon: Decimal = Decimal('0.1')
    ):
        """
        Initialize reinforcement learning system.

        Args:
            state_features: List of state feature names
            learning_rate: Learning rate for Q-learning
            discount_factor: Discount factor for future rewards
            epsilon: Initial exploration rate
        """
        try:
            self.logger.info("Initializing reinforcement learning system")

            # Create state encoder
            self.state_encoder = StateEncoder(state_features)

            # Create Q-learning agent
            state_size = len(state_features)
            action_size = len(self.action_mapping)
            self.q_learning_agent = QLearningAgent(
                state_size=state_size,
                action_size=action_size,
                learning_rate=learning_rate,
                discount_factor=discount_factor,
                epsilon=epsilon
            )

            # Create reward calculator
            self.reward_calculator = RewardCalculator()

            self.logger.info(
                "Reinforcement learning system initialized",
                state_size=state_size,
                action_size=action_size,
                learning_rate=learning_rate
            )

        except MethodologyError as e:
            self.logger.error(f"Error initializing reinforcement learning: {e}")
            raise

    async def select_methodology(
        self,
        state_features: Dict[str, Decimal],
        training: bool = True
    ) -> Tuple[ValuationMethodology, float]:
        """
        Select valuation methodology using RL.

        Args:
            state_features: Current state features
            training: Whether in training mode

        Returns:
            Selected methodology and confidence
        """
        try:
            if not self.q_learning_agent:
                raise ValueError("RL system not initialized")

            # Encode state
            state = self.state_encoder.encode_state(state_features)

            # Get action from Q-learning agent
            action = self.q_learning_agent.get_action(state, training)

            # Get methodology
            methodology = self.action_mapping[action]

            # Get confidence from Q-values
            q_values = self.q_learning_agent.get_q_values(state)
            confidence = to_decimal(np.max(q_values) / np.sum(q_values)) if np.sum(q_values) > 0 else Decimal('0.25')

            self.logger.debug(
                "Methodology selected using RL",
                methodology=methodology.value,
                confidence=confidence,
                action=action
            )

            return methodology, confidence

        except MultiplesCalculationError as e:
            self.logger.error(f"Error selecting methodology: {e}")
            # Fallback to default methodology
            return ValuationMethodology.MULTIPLES, Decimal('0.5')

    async def update_learning(
        self,
        state_features: Dict[str, Decimal],
        selected_methodology: ValuationMethodology,
        valuation_outcome: Dict[str, Any],
        user_feedback: Optional[Dict[str, Any]] = None
    ):
        """
        Update learning based on valuation outcome.

        Args:
            state_features: State features when methodology was selected
            selected_methodology: Methodology that was selected
            valuation_outcome: Outcome of the valuation
            user_feedback: User feedback (optional)
        """
        try:
            if not self.q_learning_agent:
                return

            # Encode state
            state = self.state_encoder.encode_state(state_features)

            # Get action index
            action = next(
                (idx for idx, method in self.action_mapping.items() 
                 if method == selected_methodology), 0
            )

            # Calculate reward
            reward = self.reward_calculator.calculate_reward(
                valuation_outcome, user_feedback
            )

            # Simulate next state (in practice, this would be the actual next state)
            next_state = state  # Simplified

            # Update Q-learning agent
            self.q_learning_agent.update_q_value(state, action, reward, next_state)

            # Store experience
            self.q_learning_agent.store_experience(
                state, action, reward, next_state, done=True
            )

            # Decay exploration rate
            self.q_learning_agent.decay_epsilon()

            # Track learning progress
            self.learning_history.append({
                'state': state,
                'action': action,
                'reward': reward,
                'methodology': selected_methodology.value,
                'timestamp': datetime.utcnow()
            })

            self.logger.debug(
                "Learning updated",
                reward=reward,
                methodology=selected_methodology.value,
                exploration_rate=self.q_learning_agent.epsilon
            )

        except MethodologyError as e:
            self.logger.error(f"Error updating learning: {e}")

    async def train_episode(
        self,
        training_data: List[Dict[str, Any]],
        episodes: int = 100
    ) -> Dict[str, Any]:
        """
        Train RL agent on historical data.

        Args:
            training_data: Historical valuation data
            episodes: Number of training episodes

        Returns:
            Training results
        """
        try:
            self.logger.info("Starting RL training", episodes=episodes)

            episode_rewards = []
            episode_lengths = []

            for episode in range(episodes):
                episode_reward = 0
                episode_length = 0

                # Shuffle training data
                random.shuffle(training_data)

                for data_point in training_data:
                    # Extract state features
                    state_features = self._extract_state_features(data_point)

                    # Select methodology
                    methodology, confidence = await self.select_methodology(
                        state_features, training=True
                    )

                    # Simulate outcome (in practice, this would be actual outcome)
                    outcome = self._simulate_outcome(data_point, methodology)

                    # Calculate reward
                    reward = self.reward_calculator.calculate_reward(outcome)

                    # Update learning
                    await self.update_learning(
                        state_features, methodology, outcome
                    )

                    episode_reward += reward
                    episode_length += 1

                episode_rewards.append(episode_reward)
                episode_lengths.append(episode_length)

                if episode % 10 == 0:
                    avg_reward = np.mean(episode_rewards[-10:])
                    self.logger.info(
                        f"Episode {episode}, Average Reward: {avg_reward:.3f}"
                    )

            # Calculate final metrics
            final_metrics = {
                'episodes': episodes,
                'final_avg_reward': np.mean(episode_rewards[-10:]),
                'final_avg_length': np.mean(episode_lengths[-10:]),
                'total_experiences': len(self.q_learning_agent.experience_buffer),
                'final_epsilon': self.q_learning_agent.epsilon
            }

            self.logger.info(
                "RL training completed",
                final_avg_reward=final_metrics['final_avg_reward'],
                final_epsilon=final_metrics['final_epsilon']
            )

            return final_metrics

        except ValuationEngineError as e:
            self.logger.error(f"Error training RL agent: {e}")
            raise

    def _extract_state_features(self, data_point: Dict[str, Any]) -> Dict[str, Decimal]:
        """Extract state features from data point"""
        try:
            features = {}

            # Financial features
            features['revenue'] = data_point.get('revenue', 0) / 1_000_000  # Normalize to millions
            features['ebitda'] = data_point.get('ebitda', 0) / 1_000_000
            features['employees'] = data_point.get('employees', 0) / 100  # Normalize to hundreds

            # Industry features
            features['industry_risk'] = data_point.get('industry_risk', Decimal('0.5'))
            features['market_growth'] = data_point.get('market_growth', Decimal('0.05'))

            # Company features
            features['company_age'] = data_point.get('company_age', 10) / 100  # Normalize
            features['profitability'] = data_point.get('profitability', Decimal('0.1'))

            return features

        except MethodologyError as e:
            self.logger.error(f"Error extracting state features: {e}")
            return {}

    def _simulate_outcome(self, data_point: Dict[str, Any], methodology: ValuationMethodology) -> Dict[str, Any]:
        """Simulate valuation outcome"""
        try:
            # This would contain actual outcome simulation logic
            # For now, return a simplified outcome
            base_value = data_point.get('revenue', 0) * Decimal('2.0')

            if methodology == ValuationMethodology.DCF:
                multiplier = Decimal('2.5')
            elif methodology == ValuationMethodology.MULTIPLES:
                multiplier = Decimal('2.0')
            elif methodology == ValuationMethodology.ASSET_BASED:
                multiplier = Decimal('1.5')
            else:  # HYBRID
                multiplier = Decimal('2.2')

            valuation = base_value * multiplier

            return {
                'valuation': valuation,
                'methodology': methodology.value,
                'confidence': Decimal('0.8'),
                'accuracy': Decimal('0.85')
            }

        except InvalidDiscountError as e:
            self.logger.error(f"Error simulating outcome: {e}")
            return {}

    def _initialize_learning_config(self) -> Dict[str, Any]:
        """Initialize learning configuration"""
        return {
            'learning_rate': Decimal('0.1'),
            'discount_factor': Decimal('0.9'),
            'epsilon_start': Decimal('0.1'),
            'epsilon_end': Decimal('0.01'),
            'epsilon_decay': Decimal('0.995'),
            'buffer_size': 10000,
            'batch_size': 32,
            'update_frequency': 10
        }


class StateEncoder:
    """State encoder for RL environment"""

    def __init__(self, feature_names: List[str]):
        self.feature_names = feature_names
        self.feature_ranges = {}
        self.logger = logger

    def encode_state(self, features: Dict[str, Decimal]) -> int:
        """Encode state features into discrete state index"""
        try:
            # Simple state encoding - in practice, this would be more sophisticated
            state_vector = []
            for feature_name in self.feature_names:
                value = features.get(feature_name, 0)
                # Normalize and discretize
                normalized_value = min(max(value, 0), 1)
                discrete_value = int(normalized_value * 10)  # 0-10 scale
                state_vector.append(discrete_value)

            # Convert to single state index
            state_index = 0
            for i, value in enumerate(state_vector):
                state_index += value * (11 ** i)

            return state_index % 1000  # Limit state space

        except ValuationEngineError as e:
            self.logger.error(f"Error encoding state: {e}")
            return 0


class RewardCalculator:
    """Reward calculator for RL agent"""

    def __init__(self):
        self.logger = logger

    def calculate_reward(
        self,
        valuation_outcome: Dict[str, Any],
        user_feedback: Optional[Dict[str, Any]] = None
    ) -> Decimal:
        """
        Calculate reward based on valuation outcome.

        Args:
            valuation_outcome: Outcome of the valuation
            user_feedback: User feedback (optional)

        Returns:
            Reward value
        """
        try:
            reward = Decimal('0.0')

            # Base reward from valuation accuracy
            accuracy = valuation_outcome.get('accuracy', Decimal('0.5'))
            reward += accuracy * 10  # Scale accuracy to 0-10

            # Confidence bonus
            confidence = valuation_outcome.get('confidence', Decimal('0.5'))
            reward += confidence * 5  # Scale confidence to 0-5

            # User feedback bonus
            if user_feedback:
                satisfaction = user_feedback.get('satisfaction', Decimal('0.5'))
                reward += satisfaction * 10  # Scale satisfaction to 0-10

                # Penalty for negative feedback
                if satisfaction < 0.3:
                    reward -= 5

            # Methodology-specific bonuses
            methodology = valuation_outcome.get('methodology', 'unknown')
            if methodology == 'dcf' and accuracy > 0.8:
                reward += 2  # Bonus for high-accuracy DCF
            elif methodology == 'multiples' and accuracy > 0.7:
                reward += 1  # Bonus for good multiples

            # Normalize reward to reasonable range
            reward = max(-10, min(20, reward))

            return reward

        except DCFCalculationError as e:
            self.logger.error(f"Error calculating reward: {e}")
            return Decimal('0.0')
