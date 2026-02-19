from .simulator import simulate_step

HORIZON = 14  # days


def rollout(initial_state, action_sequence):
    state = initial_state

    for action in action_sequence:
        state = simulate_step(state, action)

    return state  # predicted future player
