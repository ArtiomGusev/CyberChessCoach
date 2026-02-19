import torch
from .model import NeuralSkillDynamics


class SkillDynamicsPredictor:
    """
    Runtime wrapper used by Monte-Carlo simulator.
    """

    def __init__(self, model: NeuralSkillDynamics, device="cpu"):
        self.model = model.to(device)
        self.model.eval()
        self.device = device

    @torch.no_grad()
    def predict(self, state_vec, action_id):
        state = torch.tensor(state_vec, dtype=torch.float32).unsqueeze(0).to(self.device)
        action = torch.tensor([action_id], dtype=torch.long).to(self.device)

        d_skill, conf, fatigue = self.model(state, action)

        return (
            d_skill.item(),
            conf.item(),
            fatigue.item(),
        )


def neural_transition(state, action, predictor):
    d_skill, conf, fatigue = predictor.predict(state, action)

    next_state = state.copy()
    next_state[0] += d_skill      # skill index
    next_state[1] = conf          # confidence index
    next_state[2] = fatigue       # fatigue index

    return next_state
