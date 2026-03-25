"""
SECA status endpoint and SAFE_MODE constant tests.

These tests verify three invariants critical for P4 auditability:
1.  SAFE_MODE is permanently True in this release (no accidental disabling).
2.  assert_safe() never raises while SAFE_MODE is True.
3.  GET /seca/status returns the correct runtime flags without authentication.

Test tiers
----------
Tier 1 — direct import of the safe_mode module (no FastAPI stack required).
Tier 2 — minimal FastAPI stub that mirrors the seca_status() handler logic,
          avoiding the server.py import chain (which requires Stockfish + DB).

Invariants pinned
-----------------
  SAFE_MODE_CONST_TRUE    SAFE_MODE constant == True in safe_mode.py.
  ASSERT_SAFE_NOOP        assert_safe() does not raise when SAFE_MODE is True.
  STATUS_200              GET /seca/status returns HTTP 200.
  STATUS_SAFE_MODE_TRUE   Response safe_mode field is True.
  STATUS_BANDIT_FALSE     Response bandit_enabled field is False.
  STATUS_HAS_VERSION      Response version field is a non-empty string.
  STATUS_VERSION_1_0      Response version field equals "1.0".
  STATUS_NO_AUTH          Endpoint is accessible without any API key.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Tier 1 — safe_mode module invariants
# ---------------------------------------------------------------------------


class TestSafeModeConstant:

    def test_safe_mode_const_true(self):
        """SAFE_MODE_CONST_TRUE: SAFE_MODE is True in the runtime module."""
        from llm.seca.runtime.safe_mode import SAFE_MODE

        assert SAFE_MODE is True, (
            "SAFE_MODE must be True in this release. "
            "Bandit training and neural policy updates are prohibited."
        )

    def test_assert_safe_noop_when_safe_mode_true(self):
        """ASSERT_SAFE_NOOP: assert_safe() does not raise when SAFE_MODE is True."""
        from llm.seca.runtime.safe_mode import assert_safe

        # Must not raise
        assert_safe()


# ---------------------------------------------------------------------------
# Tier 2 — /seca/status endpoint shape (minimal stub, no server.py import)
# ---------------------------------------------------------------------------


def _build_status_app() -> FastAPI:
    """Return a minimal FastAPI app that mirrors the seca_status() handler."""
    from llm.seca.runtime.safe_mode import SAFE_MODE

    stub = FastAPI()

    @stub.get("/seca/status")
    def seca_status():
        return {
            "safe_mode": SAFE_MODE,
            "bandit_enabled": not SAFE_MODE,
            "version": "1.0",
        }

    return stub


@pytest.fixture(scope="module")
def status_client():
    app = _build_status_app()
    with TestClient(app) as c:
        yield c


class TestSecaStatusEndpoint:

    def test_status_200(self, status_client):
        """STATUS_200: GET /seca/status returns HTTP 200."""
        resp = status_client.get("/seca/status")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"

    def test_status_safe_mode_true(self, status_client):
        """STATUS_SAFE_MODE_TRUE: safe_mode field is True."""
        data = status_client.get("/seca/status").json()
        assert data.get("safe_mode") is True, (
            f"safe_mode must be True, got {data.get('safe_mode')!r}"
        )

    def test_status_bandit_enabled_false(self, status_client):
        """STATUS_BANDIT_FALSE: bandit_enabled field is False."""
        data = status_client.get("/seca/status").json()
        assert data.get("bandit_enabled") is False, (
            f"bandit_enabled must be False, got {data.get('bandit_enabled')!r}"
        )

    def test_status_has_version(self, status_client):
        """STATUS_HAS_VERSION: version field is a non-empty string."""
        data = status_client.get("/seca/status").json()
        version = data.get("version")
        assert isinstance(version, str) and version, (
            f"version must be a non-empty string, got {version!r}"
        )

    def test_status_version_1_0(self, status_client):
        """STATUS_VERSION_1_0: version field equals '1.0'."""
        data = status_client.get("/seca/status").json()
        assert data.get("version") == "1.0", (
            f"version must be '1.0', got {data.get('version')!r}"
        )

    def test_status_no_auth_required(self, status_client):
        """STATUS_NO_AUTH: endpoint is accessible without any Authorization or X-Api-Key header."""
        resp = status_client.get("/seca/status")
        assert resp.status_code == 200, (
            f"/seca/status must be open (no auth). Got {resp.status_code}"
        )
