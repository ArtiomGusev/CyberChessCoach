"""
Regression tests for FenMoveCache._cache_key format and partitioning.

engine.md states: "Cached engine results are keyed by normalized FEN plus nodes
or movetime." FenMoveCache uses a different, more specific scheme:

    fen_move:v2:<sha256(fen|mode|target_elo|line_key)>

Key properties documented here:
  - Namespace prefix: "fen_move:v2:" followed by a 64-hex-char SHA-256 digest.
  - Key is partitioned by: fen, mode, target_elo, and line_key.
  - Key is NOT partitioned by movetime_ms (intentional: movetime is coarse-grained
    and not used for cache disambiguation in this path).
  - None line_key is treated identically to an omitted line_key.

Any change to these invariants requires a migration plan for existing cached data
and must update this test suite.
"""
import chess

from llm.seca.engines.stockfish.pool import FenMoveCache

_FEN_AFTER_E4 = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1"


def _cache() -> FenMoveCache:
    return FenMoveCache(redis_url=None)


# ---------------------------------------------------------------------------
# Key format
# ---------------------------------------------------------------------------

def test_cache_key_has_namespace_prefix():
    key = _cache()._cache_key(
        fen=chess.STARTING_FEN,
        mode="blitz",
        movetime_ms=25,
        target_elo=None,
    )
    assert key.startswith("fen_move:v2:"), (
        f"Key '{key}' does not start with 'fen_move:v2:'. "
        "The namespace prefix is part of the stable cache contract."
    )


def test_cache_key_digest_is_64_hex_chars():
    key = _cache()._cache_key(
        fen=chess.STARTING_FEN,
        mode="blitz",
        movetime_ms=25,
        target_elo=None,
    )
    digest = key[len("fen_move:v2:"):]
    assert len(digest) == 64, (
        f"SHA-256 digest should be 64 hex chars, got {len(digest)}: '{digest}'"
    )
    assert all(c in "0123456789abcdef" for c in digest), (
        f"Digest contains non-hex characters: '{digest}'"
    )


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------

def test_cache_key_is_deterministic():
    c = _cache()
    kwargs = dict(fen=chess.STARTING_FEN, mode="blitz", movetime_ms=25, target_elo=1500)
    assert c._cache_key(**kwargs) == c._cache_key(**kwargs)


# ---------------------------------------------------------------------------
# Partitioning — different inputs produce different keys
# ---------------------------------------------------------------------------

def test_cache_key_differs_by_fen():
    c = _cache()
    base = dict(mode="blitz", movetime_ms=25, target_elo=None)
    assert c._cache_key(fen=chess.STARTING_FEN, **base) != c._cache_key(fen=_FEN_AFTER_E4, **base)


def test_cache_key_differs_by_mode():
    c = _cache()
    base = dict(fen=chess.STARTING_FEN, movetime_ms=25, target_elo=None)
    assert c._cache_key(mode="blitz", **base) != c._cache_key(mode="training", **base)
    assert c._cache_key(mode="blitz", **base) != c._cache_key(mode="analysis", **base)
    assert c._cache_key(mode="training", **base) != c._cache_key(mode="analysis", **base)


def test_cache_key_differs_by_target_elo():
    c = _cache()
    base = dict(fen=chess.STARTING_FEN, mode="blitz", movetime_ms=25)
    assert c._cache_key(target_elo=1000, **base) != c._cache_key(target_elo=2000, **base)


def test_cache_key_differs_by_line_key():
    c = _cache()
    base = dict(fen=chess.STARTING_FEN, mode="blitz", movetime_ms=25, target_elo=None)
    assert c._cache_key(line_key="line_a", **base) != c._cache_key(line_key="line_b", **base)


def test_cache_key_differs_when_one_elo_is_none():
    c = _cache()
    base = dict(fen=chess.STARTING_FEN, mode="blitz", movetime_ms=25)
    assert c._cache_key(target_elo=None, **base) != c._cache_key(target_elo=1500, **base)


# ---------------------------------------------------------------------------
# Invariants — same keys despite parameter variation
# ---------------------------------------------------------------------------

def test_cache_key_invariant_to_movetime_ms():
    """
    Document: movetime_ms is present in _cache_key's signature but is NOT
    included in the SHA-256 digest. Two requests for the same position at
    different movetime values share the same FenMoveCache key.

    This is intentional — the cache partitions only by (fen, mode, target_elo,
    line_key). Movetime is considered coarse-grained and not worth splitting the
    cache on.

    Pinning this invariant means any future attempt to include movetime in the
    digest will trip this test and require a migration plan for existing cached data.
    """
    c = _cache()
    base = dict(fen=chess.STARTING_FEN, mode="blitz", target_elo=None)
    key_fast = c._cache_key(movetime_ms=25, **base)
    key_slow = c._cache_key(movetime_ms=2000, **base)
    assert key_fast == key_slow, (
        "movetime_ms must NOT be part of the FenMoveCache key. "
        "If you changed this, update the cache key version and provide a migration plan."
    )


def test_cache_key_none_line_key_equals_omitted():
    """None and omitted line_key produce identical keys (both map to '-' sentinel)."""
    c = _cache()
    base = dict(fen=chess.STARTING_FEN, mode="blitz", movetime_ms=25, target_elo=None)
    assert c._cache_key(line_key=None, **base) == c._cache_key(**base)


# ---------------------------------------------------------------------------
# Custom namespace
# ---------------------------------------------------------------------------

def test_custom_namespace_reflected_in_key():
    c = FenMoveCache(redis_url=None, namespace="custom_ns:v99")
    key = c._cache_key(
        fen=chess.STARTING_FEN,
        mode="blitz",
        movetime_ms=25,
        target_elo=None,
    )
    assert key.startswith("custom_ns:v99:")
