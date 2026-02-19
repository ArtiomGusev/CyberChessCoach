class SkillTrainer:
    def __init__(self):
        self.last_accuracy = None

    def train_on_events(self, events):
        """
        Extremely simple causal learning placeholder.

        Later:
        - outcome attribution
        - weakness correlation
        - explanation policy update
        """

        games = len(events)

        avg_accuracy = sum(e.accuracy for e in events) / games

        # pretend we updated internal model
        self.last_accuracy = avg_accuracy

        return {
            "games_seen": games,
            "avg_accuracy": round(avg_accuracy, 3),
        }
