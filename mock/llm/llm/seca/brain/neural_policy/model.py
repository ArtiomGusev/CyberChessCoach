import torch
import torch.nn as nn


class NeuralPolicy(nn.Module):
    def __init__(self, context_dim: int, n_actions: int):
        super().__init__()

        self.net = nn.Sequential(
            nn.Linear(context_dim + n_actions, 64),
            nn.ReLU(),
            nn.Linear(64, 32),
            nn.ReLU(),
            nn.Linear(32, 1),
        )

        self.n_actions = n_actions

    def forward(self, context, action_onehot):
        x = torch.cat([context, action_onehot], dim=1)
        return self.net(x).squeeze(1)
