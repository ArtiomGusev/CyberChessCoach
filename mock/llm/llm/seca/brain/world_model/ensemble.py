import numpy as np
import joblib
from pathlib import Path


class EnsembleWorldModel:
    def __init__(self, model_dir="llm/seca/brain/world_model", n_models=5):
        self.models = []

        for i in range(n_models):
            path = Path(model_dir) / f"world_model_{i}.pkl"
            if path.exists():
                self.models.append(joblib.load(path))

        if not self.models:
            raise RuntimeError("No ensemble models found")

    # ---------------------------------
    # predict mean + uncertainty
    # ---------------------------------
    def predict(self, x: np.ndarray):
        preds = np.array([m.predict(x.reshape(1, -1))[0] for m in self.models])

        mean = preds.mean(axis=0)
        std = preds.std(axis=0)

        rating_delta = mean[0]
        conf_delta = mean[1]

        rating_unc = std[0]
        conf_unc = std[1]

        return rating_delta, conf_delta, rating_unc, conf_unc
