class WorldModelPolicy:
    """
    Chooses coaching focus via counterfactual simulation.
    """

    def __init__(self, simulator, skill_names):
        self.simulator = simulator
        self.skill_names = skill_names

    def choose_focus(self):
        best_skill = None
        best_win_prob = -1.0

        for i, skill in enumerate(self.skill_names):
            wp = self.simulator.evaluate_intervention(i)

            if wp > best_win_prob:
                best_win_prob = wp
                best_skill = skill

        return best_skill, best_win_prob
