class CoachingPolicy:
    """
    Chooses next coaching focus using skill graph.
    """

    def __init__(self, graph):
        self.graph = graph

    def choose_focus(self):
        """
        Pick weakest high-impact skill.
        """

        best_skill = None
        best_score = float("inf")

        for skill, value in self.graph.values.items():
            confidence = self.graph.confidence[skill]

            # prioritize low skill + high certainty
            score = value - confidence

            if score < best_score:
                best_score = score
                best_skill = skill

        return best_skill
