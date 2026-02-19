import random


class AlgorithmGenerator:
    """
    Creates small variations of learning parameters.
    """

    def propose_bandit_variant(self):
        return {
            "epsilon": random.uniform(0.01, 0.3),
            "name": f"bandit_eps_{random.randint(0,9999)}",
        }

    def propose_rating_variant(self):
        return {
            "k_factor": random.uniform(8, 40),
            "name": f"rating_k_{random.randint(0,9999)}",
        }
