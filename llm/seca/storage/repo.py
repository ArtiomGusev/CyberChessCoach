import uuid
from .db import get_conn

# -------------------------------------------------
# Player
# -------------------------------------------------


def ensure_player(player_id: str):
    conn = get_conn()
    try:
        conn.execute(
            "INSERT OR IGNORE INTO players (id) VALUES (?)",
            (player_id,),
        )
        conn.commit()
    finally:
        conn.close()


# -------------------------------------------------
# Game lifecycle
# -------------------------------------------------


def get_or_create_auto_game(player_id: str) -> str:
    """Return a stable per-player game ID for non-session move logging.

    Uses a deterministic `auto-{player_id}` key so all moves from the same
    authenticated player are grouped under one row until a real session system
    replaces this (see server.py /game/start endpoint).
    """
    ensure_player(player_id)
    game_id = f"auto-{player_id}"
    conn = get_conn()
    try:
        conn.execute(
            "INSERT OR IGNORE INTO games (id, player_id) VALUES (?, ?)",
            (game_id, player_id),
        )
        conn.commit()
    finally:
        conn.close()
    return game_id


def create_game(player_id: str) -> str:
    ensure_player(player_id)

    game_id = str(uuid.uuid4())

    conn = get_conn()
    try:
        conn.execute(
            "INSERT INTO games (id, player_id) VALUES (?, ?)",
            (game_id, player_id),
        )
        conn.commit()
    finally:
        conn.close()

    return game_id


def finish_game(game_id: str, result: str):
    conn = get_conn()
    try:
        conn.execute(
            "UPDATE games SET result = ?, finished_at = CURRENT_TIMESTAMP WHERE id = ?",
            (result, game_id),
        )
        conn.commit()
    finally:
        conn.close()


# -------------------------------------------------
# Moves
# -------------------------------------------------


def log_move(game_id: str, ply: int, fen: str, uci: str, san: str, eval: float | None):
    conn = get_conn()
    try:
        conn.execute(
            """
            INSERT INTO moves (game_id, ply, fen, uci, san, eval)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (game_id, ply, fen, uci, san, eval),
        )
        conn.commit()
    finally:
        conn.close()


# -------------------------------------------------
# Explanations
# -------------------------------------------------


def log_explanation(
    game_id: str,
    ply: int,
    explanation_type: str,
    confidence: float,
):
    conn = get_conn()
    try:
        cur = conn.execute(
            """
            INSERT INTO explanations (game_id, ply, explanation_type, confidence)
            VALUES (?, ?, ?, ?)
            """,
            (game_id, ply, explanation_type, confidence),
        )
        conn.commit()
        explanation_id = cur.lastrowid
    finally:
        conn.close()

    return explanation_id


def update_learning_score(explanation_id: int, score: float):
    conn = get_conn()
    try:
        conn.execute(
            "UPDATE explanations SET learning_score = ? WHERE id = ?",
            (score, explanation_id),
        )
        conn.commit()
    finally:
        conn.close()
