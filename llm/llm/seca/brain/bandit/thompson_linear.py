import numpy as np
import pickle
from pathlib import Path


MODEL_PATH = Path("llm/seca/brain/bandit/thompson_bandit.pkl")


class LinearThompsonBandit:
    """
    Bayesian linear contextual bandit using Thompson Sampling.
    """

    def __init__(self, n_actions: int, n_features: int, noise_var: float = 1.0):
        self.n_actions = n_actions
        self.n_features = n_features
        self.noise_var = noise_var

        self.A = [np.eye(n_features) for _ in range(n_actions)]
        self.b = [np.zeros((n_features, 1)) for _ in range(n_actions)]

    # -------------------------
    # Posterior sampling
    # -------------------------
    def _sample_theta(self, action: int):
        A_inv = np.linalg.inv(self.A[action])
        mu = A_inv @ self.b[action]
        cov = self.noise_var * A_inv

        return np.random.multivariate_normal(
            mean=mu.flatten(),
            cov=cov,
        ).reshape(-1, 1)

    # -------------------------
    # Action selection
    # -------------------------
    def select(self, x: np.ndarray) -> int:
        sampled_rewards = []

        for a in range(self.n_actions):
            theta_sample = self._sample_theta(a)
            reward = float(theta_sample.T @ x)
            sampled_rewards.append(reward)

        return int(np.argmax(sampled_rewards))

    # -------------------------
    # Update posterior
    # -------------------------
    def update(self, action: int, x: np.ndarray, reward: float):
        self.A[action] += x @ x.T
        self.b[action] += reward * x

    # -------------------------
    # Persistence
    # -------------------------
    def save(self):
        MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(MODEL_PATH, "wb") as f:
            pickle.dump(self, f)

    @staticmethod
    def load_or_create(n_actions: int, n_features: int):
        if MODEL_PATH.exists():
            with open(MODEL_PATH, "rb") as f:
                return pickle.load(f)

        return LinearThompsonBandit(n_actions, n_features)
