"""
SECA Self-Play Game Simulator

Purpose
-------
Simulate a full chess game starting from a curriculum FEN and
produce a payload compatible with /game/finish.

This is intentionally lightweight and engine-agnostic so it can run
in research loops or CI without Stockfish. Later we can swap the
move policy with a real engine or neural policy.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Dict, List, Optional


# ============================================================
# Data structures
# ============================================================


@dataclass
class SimulatedGameResult:
    pgn: str
    result: str  # "win" | "loss" | "draw"
    accuracy: float
    weaknesses: Dict[str, float]


# ============================================================
# Simple pseudo-chess move generator
# ============================================================
# NOTE:
# We intentionally avoid heavy chess dependencies.
# This produces synthetic but structurally valid PGN strings
# sufficient for backend learning pipelines.
# ============================================================

PIECE_MOVES = [
    "e4",
    "d4",
    "Nf3",
    "c4",
    "e5",
    "d5",
    "Nc6",
    "Nf6",
    "Bb5",
    "Bc4",
    "O-O",
    "Re1",
    "Qh5",
    "Qf3",
    "g3",
    "b3",
]

RESULTS = ["win", "loss", "draw"]


# ============================================================
# Core simulation logic
# ============================================================


def _simulate_move_sequence(max_moves: int = 40) -> List[str]:
    """Generate a synthetic sequence of SAN moves."""

    moves: List[str] = []

    for turn in range(1, max_moves + 1):
        white_move = random.choice(PIECE_MOVES)
        moves.append(f"{turn}. {white_move}")

        # 10% chance game ends early
        if random.random() < 0.10:
            break

        black_move = random.choice(PIECE_MOVES)
        moves[-1] += f" {black_move}"

        # 10% chance game ends after black move
        if random.random() < 0.10:
            break

    return moves


def _estimate_accuracy(confidence: float, opponent_rating: float, player_rating: float) -> float:
    """
    Rough synthetic accuracy model.

    Higher confidence -> higher accuracy.
    Stronger opponent -> lower accuracy.
    """

    base = 0.6 + (confidence - 0.5) * 0.3

    rating_diff = opponent_rating - player_rating
    difficulty_penalty = rating_diff / 1000.0

    noise = random.uniform(-0.05, 0.05)

    acc = base - difficulty_penalty + noise

    return max(0.1, min(0.99, acc))


def _sample_result(accuracy: float) -> str:
    """Map accuracy -> probabilistic game result."""

    win_p = accuracy
    draw_p = 0.15
    loss_p = max(0.0, 1.0 - win_p - draw_p)

    r = random.random()

    if r < win_p:
        return "win"
    if r < win_p + draw_p:
        return "draw"
    return "loss"


def _infer_weakness_updates(result: str, accuracy: float) -> Dict[str, float]:
    """
    Produce synthetic weakness signals for analytics learning.

    Idea:
    - Low accuracy -> tactical/calculation weakness
    - Draw -> endgame/time pressure signal
    - Loss -> multiple weaknesses amplified
    """

    weaknesses: Dict[str, float] = {}

    if accuracy < 0.5:
        weaknesses["tactics"] = round(1.0 - accuracy, 3)
        weaknesses["calculation"] = round(0.8 - accuracy / 2, 3)

    if result == "draw":
        weaknesses["endgame"] = round(0.3 + (0.6 - accuracy), 3)

    if result == "loss":
        weaknesses["time_management"] = round(0.5 + (0.5 - accuracy), 3)

    return weaknesses


# ============================================================
# Public API
# ============================================================


def simulate_game(
    *,
    start_fen: str,
    theme: str,
    player_rating: float,
    opponent_rating: float,
    confidence: float,
    max_moves: int = 40,
) -> SimulatedGameResult:
    """
    Run a full synthetic game simulation.

    Parameters
    ----------
    start_fen : str
        Curriculum starting position.
    theme : str
        Training theme label.
    player_rating : float
    opponent_rating : float
    confidence : float
    max_moves : int

    Returns
    -------
    SimulatedGameResult
        Ready to POST into /game/finish.
    """

    # 1) Generate synthetic PGN
    moves = _simulate_move_sequence(max_moves=max_moves)

    pgn = " ".join(moves)

    # 2) Estimate accuracy
    accuracy = _estimate_accuracy(confidence, opponent_rating, player_rating)

    # 3) Sample result
    result = _sample_result(accuracy)

    # 4) Weakness analytics
    weaknesses = _infer_weakness_updates(result, accuracy)

    return SimulatedGameResult(
        pgn=pgn,
        result=result,
        accuracy=round(accuracy, 3),
        weaknesses=weaknesses,
    )


# ============================================================
# Quick manual test
# ============================================================


if __name__ == "__main__":
    game = simulate_game(
        start_fen="startpos",
        theme="complex_middlegame",
        player_rating=1200,
        opponent_rating=1250,
        confidence=0.55,
    )

    print("=== Simulated Game ===")
    print(game)
