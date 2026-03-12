"""
Regression tests for FenMoveCache._cache_key.

Invariants pinned by this test module:

1. KEY FORMAT: The cache key always starts with "fen_move:v2:" (the default
   namespace), followed by a colon, followed by a 64-hex-character SHA-256
   digest.

2. DETERMINISM: Calling _cache_key with identical arguments always returns the
   same key, regardless of call order or timing.

3. SENSITIVITY: The key differs when fen, mode, target_elo, or line_key differ.
   Each of these values participates in the digest.

4. MOVETIME EXCLUSION (documented intentional design): movetime_ms is NOT
   included in the SHA-256 digest. Two calls that differ only in movetime_ms
   return the same cache key. This is a deliberate coarsening to improve cache
   hit rates across requests that differ only in think-time budget. Any change
   to include movetime_ms in the digest would be a breaking cache-key change
   and must be accompanied by a namespace bump (e.g. "fen_move:v3").

5. NONE LINE_KEY SENTINEL: Passing line_key=None produces the same key as
   omitting line_key entirely (the default is None). The implementation
   normalises None to the string "-" before hashing.
"""
import hashlib

import pytest

from llm.seca.engines.stockfish.pool import FenMoveCache

_STARTPOS_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
_FEN_AFTER_E4 = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1"


def _make_cache() -> FenMoveCache:
    return FenMoveCache(redis_url=None)


# ---------------------------------------------------------------------------
# Key format
# ---------------------------------------------------------------------------

def test_cache_key_starts_with_namespace():
    cache = _make_cache()
    key = cache._cache_key(
        fen=_STARTPOS_FEN,
        mode="default",
        movetime_ms=40,
        target_elo=None,
    )
    assert key.startswith("fen_move:v2:"), (
        f"Key must start with 'fen_move:v2:' but got: {key!r}"
    )


def test_cache_key_digest_is_64_hex_chars():
    cache = _make_cache()
    key = cache._cache_key(
        fen=_STARTPOS_FEN,
        mode="default",
        movetime_ms=40,
        target_elo=None,
    )
    prefix = "fen_move:v2:"
    digest_part = key[len(prefix):]
    assert len(digest_part) == 64, (
        f"SHA-256 hex digest must be 64 chars, got {len(digest_part)}: {digest_part!r}"
    )
    assert all(c in "0123456789abcdef" for c in digest_part), (
        f"Digest must be lowercase hex, got: {digest_part!r}"
    )


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------

def test_cache_key_is_deterministic():
    cache = _make_cache()
    kwargs = dict(
        fen=_STARTPOS_FEN,
        mode="blitz",
        movetime_ms=25,
        target_elo=1500,
        line_key="opening_ruy_lopez",
    )
    key_a = cache._cache_key(**kwargs)
    key_b = cache._cache_key(**kwargs)
    assert key_a == key_b


def test_cache_key_same_across_separate_instances():
    cache1 = _make_cache()
    cache2 = _make_cache()
    kwargs = dict(
        fen=_STARTPOS_FEN,
        mode="training",
        movetime_ms=40,
        target_elo=None,
    )
    assert cache1._cache_key(**kwargs) == cache2._cache_key(**kwargs)


# ---------------------------------------------------------------------------
# Sensitivity: key differs when inputs differ
# ---------------------------------------------------------------------------

def test_cache_key_differs_by_fen():
    cache = _make_cache()
    key_start = cache._cache_key(
        fen=_STARTPOS_FEN, mode="default", movetime_ms=40, target_elo=None
    )
    key_e4 = cache._cache_key(
        fen=_FEN_AFTER_E4, mode="default", movetime_ms=40, target_elo=None
    )
    assert key_start != key_e4


def test_cache_key_differs_by_mode():
    cache = _make_cache()
    key_blitz = cache._cache_key(
        fen=_STARTPOS_FEN, mode="blitz", movetime_ms=40, target_elo=None
    )
    key_analysis = cache._cache_key(
        fen=_STARTPOS_FEN, mode="analysis", movetime_ms=40, target_elo=None
    )
    assert key_blitz != key_analysis


def test_cache_key_differs_by_target_elo():
    cache = _make_cache()
    key_1200 = cache._cache_key(
        fen=_STARTPOS_FEN, mode="default", movetime_ms=40, target_elo=1200
    )
    key_2000 = cache._cache_key(
        fen=_STARTPOS_FEN, mode="default", movetime_ms=40, target_elo=2000
    )
    key_none = cache._cache_key(
        fen=_STARTPOS_FEN, mode="default", movetime_ms=40, target_elo=None
    )
    assert key_1200 != key_2000
    assert key_1200 != key_none
    assert key_2000 != key_none


def test_cache_key_differs_by_line_key():
    cache = _make_cache()
    key_a = cache._cache_key(
        fen=_STARTPOS_FEN,
        mode="default",
        movetime_ms=40,
        target_elo=None,
        line_key="ruy_lopez",
    )
    key_b = cache._cache_key(
        fen=_STARTPOS_FEN,
        mode="default",
        movetime_ms=40,
        target_elo=None,
        line_key="sicilian",
    )
    assert key_a != key_b


# ---------------------------------------------------------------------------
# INVARIANT: movetime_ms is excluded from the digest (documented design)
# ---------------------------------------------------------------------------

def test_cache_key_movetime_ms_excluded_from_digest():
    """
    movetime_ms does NOT participate in the SHA-256 digest.

    This is a documented intentional design decision: cache hits are coarsened
    across requests that differ only in think-time budget. Two calls with
    different movetime_ms values but identical fen, mode, target_elo, and
    line_key must return the same cache key.

    If this test fails after a code change it means the cache-key contract has
    been broken. A namespace bump (e.g. "fen_move:v3") is required alongside
    any change that adds movetime_ms to the digest.
    """
    cache = _make_cache()
    key_fast = cache._cache_key(
        fen=_STARTPOS_FEN,
        mode="default",
        movetime_ms=20,
        target_elo=None,
    )
    key_slow = cache._cache_key(
        fen=_STARTPOS_FEN,
        mode="default",
        movetime_ms=2000,
        target_elo=None,
    )
    assert key_fast == key_slow, (
        "movetime_ms must be excluded from the cache key digest. "
        "Different movetime_ms values with identical other args must produce the same key. "
        "See FenMoveCache._cache_key implementation for the documented rationale."
    )


def test_cache_key_movetime_ms_excluded_with_line_key():
    cache = _make_cache()
    key_a = cache._cache_key(
        fen=_FEN_AFTER_E4,
        mode="training",
        movetime_ms=40,
        target_elo=1500,
        line_key="king_pawn",
    )
    key_b = cache._cache_key(
        fen=_FEN_AFTER_E4,
        mode="training",
        movetime_ms=500,
        target_elo=1500,
        line_key="king_pawn",
    )
    assert key_a == key_b


# ---------------------------------------------------------------------------
# None line_key sentinel equals omitted line_key
# ---------------------------------------------------------------------------

def test_cache_key_none_line_key_equals_omitted_line_key():
    """
    Passing line_key=None must yield the same key as not passing line_key at
    all. The implementation normalises None to '-' before hashing, so both
    call forms are equivalent.
    """
    cache = _make_cache()
    key_explicit_none = cache._cache_key(
        fen=_STARTPOS_FEN,
        mode="default",
        movetime_ms=40,
        target_elo=None,
        line_key=None,
    )
    key_omitted = cache._cache_key(
        fen=_STARTPOS_FEN,
        mode="default",
        movetime_ms=40,
        target_elo=None,
    )
    assert key_explicit_none == key_omitted


def test_cache_key_none_line_key_differs_from_real_line_key():
    cache = _make_cache()
    key_none = cache._cache_key(
        fen=_STARTPOS_FEN,
        mode="default",
        movetime_ms=40,
        target_elo=None,
        line_key=None,
    )
    key_real = cache._cache_key(
        fen=_STARTPOS_FEN,
        mode="default",
        movetime_ms=40,
        target_elo=None,
        line_key="some_line",
    )
    assert key_none != key_real


# ---------------------------------------------------------------------------
# Cross-check: manually reproduce the digest to verify implementation
# ---------------------------------------------------------------------------

def test_cache_key_digest_matches_manual_sha256():
    """Verify that the key is exactly sha256(f'{fen}|{mode}|{target_elo}|{line_key or "-"}')."""
    cache = _make_cache()
    fen = _STARTPOS_FEN
    mode = "blitz"
    target_elo = 1800
    line_key = "sicilian_najdorf"

    key = cache._cache_key(
        fen=fen,
        mode=mode,
        movetime_ms=99,  # excluded from digest
        target_elo=target_elo,
        line_key=line_key,
    )

    raw = f"{fen}|{mode}|{target_elo}|{line_key}".encode("utf-8")
    expected_digest = hashlib.sha256(raw).hexdigest()
    expected_key = f"fen_move:v2:{expected_digest}"

    assert key == expected_key
