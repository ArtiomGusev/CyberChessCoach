from .rollout import rollout
from llm.seca.brain.bandit.actions import ACTIONS

BEAM_WIDTH = 5
DEPTH = 3  # number of training steps we simulate


def plan(initial_state):
    beams = [([], initial_state)]

    for _ in range(DEPTH):
        new_beams = []

        for seq, _ in beams:
            for action in ACTIONS:
                new_seq = seq + [action]
                future_state = rollout(initial_state, new_seq)

                score = future_state[0]  # predicted rating
                new_beams.append((new_seq, score))

        # keep best beams
        new_beams.sort(key=lambda x: x[1], reverse=True)
        beams = [(seq, None) for seq, _ in new_beams[:BEAM_WIDTH]]

    return beams[0][0][0]  # best FIRST action
