# seca/simre/engine.py

class SIMRE:
    def __init__(self, policy, evaluator):
        self.policy = policy
        self.evaluator = evaluator
        self.dataset = MetaDataset()

    def step(self, players, hypothesis):
        # create modified policy
        new_policy = hypothesis.modify_fn(self.policy)

        # run A/B test
        mean_A, mean_B = run_ab_test(
            players, self.policy, new_policy, self.evaluator
        )

        # choose winner
        winner = choose_winner(mean_A, mean_B)

        if winner == "new":
            self.policy = new_policy
            hypothesis.score = mean_B
        else:
            hypothesis.score = mean_A

        return {
            "winner": winner,
            "mean_A": mean_A,
            "mean_B": mean_B,
        }
