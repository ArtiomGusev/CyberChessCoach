import pandas as pd
import numpy as np
from .ips import ips_estimate, cumulative_regret


def evaluate_policy(df: pd.DataFrame, policy_fn):
    """
    Replay historical contexts through a new policy.
    """
    accepted = []

    for _, row in df.iterrows():
        x = np.array(row["context"])
        logged_action = row["action"]

        new_action, prob = policy_fn(x)

        if new_action == logged_action:
            accepted.append(
                {
                    "reward": row["reward"],
                    "prob": prob,
                }
            )

    if not accepted:
        return None

    sub = pd.DataFrame(accepted)
    return ips_estimate(sub)
