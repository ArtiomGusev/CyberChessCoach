import json
import numpy as np
from dataclasses import dataclass
from typing import List, Tuple

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from llm.seca.auth.models import Player
from llm.seca.learning.player_embedding import embedding_from_json, zeros_embedding

# --------------------------------------------------
# Data structures
# --------------------------------------------------


@dataclass
class PlayerState:
    rating: float
    confidence: float
    weaknesses: np.ndarray  # vector
    z_player: np.ndarray  # 16-d embedding


@dataclass
class Trajectory:
    actions: List[str]
    states: List[PlayerState]
    score: float


# --------------------------------------------------
# Planner
# --------------------------------------------------


class BeamPlanner8Week:
    def __init__(
        self,
        world_model,
        actions: List[str],
        beam_width: int = 5,
        horizon: int = 8,
        w_rating: float = 1.0,
        w_conf: float = 0.5,
        w_weak: float = 0.7,
    ):
        self.world_model = world_model
        self.actions = actions
        self.beam_width = beam_width
        self.horizon = horizon

        self.w_rating = w_rating
        self.w_conf = w_conf
        self.w_weak = w_weak

    # --------------------------------------------------

    def reward(self, state: PlayerState) -> float:
        weakness_score = np.mean(state.weaknesses)
        return (
            self.w_rating * state.rating
            + self.w_conf * state.confidence
            - self.w_weak * weakness_score
        )

    # --------------------------------------------------

    def predict_next(self, state: PlayerState, action: str) -> PlayerState:
        """
        World model predicts deltas.
        """
        features = np.concatenate(
            [[state.rating, state.confidence], state.weaknesses, state.z_player]
        )

        delta = self.world_model.predict(features, action)

        new_rating = state.rating + delta["rating"]
        new_conf = np.clip(state.confidence + delta["confidence"], 0, 1)
        new_weak = np.clip(state.weaknesses + delta["weaknesses"], 0, 1)

        return PlayerState(new_rating, new_conf, new_weak, state.z_player)

    # --------------------------------------------------

    def plan(self, start: PlayerState) -> Trajectory:
        """
        Beam search over 8 weeks.
        """

        beam: List[Trajectory] = [Trajectory(actions=[], states=[start], score=0.0)]

        for _ in range(self.horizon):

            new_beam: List[Trajectory] = []

            for traj in beam:
                current_state = traj.states[-1]

                for action in self.actions:
                    next_state = self.predict_next(current_state, action)

                    new_score = traj.score + self.reward(next_state)

                    new_beam.append(
                        Trajectory(
                            actions=traj.actions + [action],
                            states=traj.states + [next_state],
                            score=new_score,
                        )
                    )

            # keep best trajectories
            new_beam.sort(key=lambda t: t.score, reverse=True)
            beam = new_beam[: self.beam_width]

        return beam[0]


def best_8_week_plan(player_id: str, world_model, actions: List[str]) -> Trajectory:
    engine = create_engine("sqlite:///data/seca.db", connect_args={"check_same_thread": False})
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    try:
        player = db.query(Player).filter_by(id=player_id).first()
        if not player:
            raise ValueError("Player not found")

        skill_vector = json.loads(player.skill_vector_json or "{}")
        weakness_keys = sorted(skill_vector.keys())
        weaknesses = np.array([skill_vector.get(k, 0.0) for k in weakness_keys], dtype=np.float32)

        z_player = (
            embedding_from_json(player.player_embedding)
            if hasattr(player, "player_embedding")
            else zeros_embedding()
        )

        state = PlayerState(
            rating=float(player.rating),
            confidence=float(player.confidence),
            weaknesses=weaknesses,
            z_player=z_player,
        )

        planner = BeamPlanner8Week(world_model, actions)
        return planner.plan(state)
    finally:
        db.close()
