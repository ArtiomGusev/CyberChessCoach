import numpy as np


class SimulatedPlayer:
    def __init__(self):
        self.rating = 1200.0
        self.confidence = 0.5
        self.weakness = np.random.rand(3)

    def step(self, action, world_model):
        """
        Apply training action using learned world model + noise.
        """
        x = np.array(
            [
                self.rating,
                self.confidence,
                *self.weakness,
                action,
            ]
        ).reshape(1, -1)

        dr, dc = world_model.predict(x)[0]

        # stochasticity
        dr += np.random.normal(0, 5)
        dc += np.random.normal(0, 0.02)

        self.rating += dr
        self.confidence = np.clip(self.confidence + dc, 0, 1)

        reward = dr + 50 * dc
        return reward
