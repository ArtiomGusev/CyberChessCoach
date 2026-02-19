import numpy as np
from dataclasses import dataclass
from typing import List, Tuple

from .counterfactual import CounterfactualPlanner
from llm.seca.brain.world_model.ensemble import EnsembleWorldModel
from llm.seca.brain.planning.risk import risk_adjusted_reward


@dataclass
class Trajectory:
    state: np.ndarray
    score: float
    actions: List[int]


class RolloutPlanner:
    def __init__(
        self,
        horizon: int = 4,      # weeks ahead
        beam_width: int = 5,   # number of futures kept
        gamma: float = 0.9,
    ):
        self.horizon = horizon
        self.beam_width = beam_width
        self.gamma = gamma
        self.cf = CounterfactualPlanner()
        self.ensemble = EnsembleWorldModel()

    # ---------------------------------
    # simulate one step forward
    # ---------------------------------
    def step(self, state: np.ndarray, action_vec: np.ndarray):
        features = np.concatenate([state, action_vec])
        r_delta, c_delta, r_unc, c_unc = self.ensemble.predict(features)

        next_state = state.copy()
        next_state[0] += r_delta        # rating
        next_state[1] += c_delta        # confidence

        reward = risk_adjusted_reward(r_delta, c_delta, r_unc, c_unc)

        return next_state, reward

    # ---------------------------------
    # full rollout planning
    # ---------------------------------
    def plan(
        self,
        start_state: np.ndarray,
        actions: List[np.ndarray],
    ) -> Tuple[int, float]:
        """
        Returns:
            best first action index
            expected long-term score
        """

        beam = [Trajectory(start_state, 0.0, [])]

        for t in range(self.horizon):
            new_beam = []

            for traj in beam:
                for i, a in enumerate(actions):
                    next_state, reward = self.step(traj.state, a)

                    discounted = (self.gamma ** t) * reward

                    new_traj = Trajectory(
                        state=next_state,
                        score=traj.score + discounted,
                        actions=traj.actions + [i],
                    )
                    new_beam.append(new_traj)

            # keep only best futures
            new_beam.sort(key=lambda x: x.score, reverse=True)
            beam = new_beam[: self.beam_width]

        best = beam[0]
        best_first_action = best.actions[0]

        return best_first_action, best.score
