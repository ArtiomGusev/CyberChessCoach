import numpy as np


class MetaCoach:
    def __init__(self, strategies: list[str]):
        self.strategies = strategies
        self.weights = {s: 0.0 for s in strategies}  # learned value

    # -------------------------------------------------

    def predict_improvement(self, player_state: np.ndarray) -> dict:
        """
        Dummy linear scorer (replace with ML model later).
        """
        return {s: self.weights[s] for s in self.strategies}

    # -------------------------------------------------

    def choose_strategy(self, player_state: np.ndarray) -> str:
        scores = self.predict_improvement(player_state)
        return max(scores, key=scores.get)

    # -------------------------------------------------

    def update(self, strategy: str, observed_gain: float, lr: float = 0.1):
        """
        Online learning from real player improvement.
        """
        self.weights[strategy] += lr * observed_gain
