import pandas as pd
import matplotlib.pyplot as plt
from .ips import cumulative_regret


def plot(df: pd.DataFrame):
    rewards = df["reward"].values
    regret = cumulative_regret(rewards)

    plt.plot(regret)
    plt.title("Cumulative Regret")
    plt.xlabel("Steps")
    plt.ylabel("Regret")
    plt.show()
