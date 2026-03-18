import uuid
from .db import get_conn

# -------------------------------------------------
# Player
# -------------------------------------------------


def ensure_player(player_id: str):
    conn = get_conn()
    conn.execute(
        "INSERT OR IGNORE INTO players (id) VALUES (?)",
        (player_id,),
    )
    conn.commit()
    conn.close()


# -------------------------------------------------
# Game lifecycle
# -------------------------------------------------


def create_game(player_id: str) -> str:
    ensure_player(player_id)

    game_id = str(uuid.uuid4())

    conn = get_conn()
    conn.execute(
        "INSERT INTO games (id, player_id) VALUES (?, ?)",
        (game_id, player_id),
    )
    conn.commit()
    conn.close()

    return game_id


def finish_game(game_id: str, result: str):
    conn = get_conn()
    conn.execute(
        "UPDATE games SET result = ?, finished_at = CURRENT_TIMESTAMP WHERE id = ?",
        (result, game_id),
    )
    conn.commit()
    conn.close()


# -------------------------------------------------
# Moves
# -------------------------------------------------


def log_move(game_id: str, ply: int, fen: str, uci: str, san: str, eval: float | None):
    conn = get_conn()
    conn.execute(
        """
        INSERT INTO moves (game_id, ply, fen, uci, san, eval)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (game_id, ply, fen, uci, san, eval),
    )
    conn.commit()
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
    cur = conn.execute(
        """
        INSERT INTO explanations (game_id, ply, explanation_type, confidence)
        VALUES (?, ?, ?, ?)
        """,
        (game_id, ply, explanation_type, confidence),
    )
    conn.commit()
    explanation_id = cur.lastrowid
    conn.close()

    return explanation_id


def update_learning_score(explanation_id: int, score: float):
    conn = get_conn()
    conn.execute(
        "UPDATE explanations SET learning_score = ? WHERE id = ?",
        (score, explanation_id),
    )
    conn.commit()
    conn.close()
