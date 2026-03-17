from datetime import timedelta
import pandas as pd
from sqlalchemy import text


# ---------------------------
# Load game events
# ---------------------------
def load_game_events(engine):
    with engine.connect() as conn:
        tables = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'")).fetchall()
    table_names = {t[0] for t in tables}
    if "analytics_events" not in table_names:
        return pd.DataFrame(columns=["player_id", "created_at"])

    query = """
        SELECT player_id, created_at
        FROM analytics_events
        WHERE event_type = 'game_finished'
        ORDER BY created_at ASC
    """
    return pd.read_sql(text(query), engine, parse_dates=["created_at"])


# ---------------------------
# Compute D1/D7/D30 retention
# ---------------------------
def compute_retention(df: pd.DataFrame):
    if df.empty:
        return {}

    first_seen = df.groupby("player_id")["created_at"].min()
    df = df.join(first_seen, on="player_id", rsuffix="_first")

    df["days_since_first"] = (df["created_at"] - df["created_at_first"]).dt.days

    metrics = {}

    for day in [1, 7, 30]:
        retained_players = df[df["days_since_first"] >= day]["player_id"].nunique()
        total_players = first_seen.shape[0]

        metrics[f"D{day}_retention"] = retained_players / total_players if total_players else 0

    return metrics


# ---------------------------
# Weekly session frequency
# ---------------------------
def compute_weekly_sessions(df: pd.DataFrame):
    if df.empty:
        return 0

    df["week"] = df["created_at"].dt.to_period("W")
    sessions_per_player = df.groupby(["player_id", "week"]).size()
    return sessions_per_player.mean()


# ---------------------------
# Public entrypoint
# ---------------------------
def build_retention_report(engine):
    df = load_game_events(engine)

    return {
        **compute_retention(df),
        "weekly_sessions": compute_weekly_sessions(df),
        "players": df["player_id"].nunique(),
        "games": len(df),
    }
