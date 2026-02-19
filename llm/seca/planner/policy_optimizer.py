class PolicyOptimizer:
    """
    Chooses optimal next training using Monte-Carlo simulation.
    """

    def __init__(self, simulator):
        self.simulator = simulator

    def choose_next_training(self, current_skill: float) -> str:
        return self.simulator.best_action(current_skill)
