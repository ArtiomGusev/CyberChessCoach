import random


def monte_carlo_plan(sim, state, horizon=20, trials=200):
    best_score = -1e9
    best_seq = None

    for _ in range(trials):
        s = state.copy()
        seq = []

        for _ in range(horizon):
            a = random.randint(0, 5)
            seq.append(a)
            s = sim.step(s, a)

        score = reward_fn(s)

        if score > best_score:
            best_score = score
        best_seq = seq

    return best_seq, best_score
