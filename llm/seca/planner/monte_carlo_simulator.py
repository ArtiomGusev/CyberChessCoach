import random
from typing import List, Callable

from .neural_dynamics.infer import neural_transition


class MonteCarloTrainingSimulator:
    """
    Simulates future skill trajectories under different training actions.
    """

    def __init__(
        self,
        transition_fn: Callable[[list[float], object], list[float]] | None,
        reward_fn: Callable[[list[float]], float],
        actions: List[object],
        predictor=None,
        horizon: int = 14,
        simulations: int = 200,
        discount: float = 0.95,
    ):
        if transition_fn is None:
            if predictor is None:
                raise ValueError("transition_fn or predictor is required")
            self.transition_fn = lambda s, a: neural_transition(s, a, predictor)
        else:
            self.transition_fn = transition_fn
        self.reward_fn = reward_fn
        self.actions = actions
        self.horizon = horizon
        self.simulations = simulations
        self.discount = discount

    # -------------------------
    # Single rollout
    # -------------------------
    def rollout(self, start_state: list[float], first_action) -> float:
        state = start_state.copy()
        total_reward = 0.0
        gamma = 1.0

        action = first_action

        for _ in range(self.horizon):
            state = self.transition_fn(state, action)
            total_reward += gamma * self.reward_fn(state)

            gamma *= self.discount
            action = random.choice(self.actions)

        return total_reward

    # -------------------------
    # Evaluate first action
    # -------------------------
    def evaluate_action(self, start_state: list[float], action) -> float:
        rewards = [self.rollout(start_state, action) for _ in range(self.simulations)]
        return sum(rewards) / len(rewards)

    # -------------------------
    # Best action
    # -------------------------
    def best_action(self, start_state: list[float]):
        scores = {a: self.evaluate_action(start_state, a) for a in self.actions}
        return max(scores, key=scores.get)
