import pandas as pd
from sklearn.cluster import KMeans
import joblib

DATA = "llm/seca/brain/population/population_dataset.csv"
MODEL = "llm/seca/brain/population/player_clusters.pkl"


def train():
    df = pd.read_csv(DATA)

    X = df[["rating_before", "confidence_before", "accuracy"]]

    model = KMeans(n_clusters=8, random_state=0)
    model.fit(X)

    joblib.dump(model, MODEL)
    print("Player cluster model saved ->", MODEL)


if __name__ == "__main__":
    train()
