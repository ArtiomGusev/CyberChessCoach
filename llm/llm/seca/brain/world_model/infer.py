from pathlib import Path
import joblib
import numpy as np

_MODEL = None


def _load_model():
    global _MODEL
    if _MODEL is not None:
        return _MODEL

    candidates = [
        Path("llm/seca/brain/world_model/world_model.pkl"),
        Path("seca/brain/world_model/world_model.pkl"),
    ]
    for path in candidates:
        if path.exists():
            _MODEL = joblib.load(path)
            return _MODEL

    return None


def _coerce_features(values):
    features = []
    for v in values:
        try:
            features.append(float(v))
        except Exception:
            features.append((abs(hash(str(v))) % 1000) / 1000.0)
    return features


def predict_next_state(state, action_features):
    """
    state: [rating, confidence, accuracy]
    action_features: vector describing training intervention
    """
    model = _load_model()
    if model is None:
        return state

    state_vec = _coerce_features(state)
    action_vec = _coerce_features(action_features)
    x = np.array(state_vec + action_vec, dtype=float).reshape(1, -1)
    preds = model.predict(x)
    delta_rating, delta_conf = preds[0][0], preds[0][1]

    return [
        float(state[0] + delta_rating),
        float(state[1] + delta_conf),
        float(state[2]),
    ]
