from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Any

import numpy as np


# ---------------------------------------------------------------------
# World state
# ---------------------------------------------------------------------

@dataclass
class WorldState:
    """
    Latent representation of player skill dynamics.

    v0:
    - simple numeric vector
    - placeholder for neural model
    """
    vector: np.ndarray


# ---------------------------------------------------------------------
# Skill World Model
# ---------------------------------------------------------------------

class SkillWorldModel:
    """
    Predicts how player skill evolves after training/game events.

    Current version:
    - deterministic identity dynamics
    - safe bootstrap for SECA runtime

    Future:
    - neural dynamics model (PyTorch)
    - uncertainty estimation
    - planning support
    """

    def __init__(self, dim: int = 32):
        self.dim = dim

    # -----------------------------------------------------------------

    def encode(self, skill_dict: Dict[str, float]) -> WorldState:
        """
        Convert skill dictionary → latent vector.
        """
        vec = np.zeros(self.dim, dtype=np.float32)

        for i, (_, v) in enumerate(skill_dict.items()):
            if i >= self.dim:
                break
            vec[i] = float(v)

        return WorldState(vector=vec)

    # -----------------------------------------------------------------

    def predict_next(self, state: WorldState, action: Dict[str, Any] | None = None) -> WorldState:
        """
        Predict next latent state after training action.

        v0:
        - identity transition (no change)
        """
        return WorldState(vector=state.vector.copy())

    # -----------------------------------------------------------------

    def decode(self, state: WorldState) -> Dict[str, float]:
        """
        Convert latent vector → interpretable skill dict.

        v0:
        - index-based dummy mapping
        """
        return {f"skill_{i}": float(v) for i, v in enumerate(state.vector) if v != 0.0}
