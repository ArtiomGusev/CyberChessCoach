import joblib
import pandas as pd

CLUSTERS = "llm/seca/brain/population/player_clusters.pkl"
DATA = "llm/seca/brain/population/population_dataset.csv"

cluster_model = joblib.load(CLUSTERS)
df = pd.read_csv(DATA)


def best_action_for_state(state):
    cluster = cluster_model.predict([state])[0]

    subset = df.iloc[cluster_model.labels_ == cluster]

    if len(subset) == 0:
        return "tactics_easy"

    best_row = subset.sort_values("future_gain", ascending=False).iloc[0]

    return best_row.get("recommended_action", "tactics_easy")
