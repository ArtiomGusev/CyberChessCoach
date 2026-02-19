class SkillWorldSimulator:
    def __init__(self, predictor):
    self.predictor = predictor

    def step(self, state, action):
    d_skill, conf, fatigue = self.predictor.predict(state, action)

    next_state = state.copy()
    next_state[0] += d_skill
    next_state[1] = conf
    next_state[2] = fatigue

    return next_state
