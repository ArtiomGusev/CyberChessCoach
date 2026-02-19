import pandas as pd

SRC = "llm/seca/brain/data/world_model_dataset.csv"
VALUE_SRC = "llm/seca/brain/rl/value_dataset.csv"
OUT = "llm/seca/brain/population/population_dataset.csv"


def build():
    base = pd.read_csv(SRC)
    if "future_gain" in base.columns:
        df = base
    else:
        value = pd.read_csv(VALUE_SRC)
        df = base.merge(
            value[["rating_before", "confidence_before", "accuracy", "future_gain"]],
            on=["rating_before", "confidence_before", "accuracy"],
            how="left",
        )

    cols = [
        "player_id",
        "rating_before",
        "confidence_before",
        "accuracy",
        "future_gain",
    ]

    df[cols].dropna().to_csv(OUT, index=False)
    print("Population dataset saved ->", OUT)


if __name__ == "__main__":
    build()
