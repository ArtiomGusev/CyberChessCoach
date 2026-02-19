from llm.seca.brain.world_model.infer import predict_next_state


def simulate_step(state, action_features):
    """
    state: [rating, confidence, accuracy]
    action_features: vector describing training intervention
    """
    return predict_next_state(state, action_features)
