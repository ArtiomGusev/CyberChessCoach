import random
from dataclasses import dataclass
from typing import Dict, List


# ------------------------------------------------------------
# Data structure returned by sampler
# ------------------------------------------------------------

@dataclass
class CurriculumPosition:
    fen: str
    theme: str
    opponent_rating: float


# ------------------------------------------------------------
# Weakness → theme mapping
# ------------------------------------------------------------

WEAKNESS_THEME_MAP: Dict[str, List[str]] = {
    "time_management": ["complex_middlegame", "imbalanced_position"],
    "tactics": ["sharp_tactic", "sacrifice_attack"],
    "endgame": ["rook_endgame", "king_pawn_endgame"],
    "opening": ["early_opening", "gambit_structure"],
    "calculation": ["forcing_line", "tactical_sequence"],
}


# ------------------------------------------------------------
# Example FEN libraries per theme
# (small handcrafted seed set — later replaced by DB/engine)
# ------------------------------------------------------------

THEME_FENS: Dict[str, List[str]] = {
    "complex_middlegame": [
        "r2q1rk1/pp2bppp/2npbn2/2p1p3/2P1P3/2NPBN2/PP2BPPP/R2Q1RK1 w - - 0 10",
        "r1bq1rk1/pp3ppp/2n1pn2/2bp4/2P5/2NP1NP1/PP2PPBP/R1BQ1RK1 w - - 0 9",
    ],
    "sharp_tactic": [
        "r1bqk2r/pppp1ppp/2n5/4p3/2B1P1n1/5N2/PPPP1PPP/RNBQ1RK1 w kq - 2 6",
    ],
    "rook_endgame": [
        "8/8/3k4/8/3K4/8/6R1/8 w - - 0 1",
    ],
    "king_pawn_endgame": [
        "8/8/3k4/8/3K4/4P3/8/8 w - - 0 1",
    ],
    "early_opening": [
        "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1",
    ],
}


# ------------------------------------------------------------
# Helper functions
# ------------------------------------------------------------

def choose_theme_from_weaknesses(weaknesses: Dict[str, float]) -> str:
    """
    Pick the most severe weakness → corresponding theme.
    """
    if not weaknesses:
        return "complex_middlegame"

    # choose weakness with highest value
    main_weakness = max(weaknesses.items(), key=lambda x: x[1])[0]

    themes = WEAKNESS_THEME_MAP.get(main_weakness)

    if not themes:
        return "complex_middlegame"

    return random.choice(themes)


def choose_fen_for_theme(theme: str) -> str:
    """
    Sample a FEN corresponding to the chosen theme.
    """
    fens = THEME_FENS.get(theme)

    if not fens:
        # fallback generic middlegame
        fens = THEME_FENS["complex_middlegame"]

    return random.choice(fens)


def choose_opponent_rating(player_rating: float, confidence: float) -> float:
    """
    Curriculum difficulty rule:

    Low confidence  → easier opponent  
    High confidence → stronger opponent
    """

    # difficulty shift scaled by confidence
    shift = (confidence - 0.5) * 200  # ±100 ELO

    noise = random.uniform(-50, 50)

    return max(100.0, player_rating + shift + noise)


# ------------------------------------------------------------
# Main sampler API
# ------------------------------------------------------------

def sample_curriculum_position(
    rating: float,
    confidence: float,
    weaknesses: Dict[str, float],
) -> CurriculumPosition:
    """
    Core curriculum sampling logic.
    """

    theme = choose_theme_from_weaknesses(weaknesses)
    fen = choose_fen_for_theme(theme)
    opponent_rating = choose_opponent_rating(rating, confidence)

    return CurriculumPosition(
        fen=fen,
        theme=theme,
        opponent_rating=opponent_rating,
    )
