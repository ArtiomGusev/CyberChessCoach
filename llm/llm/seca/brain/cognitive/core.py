class CognitiveCore:
    """
    Unified thinking loop of SECA.
    """

    def __init__(self, memory, world_model, reasoner, planner, learner):
        self.memory = memory
        self.world_model = world_model
        self.reasoner = reasoner
        self.planner = planner
        self.learner = learner

    def think(self, player_state):
        # 1. recall relevant experience
        context = self.memory.retrieve(player_state)

        # 2. simulate possible futures
        simulations = self.reasoner.simulate(
            player_state,
            context,
            self.world_model,
        )

        # 3. choose best long-term plan
        plan = self.planner.select(simulations)

        return plan

    def learn(self, outcome):
        # update memory + models
        self.memory.store(outcome)
        self.learner.update(outcome)
