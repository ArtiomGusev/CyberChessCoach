import torch
import torch.nn as nn


class NeuralSkillDynamics(nn.Module):
    """
    Predicts next player state after a training action.
    """

    def __init__(
        self,
        state_dim: int = 16,
        action_dim: int = 8,
        hidden_dim: int = 128,
    ):
        super().__init__()

        self.action_embed = nn.Embedding(action_dim, 16)

        self.net = nn.Sequential(
            nn.Linear(state_dim + 16, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim),
            nn.ReLU(),
        )

        # Outputs
        self.delta_skill = nn.Linear(hidden_dim, 1)
        self.next_conf = nn.Linear(hidden_dim, 1)
        self.next_fatigue = nn.Linear(hidden_dim, 1)

    def forward(self, state, action_id):
        """
        state:  (B, state_dim)
        action: (B,)
        """
        a = self.action_embed(action_id)
        x = torch.cat([state, a], dim=-1)

        h = self.net(x)

        d_skill = self.delta_skill(h)
        conf = torch.sigmoid(self.next_conf(h))
        fatigue = torch.sigmoid(self.next_fatigue(h))

        return d_skill, conf, fatigue
