import numpy as np
import pickle
from pathlib import Path

from sqlalchemy.orm import Session
from sqlalchemy import select

from llm.seca.db import SessionLocal
from llm.seca.brain.training.models import TrainingDecision, TrainingOutcome


MODEL_PATH = Path("llm/seca/brain/bandit/bandit_model.pkl")


class LinUCB:
    def __init__(self, n_actions: int, n_features: int, alpha: float = 1.0):
        self.n_actions = n_actions
        self.n_features = n_features
        self.alpha = alpha

        self.A = [np.eye(n_features) for _ in range(n_actions)]
        self.b = [np.zeros((n_features, 1)) for _ in range(n_actions)]

    def select(self, x: np.ndarray) -> int:
        """Choose best action for context x"""
        p = []

        for a in range(self.n_actions):
            A_inv = np.linalg.inv(self.A[a])
            theta = A_inv @ self.b[a]

            exploit = float(theta.T @ x)
            explore = self.alpha * np.sqrt(float(x.T @ A_inv @ x))

            p.append(exploit + explore)

        return int(np.argmax(p))

    def update(self, action: int, x: np.ndarray, reward: float):
        """Update parameters from one experience"""
        self.A[action] += x @ x.T
        self.b[action] += reward * x

    def save(self):
        MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(MODEL_PATH, "wb") as f:
            pickle.dump(self, f)

    @staticmethod
    def load_or_create(n_actions: int, n_features: int):
        if MODEL_PATH.exists():
            with open(MODEL_PATH, "rb") as f:
                return pickle.load(f)
        return LinUCB(n_actions, n_features)


N_ACTIONS = 6  # number of training strategies
N_FEATURES = 4  # context vector size
STRATEGIES = [
    "tactics",
    "calculation",
    "endgames",
    "openings",
    "play",
    "review",
]


def build_context(decision: TrainingDecision) -> np.ndarray:
    """
    Convert DB decision -> numeric vector.
    """
    x = np.array(
        [
            decision.rating_before / 3000.0,
            decision.confidence_before,
            decision.recent_accuracy or 0.5,
            decision.games_last_week / 20.0 if decision.games_last_week else 0.0,
        ],
        dtype=float,
    ).reshape(-1, 1)

    return x


def compute_reward(outcome: TrainingOutcome) -> float:
    return outcome.rating_delta + 50.0 * outcome.confidence_delta


def train_bandit_once():
    db: Session = SessionLocal()

    try:
        stmt = (
            select(TrainingDecision, TrainingOutcome)
            .join(TrainingOutcome, TrainingOutcome.decision_id == TrainingDecision.id)
            .where(TrainingDecision.outcome_ready == 1)
        )

        rows = db.execute(stmt).all()

        if not rows:
            print("No completed outcomes to learn from.")
            return

        bandit = LinUCB.load_or_create(N_ACTIONS, N_FEATURES)

        for decision, outcome in rows:
            x = build_context(decision)
            reward = compute_reward(outcome)
            action = STRATEGIES.index(decision.strategy) if decision.strategy in STRATEGIES else 0

            bandit.update(action, x, reward)

        bandit.save()

        print(f"Bandit trained on {len(rows)} samples.")

    finally:
        db.close()


if __name__ == "__main__":
    train_bandit_once()
