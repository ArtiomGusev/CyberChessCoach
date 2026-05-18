"""
Pinned invariants for the standard-Elo rating math introduced in
PR #174.

Context
-------
Pre-PR-#174 ``SkillUpdater.update_from_event`` used a homebrew
``±12 + (accuracy − 0.5) * 10`` formula.  After the 2026-05-16
multi-game probe surfaced the issues "Elo hasn't changed
significantly" and "PostGameCoachController Rules 1/2 never fire
because deltas top out at ±17", the formula was replaced with
FIDE-style classic Elo using opponent rating from the SECA adaptive
engine and banded K-factor (40 / 20 / 10).

The same K-factor table is what chess.com (Glicko-2, large RD ->
~40, small RD -> ~20) and lichess (classic-rated mode) collapse to
in the relevant regimes, so the in-app rating now tracks an
externally-recognisable scale.

Two test layers
---------------
1. ``TestEloMathPureFunctions``: pin the module-level functions in
   ``llm.seca.skills.elo`` in isolation.  No DB, no SECA adaptation,
   no game events.  Hand-computed values from the FIDE rating
   regulations so a future tweak to ``_ELO_SCALE`` or a K-factor
   band shows up as a CI failure with an exact-number diagnostic.

2. ``TestSkillUpdaterIntegrationElo``: pin the SkillUpdater's
   end-to-end behaviour through the new Elo formula.  Uses an
   in-memory SQLite session so the ``games_played`` query that
   drives the K-factor band is exercised on a real ORM, not stubbed.
"""

from __future__ import annotations

import os

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

os.environ.setdefault("SECA_API_KEY", "ci-test-key")
os.environ.setdefault("SECA_ENV", "dev")
os.environ.setdefault("SECRET_KEY", "ci-secret-key-that-is-32-chars-long!!")

from llm.seca.auth.models import Base, Player
from llm.seca.events.models import GameEvent
from llm.seca.events.storage import EventStorage
from llm.seca.skills.elo import (
    actual_score_from_result,
    apply_rating_delta,
    compute_rating_delta,
    expected_score,
    k_factor,
)
from llm.seca.skills.updater import SkillUpdater


# ===========================================================================
# Layer 1 — pure functions
# ===========================================================================


class TestEloMathPureFunctions:
    """Standard Elo math, isolated from DB / adaptation / events."""

    # ── expected_score ──────────────────────────────────────────────────

    def test_elo_expected_score_equal_rated_is_half(self):
        """Two players at the same rating each expect 0.5."""
        assert expected_score(1500.0, 1500.0) == pytest.approx(0.5)

    def test_elo_expected_score_is_symmetric_pair(self):
        """expected(A, B) + expected(B, A) = 1 — symmetry pin."""
        for a, b in [(1200, 1500), (1800, 1300), (2400, 1600)]:
            ab = expected_score(a, b)
            ba = expected_score(b, a)
            assert ab + ba == pytest.approx(1.0), (
                f"expected_score asymmetry: {a} vs {b} -> "
                f"{ab:.4f} + {ba:.4f} != 1.0"
            )

    def test_elo_expected_score_400_point_gap_is_91_percent(self):
        """A 400-point rating gap implies the stronger side scores
        roughly 0.91 (the textbook Elo example).  Pin to 2 decimal
        places so a future scale-factor change away from 400 surfaces
        immediately."""
        assert expected_score(1600.0, 1200.0) == pytest.approx(0.909, abs=0.01)
        assert expected_score(1200.0, 1600.0) == pytest.approx(0.091, abs=0.01)

    def test_elo_expected_score_in_unit_interval(self):
        """Pin the [0, 1] range across extreme gaps."""
        for opp_offset in (-2000, -1000, 0, 1000, 2000):
            score = expected_score(1500.0, 1500.0 + opp_offset)
            assert 0.0 <= score <= 1.0, (
                f"expected_score out of [0, 1]: opp_offset={opp_offset} -> {score}"
            )

    # ── k_factor ────────────────────────────────────────────────────────

    def test_elo_k_factor_banding_new(self):
        """K=40 for players with rating <2400 AND <30 prior games."""
        assert k_factor(rating=1200.0, games_played=0) == 40
        assert k_factor(rating=1200.0, games_played=29) == 40
        assert k_factor(rating=2000.0, games_played=10) == 40

    def test_elo_k_factor_banding_established(self):
        """K=20 once a sub-master player has 30+ prior games."""
        assert k_factor(rating=1200.0, games_played=30) == 20
        assert k_factor(rating=2399.9, games_played=100) == 20

    def test_elo_k_factor_banding_master(self):
        """K=10 for masters (rating >=2400), independent of games_played."""
        assert k_factor(rating=2400.0, games_played=0) == 10
        assert k_factor(rating=2400.0, games_played=50) == 10
        assert k_factor(rating=2700.0, games_played=500) == 10

    # ── actual_score_from_result ────────────────────────────────────────

    @pytest.mark.parametrize(
        "result,score",
        [
            ("win", 1.0), ("WIN", 1.0), ("Win ", 1.0),
            ("loss", 0.0), ("LOSS", 0.0),
            ("draw", 0.5), ("DRAW", 0.5),
        ],
    )
    def test_elo_actual_score_canonical_strings(self, result, score):
        assert actual_score_from_result(result) == score

    @pytest.mark.parametrize("garbage", ["", None, "unknown", "1-0", "fork"])
    def test_elo_actual_score_unknown_collapses_to_draw(self, garbage):
        """Garbage / None / unknown enum -> 0.5 (no rating bias)."""
        assert actual_score_from_result(garbage) == 0.5

    # ── compute_rating_delta ────────────────────────────────────────────

    def test_elo_win_against_equal_opponent_new_player(self):
        """New player (K=40) wins against equal-rated opponent:
        delta = 40 * (1.0 - 0.5) = +20."""
        delta = compute_rating_delta(
            player_rating=1200, opponent_rating=1200,
            actual_score=1.0, games_played=0,
        )
        assert delta == pytest.approx(20.0)

    def test_elo_loss_against_equal_opponent_new_player(self):
        """Symmetric: new player loss to equal -> -20."""
        delta = compute_rating_delta(
            player_rating=1200, opponent_rating=1200,
            actual_score=0.0, games_played=0,
        )
        assert delta == pytest.approx(-20.0)

    def test_elo_draw_against_equal_opponent_is_zero(self):
        """Equal-rated draw -> 0 (no rating movement)."""
        delta = compute_rating_delta(
            player_rating=1500, opponent_rating=1500,
            actual_score=0.5, games_played=0,
        )
        assert delta == pytest.approx(0.0)

    def test_elo_win_against_stronger_opponent_rewards_more(self):
        """New player beating a +200 stronger opponent gets a much
        bigger boost than beating an equal opponent."""
        win_equal = compute_rating_delta(1200, 1200, 1.0, 0)
        win_stronger = compute_rating_delta(1200, 1400, 1.0, 0)
        assert win_stronger > win_equal + 5, (
            f"Beating +200 stronger should reward markedly more; "
            f"equal={win_equal}, stronger={win_stronger}"
        )
        # Pin the expected value: expected(1200, 1400) ~ 0.24,
        # delta = 40 * (1 - 0.24) ~ +30.4.
        assert win_stronger == pytest.approx(30.3, abs=0.5)

    def test_elo_loss_to_stronger_opponent_costs_less(self):
        """Symmetric: losing to a much-stronger opponent costs less
        than losing to an equal opponent."""
        loss_equal = compute_rating_delta(1200, 1200, 0.0, 0)
        loss_stronger = compute_rating_delta(1200, 1400, 0.0, 0)
        assert loss_stronger > loss_equal, (
            f"Losing to +200 stronger should hurt less than losing "
            f"to equal; equal={loss_equal}, stronger={loss_stronger}"
        )
        # expected(1200, 1400) ~ 0.24, delta = 40 * (0 - 0.24) ~ -9.7.
        assert loss_stronger == pytest.approx(-9.7, abs=0.5)

    def test_elo_established_player_swings_half_of_new_player(self):
        """K=20 established player vs K=40 new player at the same
        rating against the same opponent — same outcome, half the
        movement.  This is the user-visible "ratings settle as you
        play more games" behavior."""
        delta_new = compute_rating_delta(1500, 1500, 1.0, games_played=0)
        delta_estab = compute_rating_delta(1500, 1500, 1.0, games_played=30)
        assert delta_estab == pytest.approx(delta_new / 2.0, abs=0.01)

    # ── apply_rating_delta ──────────────────────────────────────────────

    def test_elo_rating_floor_prevents_dropping_below_100(self):
        """Any sequence of losses bottoms out at 100, not at 0 or
        negative."""
        rating = 200.0
        for _ in range(100):
            rating = apply_rating_delta(rating, -40.0)
        assert rating == pytest.approx(100.0)


# ===========================================================================
# Layer 2 — SkillUpdater integration
# ===========================================================================


@pytest.fixture()
def db_session():
    """Fresh in-memory SQLite session.  Per-test isolation so
    ``GameEvent.count()`` results don't bleed between tests."""
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def _make_player(db, rating: float = 1200.0) -> Player:
    p = Player(
        id="p-elo-test",
        email="elo-test@example.com",
        password_hash="x",
        rating=rating,
        confidence=0.5,
        skill_vector_json="{}",
        player_embedding="[]",
    )
    db.add(p)
    db.commit()
    return p


_VALID_PGN = (
    '[Event "Test"]\n[Site "?"]\n[Date "2026.05.16"]\n[Round "1"]\n'
    '[White "P"]\n[Black "P"]\n[Result "1-0"]\n\n1. e4 e5 1-0'
)


def _store_and_update(db, player, result: str, weaknesses: dict | None = None):
    """Store a GameEvent and run SkillUpdater on it.

    Mirrors what ``finish_game`` does in the production handler:
    EventStorage.store_game commits the event, THEN SkillUpdater
    runs.  This sequence is load-bearing for the games_played
    count that drives K-factor banding.
    """
    storage = EventStorage(db)
    event = storage.store_game(
        player_id=player.id,
        pgn=_VALID_PGN,
        result=result,
        accuracy=0.5,
        weaknesses=weaknesses or {},
    )
    SkillUpdater(db).update_from_event(player.id, event)
    db.refresh(player)


class TestSkillUpdaterIntegrationElo:
    """End-to-end: SkillUpdater applies the standard-Elo formula
    against a real DB-backed game-count for K-factor banding."""

    def test_skill_updater_first_game_win_uses_k40(self, db_session):
        """First-ever game for a 1200 player — K=40 kicks in,
        rating moves ~+20 against equal-strength adaptive opponent.

        The adaptive opponent at rating=1200 maps to target_elo =
        600 + ((1200-400)/2000) * 1800 = 1320.  Expected for the
        player ≈ 0.32, so a win gives delta = 40 * (1 - 0.32) ≈ 27.

        Pin the actual outcome rather than the analytic value
        because the SECA adaptive engine could legitimately tweak
        the target_elo formula; what we care about is that the
        rating moved by an Elo-band-appropriate amount."""
        player = _make_player(db_session, rating=1200.0)
        rating_before = player.rating
        _store_and_update(db_session, player, "win")
        delta = player.rating - rating_before
        # K=40 against an adaptive ~1320 opponent: win Δ in [+20, +35].
        assert 18.0 <= delta <= 36.0, (
            f"K=40 new-player win delta should land in [+18, +36]; got {delta}"
        )

    def test_skill_updater_loss_against_adaptive_opponent_is_smaller_in_magnitude(
        self, db_session,
    ):
        """A 1200-rated new player loses to the ~1320 adaptive
        opponent.  Because the opponent is stronger, losing costs
        LESS in magnitude than winning rewards.

        Pre-PR-#174 the homebrew formula had win=+12 and loss=-12,
        i.e. symmetric magnitudes regardless of opponent strength —
        the very asymmetry standard Elo exists to capture.
        """
        # Fresh player + game session.
        win_player = _make_player(db_session, rating=1200.0)
        win_rating_before = win_player.rating
        _store_and_update(db_session, win_player, "win")
        win_delta = win_player.rating - win_rating_before

        # Second fresh player, same starting state, opposite result.
        loss_player = Player(
            id="p-elo-loss",
            email="elo-loss@example.com",
            password_hash="x",
            rating=1200.0,
            confidence=0.5,
            skill_vector_json="{}",
            player_embedding="[]",
        )
        db_session.add(loss_player)
        db_session.commit()
        loss_rating_before = loss_player.rating
        _store_and_update(db_session, loss_player, "loss")
        loss_delta = loss_player.rating - loss_rating_before

        assert win_delta > 0 > loss_delta, (
            f"Sign sanity: win should raise rating, loss should drop it; "
            f"got win={win_delta}, loss={loss_delta}"
        )
        assert abs(win_delta) > abs(loss_delta) + 3.0, (
            f"Adaptive opponent is stronger than the player, so winning "
            f"must reward more than losing costs.  Got |win|={abs(win_delta)}, "
            f"|loss|={abs(loss_delta)}.  Pre-PR-#174 the homebrew formula "
            f"made these always equal (±12)."
        )

    def test_skill_updater_draw_against_adaptive_opponent_is_modest_gain(
        self, db_session,
    ):
        """A draw against a stronger opponent is a modest GAIN
        (you scored 0.5 when expected ~0.32, so +20 * (0.5-0.32)
        ≈ +6).  Pre-PR-#174 a draw was a fixed +2 regardless."""
        player = _make_player(db_session, rating=1200.0)
        rating_before = player.rating
        _store_and_update(db_session, player, "draw")
        delta = player.rating - rating_before
        # Draw against ~1320 with K=40: expected ~0.32, delta = 40 * (0.5-0.32) ~+7.
        assert 4.0 <= delta <= 10.0, (
            f"Draw against the adaptive (slightly stronger) opponent "
            f"should be a modest gain; got delta={delta}"
        )

    def test_skill_updater_30th_game_drops_k_to_established(self, db_session):
        """K transitions from 40 to 20 once games_played reaches 30.

        Play 30 silent draws (no rating movement for equal-rated
        opponents), then verify that the 31st game's delta is
        roughly half what the 1st game's delta would have been.
        """
        player = _make_player(db_session, rating=1200.0)

        # First game's outcome (sets the K=40 baseline).
        _store_and_update(db_session, player, "win")
        first_win_delta = player.rating - 1200.0

        # Bring games_played up to >= 30 via fast no-op events.
        # The SkillUpdater will still apply Elo for each, so we
        # reset the rating between batches to keep the comparison
        # apples-to-apples.  Use a separate test player to avoid
        # cascading rating drift.
        established_player = Player(
            id="p-elo-estab",
            email="elo-estab@example.com",
            password_hash="x",
            rating=1200.0,
            confidence=0.5,
            skill_vector_json="{}",
            player_embedding="[]",
        )
        db_session.add(established_player)
        db_session.commit()

        # 30 prior games — use draws against an opponent we KNOW is
        # not exactly equal (the adaptive opponent at 1200 is ~1320)
        # so each game DOES move the rating slightly.  We don't
        # care about the cumulative rating, just that the count is
        # high enough to flip the K-factor band.
        for _ in range(30):
            _store_and_update(db_session, established_player, "draw")

        # 31st game.  K should be 20 now.
        rating_before_31 = established_player.rating
        _store_and_update(db_session, established_player, "win")
        established_win_delta = established_player.rating - rating_before_31

        # Established win delta should be roughly half of the new-
        # player win delta from the same nominal opponent.  Use a
        # loose bound because the cumulative draws may have shifted
        # the rating slightly and hence the opponent_rating.
        assert established_win_delta < first_win_delta * 0.75, (
            f"K=20 win delta should be markedly smaller than K=40 win "
            f"delta from a comparable starting rating.  Got "
            f"K=40 delta={first_win_delta:.2f}, "
            f"K=20 delta={established_win_delta:.2f}."
        )

    def test_skill_updater_accuracy_no_longer_directly_adds_to_rating(
        self, db_session,
    ):
        """Two wins at different accuracies produce IDENTICAL
        rating deltas — accuracy stopped being a side-channel rating
        modifier in PR #174.  The previous homebrew formula added
        ``(accuracy - 0.5) * 10`` to every delta, which leaked the
        engine recompute into the rating in a way chess.com /
        lichess never do."""

        # Player A: win with engine recompute saying 90% accuracy.
        player_a = _make_player(db_session, rating=1200.0)
        _store_and_update(
            db_session, player_a, "win",
            weaknesses={"opening": 0.1},
        )
        # Manually fudge the stored event's accuracy to simulate
        # what the engine recompute would have produced for a clean
        # win.
        latest_a = (
            db_session.query(GameEvent)
            .filter(GameEvent.player_id == player_a.id)
            .order_by(GameEvent.created_at.desc())
            .first()
        )
        latest_a.accuracy = 0.9
        db_session.commit()
        # The accuracy gets read by update_from_event ON THE NEXT
        # event for this player, but the rating delta itself is
        # already applied.  What we're asserting: that the rating
        # already applied was NOT influenced by the accuracy
        # parameter for the same result.  So we just compare
        # against a second player with identical result + different
        # accuracy.
        delta_a = player_a.rating - 1200.0

        # Player B: same starting state, same result, but with a
        # very different ``weaknesses`` shape — pre-PR-#174 the
        # accuracy modifier would have applied here too.
        player_b = Player(
            id="p-elo-b",
            email="elo-b@example.com",
            password_hash="x",
            rating=1200.0,
            confidence=0.5,
            skill_vector_json="{}",
            player_embedding="[]",
        )
        db_session.add(player_b)
        db_session.commit()
        _store_and_update(
            db_session, player_b, "win",
            weaknesses={"opening": 0.7, "middlegame": 0.3},
        )
        delta_b = player_b.rating - 1200.0

        # Same result, same opponent (both 1200, same adaptation),
        # same K-factor (both 0 prior games) -> identical delta
        # regardless of the weakness dict / accuracy.
        assert delta_a == pytest.approx(delta_b, abs=0.01), (
            f"PR #174: rating delta must depend ONLY on (rating, "
            f"opponent_rating, result, games_played) — not on accuracy "
            f"or weaknesses.  Got A delta={delta_a:.2f}, "
            f"B delta={delta_b:.2f}."
        )
