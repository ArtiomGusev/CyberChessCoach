import numpy as np


def build_context_vector(
    rating: float,
    confidence: float,
    avg_accuracy: float | None,
    recent_games: int | None,
) -> np.ndarray:
    """
    Shared context builder used by:
    - planner (decision time)
    - bandit trainer (learning time)
    """

    x = np.array(
        [
            rating / 3000.0,
            confidence,
            avg_accuracy or 0.5,
            (recent_games or 0) / 20.0,
        ]
    ).reshape(-1, 1)

    return x
