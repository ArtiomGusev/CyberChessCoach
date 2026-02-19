import pandas as pd
from sqlalchemy import create_engine, text

DB_PATH = "sqlite:///data/seca.db"
OUT = "llm/seca/brain/eval/offline_bandit_data.csv"


QUERY = """
SELECT
    player_id,
    context_json,
    action,
    reward,
    action_prob,
    created_at
FROM bandit_logs
ORDER BY created_at ASC
"""


def build():
    engine = create_engine(DB_PATH)
    df = pd.read_sql(text(QUERY), engine)

    df.to_csv(OUT, index=False)
    print("Saved:", OUT, "rows:", len(df))


if __name__ == "__main__":
    build()
