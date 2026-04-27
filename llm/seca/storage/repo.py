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
# In-progress checkpoint (cross-device resume)
# -------------------------------------------------


def checkpoint_game(game_id: str, fen: str, uci_history: str) -> bool:
    """Persist the in-progress state for [game_id].  No-ops (returns
    False) when the row is already finished or doesn't exist — sliding
    a checkpoint onto a closed game would create a phantom resume
    entry the user couldn't actually pick up.

    Returns True iff the UPDATE touched a row.
    """
    conn = get_conn()
    try:
        cur = conn.execute(
            """
            UPDATE games
               SET current_fen = ?,
                   current_uci_history = ?,
                   last_checkpoint_at = CURRENT_TIMESTAMP
             WHERE id = ?
               AND finished_at IS NULL
            """,
            (fen, uci_history, game_id),
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def get_active_game(player_id: str) -> dict | None:
    """Return the player's most recent unfinished game with a
    non-null checkpoint, or None if there isn't one.

    Shape (when present):
        {
          "game_id":             str,
          "current_fen":         str,
          "current_uci_history": str,
          "last_checkpoint_at":  str (ISO timestamp),
          "started_at":          str (ISO timestamp),
        }

    Filters:
      - Same player_id.
      - finished_at IS NULL  (unfinished).
      - current_fen IS NOT NULL  (a checkpoint was actually written;
        avoids returning rows for /game/start calls where the user
        never played a single move).

    Order: most-recent last_checkpoint_at first, so a multi-game
    history returns the user's last active session, not an ancient
    one.
    """
    conn = get_conn()
    try:
        row = conn.execute(
            """
            SELECT id,
                   current_fen,
                   current_uci_history,
                   last_checkpoint_at,
                   started_at
              FROM games
             WHERE player_id = ?
               AND finished_at IS NULL
               AND current_fen IS NOT NULL
             ORDER BY last_checkpoint_at DESC
             LIMIT 1
            """,
            (player_id,),
        ).fetchone()
    finally:
        conn.close()

    if row is None:
        return None
    return {
        "game_id": row[0],
        "current_fen": row[1],
        "current_uci_history": row[2] or "",
        "last_checkpoint_at": row[3],
        "started_at": row[4],
    }


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
