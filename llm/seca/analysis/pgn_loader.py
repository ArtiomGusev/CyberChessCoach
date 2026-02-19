import chess.pgn


def load_game(pgn_text: str):
    """
    Returns a python-chess Game object.
    """
    return chess.pgn.read_game(io := chess.pgn.StringIO(pgn_text))
