import torch
import torch.nn as nn
import torch.optim as optim

class CurriculumPolicy(nn.Module):
    def __init__(self, state_dim=3, actions=6):
        super().__init__()
        self.net = nn.Sequential(
        nn.Linear(state_dim, 64),
        nn.ReLU(),
        nn.Linear(64, actions),
    )

    def forward(self, s):
    return self.net(s)
