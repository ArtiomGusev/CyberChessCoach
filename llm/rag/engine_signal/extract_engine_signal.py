import chess

_PIECE_CP = {
    chess.PAWN: 100,
    chess.KNIGHT: 320,
    chess.BISHOP: 330,
    chess.ROOK: 500,
    chess.QUEEN: 900,
}


def side_from_fen(fen: str | None) -> str | None:
    if not fen:
        return None
    try:
        return "white" if fen.split()[1] == "w" else "black"
    except Exception:
        return None


def _fen_material_cp(board: chess.Board) -> int:
    return sum(
        _PIECE_CP.get(pt, 0) * (
            len(board.pieces(pt, chess.WHITE)) - len(board.pieces(pt, chess.BLACK))
        )
        for pt in _PIECE_CP
    )


def _fen_phase(board: chess.Board) -> str:
    total = len(board.piece_map())
    has_queens = bool(
        board.pieces(chess.QUEEN, chess.WHITE) | board.pieces(chess.QUEEN, chess.BLACK)
    )
    if board.fullmove_number <= 8 and total >= 28:
        return "opening"
    if total <= 14 or (not has_queens and total <= 20):
        return "endgame"
    return "middlegame"


def _enrich_from_fen(stockfish_json: dict, fen: str | None) -> dict:
    """Fill hollow engine signal fields from FEN when Stockfish data is absent."""
    if fen is None:
        return stockfish_json
    has_eval = bool(stockfish_json.get("evaluation"))
    has_phase = bool(stockfish_json.get("phase"))
    if has_eval and has_phase:
        return stockfish_json
    try:
        board = chess.Board(fen)
    except Exception:
        return stockfish_json
    enriched = dict(stockfish_json)
    if not has_eval:
        enriched["evaluation"] = {"type": "cp", "value": _fen_material_cp(board)}
    if not has_phase:
        enriched["phase"] = _fen_phase(board)
    return enriched


def extract_engine_signal(
    stockfish_json: dict | None,
    *,
    fen: str | None = None,
) -> dict:
    stockfish_json = _enrich_from_fen(stockfish_json or {}, fen)

    evaluation = stockfish_json.get("evaluation", {})
    eval_type = evaluation.get("type", "cp")
    _raw_value = evaluation.get("value", 0)
    try:
        value = int(_raw_value)
    except (TypeError, ValueError):
        value = 0

    # -------------------------
    # MATE (TERMINAL STATE)
    # -------------------------
    if eval_type == "mate":
        side = side_from_fen(fen)
        if side not in ("white", "black"):
            side = "unknown"

        delta = stockfish_json.get("eval_delta", 0)
        if delta >= 50:
            eval_delta = "increase"
        elif delta <= -50:
            eval_delta = "decrease"
        else:
            eval_delta = "stable"

        return {
            "evaluation": {
                "type": "mate",
                "band": "decisive_advantage",
                "side": side,
            },
            "eval_delta": eval_delta,
            "last_move_quality": stockfish_json.get("errors", {}).get(
                "last_move_quality", "unknown"
            ),
            "tactical_flags": stockfish_json.get("tactical_flags", []),
            "position_flags": stockfish_json.get("position_flags", []),
            "phase": stockfish_json.get("phase", "middlegame"),
        }

    # -------------------------
    # CP (NON-TERMINAL STATE)
    # -------------------------
    cp = abs(value)
    if cp <= 20:
        band = "equal"
    elif cp <= 60:
        band = "small_advantage"
    elif cp <= 120:
        band = "clear_advantage"
    else:
        band = "decisive_advantage"

    # Schema contract: value is centipawns from White's perspective.
    # Positive  → White is ahead  → white has the advantage.
    # Negative  → Black is ahead  → black has the advantage.
    # Zero      → equal; attribute to black by convention (band="equal" is primary).
    side = "white" if value > 0 else "black"

    delta = stockfish_json.get("eval_delta", 0)
    if delta >= 50:
        eval_delta = "increase"
    elif delta <= -50:
        eval_delta = "decrease"
    else:
        eval_delta = "stable"

    return {
        "evaluation": {
            "type": "cp",
            "band": band,
            "side": side,
        },
        "eval_delta": eval_delta,
        "last_move_quality": stockfish_json.get("errors", {}).get("last_move_quality", "unknown"),
        "tactical_flags": stockfish_json.get("tactical_flags", []),
        "position_flags": stockfish_json.get("position_flags", []),
        "phase": stockfish_json.get("phase", "middlegame"),
    }
