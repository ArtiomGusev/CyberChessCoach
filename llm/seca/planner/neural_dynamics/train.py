import torch
import torch.nn as nn
from torch.utils.data import DataLoader

from .model import NeuralSkillDynamics
from .dataset import SkillDynamicsDataset


def train_model(samples, epochs=20, lr=1e-3, device="cpu"):
    dataset = SkillDynamicsDataset(samples)
    loader = DataLoader(dataset, batch_size=64, shuffle=True)

    model = NeuralSkillDynamics().to(device)
    opt = torch.optim.Adam(model.parameters(), lr=lr)

    loss_fn = nn.MSELoss()

    for epoch in range(epochs):
        total = 0.0

        for state, action, ds, nc, nf in loader:
            state, action = state.to(device), action.to(device)
            ds, nc, nf = ds.to(device), nc.to(device), nf.to(device)

            p_ds, p_nc, p_nf = model(state, action)

            loss = (
                loss_fn(p_ds, ds)
                + loss_fn(p_nc, nc)
                + loss_fn(p_nf, nf)
            )

            opt.zero_grad()
            loss.backward()
            opt.step()

            total += loss.item()

        print(f"Epoch {epoch+1}: loss={total:.4f}")

    return model
