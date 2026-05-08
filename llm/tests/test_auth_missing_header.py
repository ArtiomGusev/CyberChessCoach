"""
Regression test for the missing-Authorization-header / 422-vs-401
contract bug that left fresh-install / post-logout Android clients
stuck at "Coach is offline".

Background
----------
``router.get_current_player`` (and ``router.logout``) used to declare
``authorization: str = Header(...)``.  When the Android client made
a request without the ``Authorization`` header — fresh install, just
after logout, just after a failed token rotation — FastAPI/Pydantic
flagged the missing header as a *body validation* error and returned
HTTP 422 with a Pydantic-shaped detail envelope::

    {"detail":[{"type":"missing","loc":["header","authorization"],
                "msg":"Field required","input":null}]}

The Android chat sheet (``ChatBottomSheet.kt``) only special-cases
401 to bounce the user to the login screen; a 422 is treated as a
generic transport error and the user sees "Coach is offline"
indefinitely.

Production repro::

    curl -X POST https://cereveon.com/chat/stream \\
         -H 'Content-Type: application/json' \\
         -d '{"fen":"...","messages":[...]}'
    HTTP/1.1 422 Unprocessable Entity

Fix
---
Both call sites now declare ``authorization: str | None = Header(None)``
and raise ``HTTPException(status_code=401, detail="Missing token")``
in the function body when ``authorization`` is falsy.  Pydantic no
longer rejects the missing header pre-body, so the 401 contract
applies uniformly: missing, malformed, expired, or revoked tokens
all return 401, and the Android client's existing 401 handler routes
the user to the login screen.

The downstream malformed-Authorization branch (``Basic xxx``,
``Bearer`` with no token) keeps its existing ``Invalid token`` /
``Invalid or expired token`` 401s — those tests live elsewhere.

Pinned invariants
-----------------
 - AUTH_HDR_01: POST /chat/stream with no Authorization header → 401
   (not 422), and the response body is the clean
   ``{"detail": "Missing token"}`` shape, not a Pydantic
   ``{"loc": ["header", "authorization"]}`` envelope.
 - AUTH_HDR_02: POST /auth/logout with no Authorization header → 401
   (same shape).
"""

from __future__ import annotations

import os

# Auth env must be set before llm.server / auth modules import — same
# pattern as the rest of the auth test suite.
os.environ.setdefault("SECA_API_KEY", "ci-test-key")
os.environ.setdefault("SECA_ENV", "dev")
os.environ.setdefault("SECRET_KEY", "ci-secret-key-that-is-32-chars-long!!")

from fastapi.testclient import TestClient

from llm.server import app


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _client() -> TestClient:
    """TestClient wired to the real FastAPI app.

    ``raise_server_exceptions=False`` so a downstream coaching-pipeline
    failure (which can't run anyway when auth fires first) doesn't
    bubble into the test as a Python exception — the assertion is
    purely on the auth-layer status code and the response body.
    """
    return TestClient(app, raise_server_exceptions=False)


def _is_pydantic_missing_header_envelope(detail: object) -> bool:
    """Detect the shape FastAPI/Pydantic uses for a missing required
    header.  When ``Header(...)`` rejects an absent header, the
    response body looks like::

        {"detail": [{"type": "missing",
                     "loc": ["header", "authorization"],
                     "msg": "Field required",
                     "input": null}]}

    We must NOT see this shape — its presence means the dependency
    declaration drifted back to ``Header(...)`` and the 401 contract
    has regressed.
    """
    if not isinstance(detail, list):
        return False
    for entry in detail:
        if not isinstance(entry, dict):
            continue
        loc = entry.get("loc")
        if isinstance(loc, list) and len(loc) >= 2:
            # Case-insensitive match on the header name; Pydantic v2
            # lowercases header field names in the loc tuple.
            if loc[0] == "header" and str(loc[1]).lower() == "authorization":
                return True
    return False


# A valid /chat/stream body — minimal but schema-compliant.  The
# missing-header check fires before ChatRequest validation runs at the
# auth-dependency layer, so an empty messages list is fine; the test
# never reaches the pipeline.  We still send a syntactically valid
# JSON document so a body-parse failure can't mask the auth-layer
# behaviour we're pinning.
_CHAT_STREAM_BODY = {
    "fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
    "messages": [{"role": "user", "content": "hi"}],
}


# ---------------------------------------------------------------------------
# AUTH_HDR_01 — /chat/stream
# ---------------------------------------------------------------------------


def test_missing_authorization_returns_401_not_422():
    """AUTH_HDR_01.

    POST /chat/stream without an Authorization header must return
    HTTP 401 with the clean ``{"detail": "Missing token"}`` body
    shape.  A 422 with a Pydantic ``{"loc": ["header", "authorization"]}``
    envelope means the ``Header(...)`` declaration regressed and the
    Android client's 401-handler will not fire — leaving fresh-install
    users stuck at "Coach is offline".
    """
    client = _client()
    response = client.post("/chat/stream", json=_CHAT_STREAM_BODY)

    assert response.status_code == 401, (
        "POST /chat/stream without Authorization must be 401 (the "
        "Android client's 'route to login' branch).  Got "
        f"{response.status_code} with body: {response.text!r}.  "
        "If this is 422, the Header(...) declaration regressed in "
        "router.get_current_player."
    )

    body = response.json()
    detail = body.get("detail")
    assert not _is_pydantic_missing_header_envelope(detail), (
        "Response body matches the Pydantic missing-header envelope "
        f"({{'loc': ['header', 'authorization']}}); got: {body!r}.  "
        "The contract is the clean string detail 'Missing token' so "
        "the Android client doesn't have to parse a Pydantic shape."
    )
    assert detail == "Missing token", (
        f"Expected detail == 'Missing token', got: {detail!r}.  "
        "If this drifted, update both the test and "
        "ChatBottomSheet.kt's expected error string together."
    )


# ---------------------------------------------------------------------------
# AUTH_HDR_02 — /auth/logout
# ---------------------------------------------------------------------------


def test_missing_authorization_on_logout_returns_401():
    """AUTH_HDR_02.

    POST /auth/logout without an Authorization header must return
    HTTP 401, mirroring AUTH_HDR_01 — the same Header(None) +
    early-401 pattern is required at every entry-point that takes
    the Authorization header directly (not via Depends).
    """
    client = _client()
    response = client.post("/auth/logout")

    assert response.status_code == 401, (
        "POST /auth/logout without Authorization must be 401.  Got "
        f"{response.status_code} with body: {response.text!r}.  "
        "If this is 422, the Header(...) declaration regressed in "
        "router.logout."
    )

    body = response.json()
    detail = body.get("detail")
    assert not _is_pydantic_missing_header_envelope(detail), (
        "Response body matches the Pydantic missing-header envelope; "
        f"got: {body!r}.  Logout must return the same clean string "
        "detail as get_current_player so a generic 401-handler in the "
        "client works for both."
    )
    assert detail == "Missing token", (
        f"Expected detail == 'Missing token', got: {detail!r}."
    )
