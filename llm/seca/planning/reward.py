def reward_fn(state):
    skill = state[0]
    confidence = state[1]

    return skill - 200 * fatigue
