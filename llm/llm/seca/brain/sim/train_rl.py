import numpy as np
import pickle
from .env import SimulatedPlayer

MODEL_PATH = "llm/seca/brain/world_model/world_model.pkl"


def load_world_model():
    with open(MODEL_PATH, "rb") as f:
        return pickle.load(f)


def random_policy(_):
    return np.random.randint(0, 5)


def run_episode(world_model, steps=50):
    player = SimulatedPlayer()
    total_reward = 0

    for _ in range(steps):
        action = random_policy(player)
        reward = player.step(action, world_model)
        total_reward += reward

    return total_reward


def train(n_episodes=1000):
    wm = load_world_model()

    rewards = [run_episode(wm) for _ in range(n_episodes)]
    print("Mean reward:", np.mean(rewards))


if __name__ == "__main__":
    train()
