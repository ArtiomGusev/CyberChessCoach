from llm.seca.planning.neural_dynamics.train import train_model


def run(samples):
    model = train_model(samples, epochs=30)

    import torch

    torch.save(model.state_dict(), "skill_dynamics.pt")
