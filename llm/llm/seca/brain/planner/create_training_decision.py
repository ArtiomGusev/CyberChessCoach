from sqlalchemy.orm import Session

from llm.seca.brain.bandit.thompson_linear import LinearThompsonBandit
from llm.seca.brain.bandit.context import build_context_vector
from llm.seca.brain.training.models import TrainingDecision

N_ACTIONS = 6
N_FEATURES = 4


def choose_strategy_with_bandit(
    rating: float,
    confidence: float,
    avg_accuracy: float | None,
    recent_games: int | None,
) -> int:
    """
    Core intelligent decision.
    """

    bandit = LinearThompsonBandit.load_or_create(N_ACTIONS, N_FEATURES)
    x = build_context_vector(rating, confidence, avg_accuracy, recent_games)

    try:
        return bandit.select(x)
    except Exception:
        # safe heuristic fallback
        return 0


def create_training_decision(
    db: Session,
    player_id: str,
    rating: float,
    confidence: float,
    avg_accuracy: float | None,
    recent_games: int | None,
) -> TrainingDecision:
    """
    Main planner entrypoint used by API / worker.
    """

    strategy_id = choose_strategy_with_bandit(
        rating,
        confidence,
        avg_accuracy,
        recent_games,
    )

    decision = TrainingDecision(
        player_id=player_id,
        rating_before=rating,
        confidence_before=confidence,
        avg_accuracy=avg_accuracy,
        games_played_recent=recent_games,
        strategy_id=strategy_id,
        outcome_ready=0,
    )

    db.add(decision)
    db.commit()
    db.refresh(decision)

    return decision
