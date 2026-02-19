# seca/simre/ab_test.py

def run_ab_test(players, base_policy, new_policy, evaluator):
    results = {"A": [], "B": []}

    for p in players:
        policy = base_policy if hash(p.id) % 2 == 0 else new_policy
        gain = evaluator.evaluate_player(p, policy)

        group = "A" if policy is base_policy else "B"
        results[group].append(gain)

    import numpy as np
    mean_A = np.mean(results["A"])
    mean_B = np.mean(results["B"])

    return mean_A, mean_B
