from pathlib import Path

from .offline_eval import ips_estimate
from llm.seca.brain.neural_policy.policy import NeuralCoach

DEPLOYED_FLAG = Path("llm/seca/brain/neural_policy/DEPLOYED")


def should_deploy(context_dim: int, n_actions: int) -> bool:
    policy = NeuralCoach(context_dim, n_actions)

    ips = ips_estimate(policy)

    if ips is None:
        print("Safety: not enough data -> reject deploy")
        return False

    print(f"Offline IPS reward: {ips:.4f}")

    # simple safety rule
    if ips <= 0:
        print("Safety: policy worse than baseline -> reject")
        return False

    return True


def mark_deployed():
    DEPLOYED_FLAG.write_text("ok")
