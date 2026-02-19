import pandas as pd
import numpy as np


def ips_estimate(df: pd.DataFrame):
    """
    Basic Inverse Propensity Scoring estimate.
    """
    weights = 1.0 / df["action_prob"].clip(lower=1e-6)
    return float(np.mean(df["reward"] * weights))


def cumulative_regret(rewards: np.ndarray):
    """
    Regret curve vs best observed reward.
    """
    best = np.maximum.accumulate(rewards)
    regret = best - rewards
    return np.cumsum(regret)
