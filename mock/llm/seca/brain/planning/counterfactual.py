import numpy as np
import joblib
from pathlib import Path

MODEL_PATH = Path("llm/seca/brain/world_model/world_model.pkl")


class CounterfactualPlanner:
    def __init__(self):
        self.model = joblib.load(MODEL_PATH)

    # ---------------------------------
    # simulate one action
    # ---------------------------------
    def simulate(self, state: np.ndarray, action_vec: np.ndarray):
        """
        Predict rating/confidence deltas.
        """
        x = np.concatenate([state, action_vec]).reshape(1, -1)
        pred = self.model.predict(x)[0]

        rating_delta = float(pred[0])
        conf_delta = float(pred[1])

        return rating_delta, conf_delta

    # ---------------------------------
    # evaluate reward of outcome
    # ---------------------------------
    def reward(self, rating_delta: float, conf_delta: float) -> float:
        return rating_delta + 0.3 * conf_delta

    # ---------------------------------
    # choose best action via imagination
    # ---------------------------------
    def choose_action(self, state: np.ndarray, actions: list[np.ndarray]):
        best_score = -1e9
        best_idx = 0
        best_future = None

        for i, a in enumerate(actions):
            r_delta, c_delta = self.simulate(state, a)
            score = self.reward(r_delta, c_delta)

            if score > best_score:
                best_score = score
                best_idx = i
                best_future = (r_delta, c_delta)

        return best_idx, best_future, best_score
