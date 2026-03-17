import argparse
import os
from dataclasses import dataclass

import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader

from llm.seca.world_model.model import SkillDynamicsModel

# ============================================================
# Dataset
# ============================================================


class SkillDataset(torch.utils.data.Dataset):
    def __init__(self, path: str):
        data = np.load(path)

        self.states = torch.tensor(data["states"], dtype=torch.float32)
        self.actions = torch.tensor(data["actions"], dtype=torch.float32)
        self.next_states = torch.tensor(data["next_states"], dtype=torch.float32)
        self.rewards = torch.tensor(data["rewards"], dtype=torch.float32)

    def __len__(self):
        return len(self.states)

    def __getitem__(self, idx):
        return (
            self.states[idx],
            self.actions[idx],
            self.next_states[idx],
            self.rewards[idx],
        )


# ============================================================
# Neural Skill Dynamics World Model
# ============================================================


class ResidualBlock(nn.Module):
    def __init__(self, channels: int):
        super().__init__()
        self.block = nn.Sequential(
            nn.Conv2d(channels, channels, 3, padding=1),
            nn.BatchNorm2d(channels),
            nn.ReLU(inplace=True),
            nn.Conv2d(channels, channels, 3, padding=1),
            nn.BatchNorm2d(channels),
        )
        self.relu = nn.ReLU(inplace=True)

    def forward(self, x):
        return self.relu(x + self.block(x))


class NeuralSkillWorldModel(nn.Module):
    """
    Predicts scalar skill signal from board state.

    Architecture:
        CNN encoder → residual tower → global pooling → MLP head
    """

    def __init__(self, in_channels: int = 12, channels: int = 128, blocks: int = 6):
        super().__init__()

        self.stem = nn.Sequential(
            nn.Conv2d(in_channels, channels, 3, padding=1),
            nn.BatchNorm2d(channels),
            nn.ReLU(inplace=True),
        )

        self.tower = nn.Sequential(*[ResidualBlock(channels) for _ in range(blocks)])

        self.head = nn.Sequential(
            nn.AdaptiveAvgPool2d(1),
            nn.Flatten(),
            nn.Linear(channels, 64),
            nn.ReLU(inplace=True),
            nn.Linear(64, 1),
        )

    def forward(self, x):
        x = self.stem(x)
        x = self.tower(x)
        return self.head(x).squeeze(-1)


class SkillWorldModel(SkillDynamicsModel):
    def __init__(self, skill_dim: int, action_dim: int, hidden_dim: int):
        super().__init__(skill_dim=skill_dim, action_dim=action_dim, hidden=hidden_dim)


# ============================================================
# Training loop
# ============================================================


@dataclass
class TrainConfig:
    dataset: str
    epochs: int = 10
    batch_size: int = 128
    lr: float = 1e-3
    skill_dim: int | None = None
    action_dim: int | None = None
    hidden_dim: int | None = None
    device: str | None = None
    save_path: str = "skill_world_model.pt"


def train(cfg):
    print(f"Loading dataset: {cfg.dataset}")

    dataset = SkillDataset(cfg.dataset)
    loader = torch.utils.data.DataLoader(
        dataset,
        batch_size=cfg.batch_size,
        shuffle=True,
    )

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print("Training on device:", device)

    skill_dim = cfg.skill_dim or dataset.states.shape[1]
    action_dim = cfg.action_dim or dataset.actions.shape[1]
    hidden_dim = cfg.hidden_dim or 128

    model = SkillWorldModel(
        skill_dim=skill_dim,
        action_dim=action_dim,
        hidden_dim=hidden_dim,
    ).to(device)

    optimizer = torch.optim.Adam(model.parameters(), lr=cfg.lr)
    loss_fn = torch.nn.MSELoss()

    # Normalize inputs to stabilize training
    state_mean = dataset.states.mean(dim=0, keepdim=True)
    state_std = dataset.states.std(dim=0, keepdim=True).clamp_min(1e-8)
    action_mean = dataset.actions.mean(dim=0, keepdim=True)
    action_std = dataset.actions.std(dim=0, keepdim=True).clamp_min(1e-8)
    next_state_mean = dataset.next_states.mean(dim=0, keepdim=True)
    next_state_std = dataset.next_states.std(dim=0, keepdim=True).clamp_min(1e-8)

    for epoch in range(1, cfg.epochs + 1):
        total_loss = 0.0

        for states, actions, next_states, rewards in loader:
            states = ((states - state_mean) / state_std).to(device)
            actions = ((actions - action_mean) / action_std).to(device)
            next_states = ((next_states - next_state_mean) / next_state_std).to(device)

            pred_next = model(states, actions)
            loss = loss_fn(pred_next, next_states)

            optimizer.zero_grad()
            loss.backward()
            optimizer.step()

            total_loss += loss.item()

        avg_loss = total_loss / len(loader)
        print(f"Epoch {epoch:02d} | loss {avg_loss:.4f}")

    # Save model
    save_path = "seca/models/skill_world_model.pt"
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    torch.save(model.state_dict(), save_path)

    print(f"Saved model -> {save_path}")


# ============================================================
# CLI
# ============================================================


def main():
    parser = argparse.ArgumentParser(description="Train Neural Skill Dynamics World Model")

    parser.add_argument("--dataset", required=True, help="Path to .npz dataset")
    parser.add_argument("--epochs", type=int, default=10)
    parser.add_argument("--batch_size", type=int, default=128)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--skill_dim", type=int, default=None)
    parser.add_argument("--action_dim", type=int, default=None)
    parser.add_argument("--hidden_dim", type=int, default=None)
    parser.add_argument("--device", default=None)
    parser.add_argument("--save", default="skill_world_model.pt")

    args = parser.parse_args()

    device = args.device or ("cuda" if torch.cuda.is_available() else "cpu")

    cfg = TrainConfig(
        dataset=args.dataset,
        epochs=args.epochs,
        batch_size=args.batch_size,
        lr=args.lr,
        skill_dim=args.skill_dim,
        action_dim=args.action_dim,
        hidden_dim=args.hidden_dim,
        device=device,
        save_path=args.save,
    )

    train(cfg)


if __name__ == "__main__":
    main()
