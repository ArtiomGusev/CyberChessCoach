import pandas as pd
from sqlalchemy import text

DEFAULT_RATING = 1200.0


# ---------------------------
# Load rating transitions
# ---------------------------
def load_rating_transitions(engine):
    with engine.connect() as conn:
        tables = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'")).fetchall()
    table_names = {t[0] for t in tables}
    if "game_events" not in table_names:
        return pd.DataFrame(columns=["player_id", "created_at", "result", "accuracy"])

    query = """
        SELECT
            ge.player_id,
            ge.created_at,
            ge.result,
            ge.accuracy
        FROM game_events ge
        ORDER BY ge.created_at ASC
    """
    df = pd.read_sql(text(query), engine, parse_dates=["created_at"])
    return add_rating_transitions(df)


def apply_rating_update(rating: float, result: str, accuracy: float) -> float:
    if result == "win":
        delta = 12
    elif result == "loss":
        delta = -12
    else:
        delta = 2

    delta += (accuracy - 0.5) * 10
    return max(100.0, rating + delta)


def add_rating_transitions(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        df["rating_before"] = []
        df["rating_after"] = []
        return df

    ratings = {}
    rating_before = []
    rating_after = []

    for row in df.itertuples(index=False):
        player_id = row.player_id
        r_before = ratings.get(player_id, DEFAULT_RATING)
        r_after = apply_rating_update(
            r_before,
            row.result,
            row.accuracy if row.accuracy is not None else 0.5,
        )

        rating_before.append(r_before)
        rating_after.append(r_after)
        ratings[player_id] = r_after

    df = df.copy()
    df["rating_before"] = rating_before
    df["rating_after"] = rating_after
    return df


# ---------------------------
# Detect "plan usage" proxy
# ---------------------------
def detect_plan_usage(df: pd.DataFrame, window_days: int = 7):
    """
    Proxy rule:
    Player used SECA plan if they played >=2 games within N days.
    """
    df = df.copy()

    df["prev_game_time"] = df.groupby("player_id")["created_at"].shift(1)
    df["days_since_prev"] = (df["created_at"] - df["prev_game_time"]).dt.days

    df["used_plan"] = df["days_since_prev"].fillna(999) <= window_days
    return df


# ---------------------------
# Compute rating deltas
# ---------------------------
def compute_rating_deltas(df: pd.DataFrame):
    df = df.copy()
    df["delta"] = df["rating_after"] - df["rating_before"]
    return df


# ---------------------------
# Aggregate effectiveness
# ---------------------------
def compute_effectiveness(df: pd.DataFrame):
    if df.empty:
        return {}

    grouped = df.groupby("used_plan")["delta"].mean()

    with_plan = float(grouped.get(True, 0))
    without_plan = float(grouped.get(False, 0))

    lift = with_plan - without_plan

    return {
        "avg_delta_with_plan": with_plan,
        "avg_delta_without_plan": without_plan,
        "learning_lift": lift,
    }


# ---------------------------
# Public entrypoint
# ---------------------------
def build_effectiveness_report(engine):
    df = load_rating_transitions(engine)
    if df.empty:
        return {
            "avg_delta_with_plan": 0,
            "avg_delta_without_plan": 0,
            "learning_lift": 0,
            "samples": 0,
            "players": 0,
        }
    df = detect_plan_usage(df)
    df = compute_rating_deltas(df)

    metrics = compute_effectiveness(df)

    metrics["samples"] = len(df)
    metrics["players"] = df["player_id"].nunique()

    return metrics
