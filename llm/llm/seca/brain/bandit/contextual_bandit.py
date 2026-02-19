import pickle
from pathlib import Path
import numpy as np
from .actions import ACTIONS

MODEL_PATH = Path("llm/seca/brain/bandit/contextual_bandit.pkl")


class LinUCB:
    def __init__(self, n_actions: int, context_dim: int, alpha: float = 1.0):
        self.n_actions = n_actions
        self.context_dim = context_dim
        self.n_features = context_dim
        self.alpha = alpha

        self.A = [np.eye(context_dim) for _ in range(n_actions)]
        self.b = [np.zeros((context_dim, 1)) for _ in range(n_actions)]

    # -----------------------------
    # AUTO-RESIZE if context changed
    # -----------------------------
    def _ensure_dim(self, context: np.ndarray):
        d = self.context_dim
        for i in range(self.n_actions):
            if self.A[i].shape != (d, d):
                self.A[i] = np.eye(d)
            if self.b[i].shape != (d, 1):
                self.b[i] = np.zeros(d).reshape(-1, 1)

    # -----------------------------
    # Choose best action
    # -----------------------------
    def select(self, context: np.ndarray, actions: list[str]) -> str:
        context = context.reshape(-1, 1)
        self._ensure_dim(context)

        best_action = None
        best_score = -1e9

        for i, a in enumerate(actions):
            A_inv = np.linalg.inv(self.A[i])
            theta = A_inv @ self.b[i]

            exploit = float(theta.T @ context)
            explore = self.alpha * np.sqrt(float(context.T @ A_inv @ context))

            score = exploit + explore

            if score > best_score:
                best_score = score
                best_action = a

        return best_action

    # -----------------------------
    # Update after reward observed
    # -----------------------------
    def update(self, action: int, context: np.ndarray, reward: float):
        context = context.reshape(-1, 1)

        # critical fix
        self._ensure_dim(context)

        self.A[action] += context @ context.T
        self.b[action] += reward * context


class ContextualBandit:
    def __init__(self, n_features: int = 3, alpha: float = 1.0, model_path: Path | None = None):
        self.n_features = n_features
        self.context_dim = n_features
        self.n_actions = len(ACTIONS)
        self.alpha = alpha
        self.model_path = model_path or MODEL_PATH
        self.bandit = LinUCB(
            n_actions=self.n_actions,
            context_dim=self.context_dim,
            alpha=self.alpha,
        )

        if self.model_path.exists():
            try:
                with open(self.model_path, "rb") as f:
                    loaded = pickle.load(f)
                self.bandit = loaded.bandit
                self.n_features = getattr(loaded, "n_features", self.n_features)
                self.context_dim = getattr(loaded, "context_dim", self.n_features)
                self.n_actions = getattr(loaded, "n_actions", self.n_actions)
                self.alpha = getattr(loaded, "alpha", self.alpha)
            except Exception:
                pass

    def update(self, context: np.ndarray, action_index: int, reward: float):
        self.bandit.update(action_index, context, reward)

    def save(self):
        self.model_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.model_path, "wb") as f:
            pickle.dump(self, f)
