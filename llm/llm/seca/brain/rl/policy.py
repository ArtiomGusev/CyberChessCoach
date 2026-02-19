import joblib
from llm.seca.brain.planner.rollout import rollout
from llm.seca.brain.bandit.actions import ACTIONS

MODEL = "llm/seca/brain/rl/value_model.pkl"
value_model = joblib.load(MODEL)


def choose_action(initial_state):
    best_action = None
    best_value = -1e9

    for action in ACTIONS:
        future_state = rollout(initial_state, [action])

        value = value_model.predict([future_state])[0]

        if value > best_value:
            best_value = value
            best_action = action

    return best_action
