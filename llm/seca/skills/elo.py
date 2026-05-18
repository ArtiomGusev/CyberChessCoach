"""Standard Elo rating math for the SECA SkillUpdater.

Replaces the pre-PR-#174 homebrew formula
(``win=+12 / loss=-12 + (accuracy − 0.5) * 10``) with FIDE-style
classic Elo so the player's rating in this app tracks the same scale
they see on chess.com / lichess.  K-factor banding follows FIDE's
published table.

Why standard Elo (not Glicko-2)
-------------------------------
chess.com and lichess publicly use Glicko-2 (an Elo refinement that
tracks rating deviation + volatility alongside the point estimate).
Glicko-2 produces tighter ratings faster in cold-start regimes but
adds three extra state fields per player (RD, vol, last-rated-at).

Classic Elo is a faithful approximation here because:

* Every match has exactly one opponent (no multi-game rated periods
  where Glicko-2 outperforms).
* Opponent rating is auto-tuned to the player by the SECA adaptive
  engine (``compute_adaptation`` -> ``target_elo``), so the
  rating-vs-strength asymmetry Glicko-2 specifically defends against
  rarely materialises in this app.
* We don't publish ratings to external systems — the scale just
  needs to FEEL like chess.com/lichess so the user can compare.

Glicko-2 migration is a documented future direction; the K-factor
table here is the single load-bearing parameter set, and a future
Glicko-2 swap would replace the entire module without touching
callers.
"""

from __future__ import annotations


# ---------------------------------------------------------------------------
# K-factor bands — FIDE table
# ---------------------------------------------------------------------------
# Reference: FIDE Rating Regulations §8.5.2 (2022 revision).
#
#   K = 40   for new players (<30 rated games) with rating <2400
#   K = 20   for established players (>=30 games) with rating <2400
#   K = 10   for masters (rating >=2400)
#
# The same table is used by lichess for their classic-rated games
# (their Glicko-2 implementation collapses to roughly these K values
# in the limit of large rating-deviation -> K=40, small RD -> K=20).
# chess.com's banding is slightly different (their Glicko-2 RD bands
# do not map cleanly to a discrete K), but their new-account
# behaviour is well-approximated by K=40 for ~30 games.

_K_NEW: int = 40
_K_ESTABLISHED: int = 20
_K_MASTER: int = 10

_MASTER_RATING_THRESHOLD: float = 2400.0
_ESTABLISHED_GAME_THRESHOLD: int = 30

#: Player's score for a draw — half of a win.  Pulled out as a
#: constant so callers don't sprinkle 0.5 literals.  ``actual_score``
#: is named per chess literature ("Sa" in the original Elo paper).
_DRAW_SCORE: float = 0.5

#: Elo's scale factor.  400 means a 400-point rating gap implies
#: roughly a 10:1 win-rate edge for the stronger player.  Identical
#: in chess.com / lichess / FIDE / USCF; if this ever needs to be a
#: configurable parameter the module should swap to a class.
_ELO_SCALE: float = 400.0

#: Hard rating floor matching the long-standing
#: ``player.rating = max(100.0, ...)`` clamp in ``SkillUpdater``.
#: Kept here so the module owns both the delta and the post-clamp
#: behaviour and the SkillUpdater call-site is a single line.
_MIN_RATING: float = 100.0


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def expected_score(player_rating: float, opponent_rating: float) -> float:
    """Standard Elo expected-score formula.

    Returns the probability the player scores 1.0 (a win, in
    draw-counting terms) against an opponent with this rating.

    Always in ``[0, 1]``; ``expected_score(A, B) + expected_score(B, A) == 1``
    (symmetric pair, pinned by
    ``test_elo_expected_score_is_symmetric_pair``).
    """
    return 1.0 / (1.0 + 10.0 ** ((opponent_rating - player_rating) / _ELO_SCALE))


def k_factor(rating: float, games_played: int) -> int:
    """FIDE-style K-factor banding.

    See module docstring for the banding rationale.
    Pinned by ``test_elo_k_factor_banding_new/established/master``.
    """
    if rating >= _MASTER_RATING_THRESHOLD:
        return _K_MASTER
    if games_played < _ESTABLISHED_GAME_THRESHOLD:
        return _K_NEW
    return _K_ESTABLISHED


def actual_score_from_result(result: str) -> float:
    """Map a ``GameEvent.result`` string to its Elo score.

    Canonical chess result encoding:
      ``"win"``  -> 1.0
      ``"draw"`` -> 0.5
      ``"loss"`` -> 0.0

    Unknown / empty strings collapse to 0.5 (draw) to bias the
    rating change toward zero rather than risk a fabricated win or
    loss.  The SkillUpdater call site is expected to log an
    operator-visible warning in that case; this module stays pure-
    mathematical.
    """
    r = (result or "").strip().lower()
    if r == "win":
        return 1.0
    if r == "loss":
        return 0.0
    return _DRAW_SCORE


def compute_rating_delta(
    player_rating: float,
    opponent_rating: float,
    actual_score: float,
    games_played: int,
) -> float:
    """Standard Elo rating-change formula.

    Δ = K · (actual_score − expected_score)

    Where ``actual_score`` is 1.0 for a win, 0.5 for a draw, 0.0 for
    a loss (use ``actual_score_from_result`` to derive from a
    ``GameEvent.result`` string).  ``K`` is banded by player rating
    and games played per ``k_factor``.

    Pinned by ``test_elo_*_delta_*`` invariants.
    """
    expected = expected_score(player_rating, opponent_rating)
    k = float(k_factor(player_rating, games_played))
    return k * (actual_score - expected)


def apply_rating_delta(rating: float, delta: float) -> float:
    """Apply a delta with the ``_MIN_RATING`` floor.

    Exists as a helper so the SkillUpdater call-site stays a single
    line and the floor lives next to the math that derived the
    delta.  Pinned by ``test_elo_rating_floor_prevents_dropping_below_100``.
    """
    return max(_MIN_RATING, rating + delta)
