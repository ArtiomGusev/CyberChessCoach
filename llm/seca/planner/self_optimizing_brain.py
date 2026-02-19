class SelfOptimizingCoachBrain:
    """
    Central intelligence of SECA.
    """

    def __init__(self, simulator, optimizer):
        self.simulator = simulator
        self.optimizer = optimizer

    def next_training(self, skill: float) -> str:
        return self.optimizer.choose_next_training(skill)
