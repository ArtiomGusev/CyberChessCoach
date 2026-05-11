"""Module-import-time guards in llm/seca/auth/tokens.py.

The two ``raise RuntimeError(...)`` lines at module top-level (the prod-
no-key crash and the < 32-char SECRET_KEY crash) are part of the security
contract:

  TGUARD_01  Production import with no SECRET_KEY env var crashes the
             process immediately rather than minting JWTs with the
             ``secrets.token_hex(32)`` fallback — which would silently
             invalidate every existing session on the next deploy
             because the fallback key isn't stable across restarts.

  TGUARD_02  Any SECRET_KEY under 32 chars crashes the process so an
             operator can't accidentally deploy with a weak key.

Tested via ``importlib.reload`` against patched ``os.environ`` so the
guards run in the same Python process as pytest — coverage.py tracks
only the main process by default, so a subprocess-based test would
report the guard lines as uncovered.  Each test restores the env AND
re-reloads tokens in a ``finally`` so subsequent tests see a healthy
tokens module; can't use the ``monkeypatch`` fixture for restoration
because pytest tears down request-scoped fixtures in reverse order
and monkeypatch's restore would run AFTER mine.
"""

from __future__ import annotations

import importlib
import os

import pytest

from llm.seca.auth import tokens as tokens_module

# A known-good SECRET_KEY used to restore the module to a healthy state
# after each test.  Long enough to clear the 32-char floor.
_HEALTHY_SECRET_KEY = "ci-secret-key-that-is-32-chars-long!!"


def _set_env(secret_key: str | None, seca_env: str) -> dict[str, str | None]:
    """Apply env overrides and return the prior values for restoration.

    A ``None`` value deletes the variable.  Mirrors monkeypatch.setenv /
    delenv but stays out of pytest's fixture-teardown ordering so we
    control the restore-then-reload sequencing ourselves.
    """
    prior = {
        "SECRET_KEY": os.environ.get("SECRET_KEY"),
        "SECA_ENV": os.environ.get("SECA_ENV"),
    }
    if secret_key is None:
        os.environ.pop("SECRET_KEY", None)
    else:
        os.environ["SECRET_KEY"] = secret_key
    os.environ["SECA_ENV"] = seca_env
    return prior


def _restore_env(prior: dict[str, str | None]) -> None:
    for key, value in prior.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value


def _reload_tokens_with_healthy_env() -> None:
    """Force-reload tokens.py in a known-good env so subsequent tests
    can import it cleanly.  Called from each guard test's finally."""
    os.environ["SECRET_KEY"] = _HEALTHY_SECRET_KEY
    os.environ["SECA_ENV"] = "dev"
    importlib.reload(tokens_module)


def test_tguard_01_prod_without_secret_key_crashes_at_import():
    """TGUARD_01 — SECA_ENV=prod without SECRET_KEY must abort the
    process at import time.  The fallback ``secrets.token_hex(32)``
    used in dev mode is NOT stable across restarts, so allowing it in
    production would silently invalidate every issued JWT the next
    time the process restarts.
    """
    prior = _set_env(secret_key=None, seca_env="prod")
    try:
        with pytest.raises(RuntimeError, match="SECRET_KEY env var is required in production"):
            importlib.reload(tokens_module)
    finally:
        _restore_env(prior)
        _reload_tokens_with_healthy_env()


def test_tguard_02_short_secret_key_crashes_at_import():
    """TGUARD_02 — SECRET_KEY shorter than 32 chars must abort the
    process at import time.  The 32-char floor is the operator-facing
    guard against deploying a weak signing key by accident."""
    prior = _set_env(secret_key="x" * 31, seca_env="dev")
    try:
        with pytest.raises(RuntimeError, match="SECRET_KEY must be at least 32 characters"):
            importlib.reload(tokens_module)
    finally:
        _restore_env(prior)
        _reload_tokens_with_healthy_env()


def test_tguard_02b_exact_32_char_secret_is_accepted():
    """TGUARD_02b — the boundary check is ``< 32``, not ``<= 32``;
    a 32-character key is the minimum allowed."""
    prior = _set_env(secret_key="x" * 32, seca_env="dev")
    try:
        reloaded = importlib.reload(tokens_module)
        assert reloaded.SECRET_KEY == "x" * 32
    finally:
        _restore_env(prior)
        _reload_tokens_with_healthy_env()
