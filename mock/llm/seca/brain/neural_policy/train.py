import torch
import torch.nn as nn
import torch.optim as optim
from pathlib import Path

from .dataset import load_training_data
from .model import NeuralPolicy
from llm.seca.brain.safety.gate import should_deploy, mark_deployed

MODEL_PATH = Path("llm/seca/brain/neural_policy/policy.pt")


def train_policy():
    X, A, y = load_training_data()

    if len(X) < 10:
        print("Not enough data to train neural policy.")
        return

    X = torch.tensor(X, dtype=torch.float32)
    y = torch.tensor(y, dtype=torch.float32)

    n_actions = int(A.max()) + 1
    context_dim = X.shape[1]

    model = NeuralPolicy(context_dim, n_actions)

    optimizer = optim.Adam(model.parameters(), lr=1e-3)
    loss_fn = nn.MSELoss()

    for _ in range(50):
        action_onehot = torch.nn.functional.one_hot(
            torch.tensor(A), num_classes=n_actions
        ).float()

        preds = model(X, action_onehot)
        loss = loss_fn(preds, y)

        optimizer.zero_grad()
        loss.backward()
        optimizer.step()

    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    torch.save(model.state_dict(), MODEL_PATH)

    print("Neural policy trained and saved.")

    if should_deploy(context_dim, n_actions):
        mark_deployed()
        print("Policy DEPLOYED")
    else:
        print("Policy REJECTED")
