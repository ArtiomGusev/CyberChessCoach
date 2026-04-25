"""Shared X-Api-Key verifier for the two FastAPI apps in this repo.

Both ``llm/server.py`` (the production coaching API) and
``llm/host_app.py`` (the host-side debug/inspection API) used to ship
their own copy of ``verify_api_key`` with identical logic.  Drift was
held back only by SN_01 / SN_01b AST-pinning tests in
``test_security_new_findings.py``; the implementations themselves had
to be edited in lock-step.

This module is the single source of truth.  ``server.py`` and
``host_app.py`` import the function — and the env-var resolution that
backs it — directly.

Behaviour
---------
- Dev mode (``SECA_API_KEY`` unset, ``SECA_ENV != prod``): pass-through.
  Matches the historical "no key configured = open" semantic for local
  development.
- Prod mode (``SECA_ENV in {prod, production}``) with no
  ``SECA_API_KEY``: HTTP 500 at request time.  ``server.py`` additionally
  hard-fails at module import via its own ``if IS_PROD and API_KEY is
  None: raise RuntimeError`` block, so a misconfigured production
  deployment never even starts; this request-time 500 is a defensive
  belt-and-braces in case that startup guard is ever bypassed.
- Configured key: constant-time comparison via ``hmac.compare_digest``.
  Mismatched keys yield HTTP 401.

The ``hmac.compare_digest`` choice (vs ``==``) is enforced by the SN_01
test in ``test_security_new_findings.py`` — replacing it would
reintroduce a one-character-at-a-time timing oracle on the API key.
"""

from __future__ import annotations

import hmac
import os

from fastapi import Header, HTTPException


_API_KEY = os.getenv("SECA_API_KEY")
_IS_PROD = os.getenv("SECA_ENV", "dev") in {"prod", "production"}


def verify_api_key(x_api_key: str = Header(None)) -> None:
    """FastAPI dependency: validate the X-Api-Key header in constant time."""
    if _API_KEY is None:
        if _IS_PROD:
            raise HTTPException(status_code=500, detail="Server misconfiguration")
        return  # dev mode — unauthenticated access permitted
    if not hmac.compare_digest(x_api_key or "", _API_KEY):
        raise HTTPException(status_code=401, detail="Unauthorized")
