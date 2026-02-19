from __future__ import annotations
from typing import Dict, Any, Optional

from llm.seca.world.model import SkillWorldModel, WorldState


class CoachEngine:
    """
    Central decision module of SECA.

    Responsibilities (future):
    - choose explanation style
    - choose training task
    - coordinate curriculum + world model
    - optimize learning outcome

    v0 (bootstrap):
    - deterministic safe behavior
    - architecture-correct interface
    """

    def __init__(self, world_model: SkillWorldModel):
        self.world_model = world_model

    # -----------------------------------------------------------------

    def build_state(self, skills: Dict[str, float]) -> WorldState:
        """
        Encode player skills into latent world state.
        """
        return self.world_model.encode(skills)

    # -----------------------------------------------------------------

    def choose_action(
        self,
        state: WorldState,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Decide what coach should do next.

        v0:
        - always return neutral explanation + no training
        """
        return {
            "type": "explain",
            "style": "neutral",
            "confidence": 0.5,
        }

    # -----------------------------------------------------------------

    def predict_outcome(
        self,
        state: WorldState,
        action: Dict[str, Any],
    ) -> WorldState:
        """
        Predict next skill state after coaching action.
        """
        return self.world_model.predict_next(state, action)
