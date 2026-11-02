"""Reward policy for reinforcement-learning valuation actions."""

from decimal import Decimal
from typing import FrozenSet, Mapping, Optional

from .rl_types import REWARD_DEFINITIONS, RLAction, RLState

METHODOLOGY_ACTIONS: FrozenSet[RLAction] = frozenset(
    {
        RLAction.SELECT_DCF,
        RLAction.SELECT_MULTIPLES,
        RLAction.SELECT_ASSET_BASED,
        RLAction.SELECT_HYBRID,
    }
)
QUESTION_ACTIONS: FrozenSet[RLAction] = frozenset(
    {
        RLAction.ASK_FINANCIAL_QUESTION,
        RLAction.ASK_OWNER_QUESTION,
        RLAction.ASK_MARKET_QUESTION,
    }
)

Feedback = Mapping[str, object]

MIN_REWARD = -Decimal("2.0")
MAX_REWARD = Decimal("2.0")


def calculate_rl_reward(
    action: RLAction,
    state: RLState,
    user_feedback: Optional[Feedback] = None,
) -> Decimal:
    """Calculate the bounded reward for an action and optional user feedback."""

    feedback = user_feedback or {}
    reward = _action_reward(action, state, feedback)
    reward += _satisfaction_reward(feedback)
    reward += _operational_penalty(feedback)
    return _clip_reward(reward)


def _action_reward(action: RLAction, state: RLState, feedback: Feedback) -> Decimal:
    if action in METHODOLOGY_ACTIONS:
        return _methodology_reward(feedback)
    if action in QUESTION_ACTIONS:
        return _question_reward(state, feedback)
    if action == RLAction.COMPLETE_VALUATION:
        return _completion_reward(feedback)
    return Decimal("0.0")


def _methodology_reward(feedback: Feedback) -> Decimal:
    if _enabled(feedback, "methodology_correct"):
        return REWARD_DEFINITIONS["methodology_correct"]
    if _enabled(feedback, "methodology_incorrect"):
        return REWARD_DEFINITIONS["methodology_incorrect"]
    return Decimal("0.1")


def _question_reward(state: RLState, feedback: Feedback) -> Decimal:
    if _enabled(feedback, "question_relevant"):
        return REWARD_DEFINITIONS["question_relevant"]
    if _enabled(feedback, "question_irrelevant"):
        return REWARD_DEFINITIONS["question_irrelevant"]
    return state.data_completeness * Decimal("0.2")


def _completion_reward(feedback: Feedback) -> Decimal:
    if _enabled(feedback, "valuation_complete"):
        return REWARD_DEFINITIONS["valuation_complete"]
    if _enabled(feedback, "valuation_incomplete"):
        return REWARD_DEFINITIONS["valuation_incomplete"]
    return Decimal("0.5")


def _satisfaction_reward(feedback: Feedback) -> Decimal:
    if _enabled(feedback, "user_satisfied"):
        return REWARD_DEFINITIONS["user_satisfied"]
    if _enabled(feedback, "user_dissatisfied"):
        return REWARD_DEFINITIONS["user_dissatisfied"]
    return Decimal("0.0")


def _operational_penalty(feedback: Feedback) -> Decimal:
    reward = Decimal("0.0")
    if _enabled(feedback, "timeout"):
        reward += REWARD_DEFINITIONS["timeout"]
    if _enabled(feedback, "error"):
        reward += REWARD_DEFINITIONS["error"]
    return reward


def _clip_reward(reward: Decimal) -> Decimal:
    return max(MIN_REWARD, min(MAX_REWARD, reward))


def _enabled(feedback: Feedback, key: str) -> bool:
    return bool(feedback.get(key, False))
