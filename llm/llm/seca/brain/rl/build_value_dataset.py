import pandas as pd

DATA_PATH = "llm/seca/brain/data/world_model_dataset.csv"
OUT_PATH = "llm/seca/brain/rl/value_dataset.csv"

HORIZON = 20  # games into future


def build():
    df = pd.read_csv(DATA_PATH)

    df["future_gain"] = (
        df["rating_after"].rolling(HORIZON, min_periods=1).sum().shift(-HORIZON + 1)
        - df["rating_before"]
    )

    df.dropna().to_csv(OUT_PATH, index=False)
    print("Value dataset saved ->", OUT_PATH)


if __name__ == "__main__":
    build()
