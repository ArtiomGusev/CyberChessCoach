import numpy as np
from .contextual_bandit import LinUCB

ACTIONS = [
    "tactics_easy",
    "tactics_medium",
    "tactics_hard",
    "play_rapid_game",
    "analyze_last_game",
]


class SECACoach:
    def __init__(self):
        self.bandit = LinUCB(n_features=6, alpha=1.2)

    # -------------------------
    # Build context vector
    # -------------------------
    def build_context(self, player) -> np.ndarray:
        return np.array(
            [
                player.rating,
                player.confidence,
                player.recent_accuracy,
                player.weak_time_management,
                player.weak_blunders,
                player.games_last_7_days,
            ],
            dtype=float,
        )

    # -------------------------
    # Recommend next action
    # -------------------------
    def recommend(self, player) -> str:
        context = self.build_context(player)
        return self.bandit.select(context, ACTIONS)

    # -------------------------
    # Learn from result
    # -------------------------
    def learn(self, player_before, player_after, action: str):
        context = self.build_context(player_before)
        reward = player_after.rating - player_before.rating
        self.bandit.update(action, context, reward)
