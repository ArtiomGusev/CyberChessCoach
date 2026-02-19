import torch
import numpy as np
from pathlib import Path

from .model import NeuralPolicy

MODEL_PATH = Path("llm/seca/brain/neural_policy/policy.pt")


class NeuralCoach:
    def __init__(self, context_dim: int, n_actions: int):
        self.model = NeuralPolicy(context_dim, n_actions)
        self.n_actions = n_actions

        if MODEL_PATH.exists():
            self.model.load_state_dict(torch.load(MODEL_PATH))
            self.model.eval()

    def select_action(self, context: np.ndarray) -> int:
        ctx = torch.tensor(context, dtype=torch.float32).unsqueeze(0)

        best_action = 0
        best_value = -1e9

        for a in range(self.n_actions):
            onehot = torch.nn.functional.one_hot(
                torch.tensor([a]), num_classes=self.n_actions
            ).float()

            value = self.model(ctx, onehot).item()

            if value > best_value:
                best_value = value
                best_action = a

        return best_action
