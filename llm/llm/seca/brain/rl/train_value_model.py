import pandas as pd
from sklearn.ensemble import RandomForestRegressor
import joblib

DATA = "llm/seca/brain/rl/value_dataset.csv"
MODEL = "llm/seca/brain/rl/value_model.pkl"


def train():
    df = pd.read_csv(DATA)

    X = df[["rating_before", "confidence_before", "accuracy"]]
    y = df["future_gain"]

    model = RandomForestRegressor(n_estimators=200)
    model.fit(X, y)

    joblib.dump(model, MODEL)
    print("Value model saved ->", MODEL)


if __name__ == "__main__":
    train()
