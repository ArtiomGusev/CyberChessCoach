import os
import secrets
from datetime import datetime, timedelta

import jwt

_IS_PROD = os.getenv("SECA_ENV", "dev") in {"prod", "production"}
_raw_secret_key = os.getenv("SECRET_KEY", "")

if _IS_PROD and not _raw_secret_key:
    raise RuntimeError(
        "SECRET_KEY env var is required in production (SECA_ENV=prod). "
        "Set a stable value of at least 32 characters."
    )

SECRET_KEY = _raw_secret_key or secrets.token_hex(32)
if len(SECRET_KEY) < 32:
    raise RuntimeError("SECRET_KEY must be at least 32 characters.")
ALGORITHM = "HS256"

# JWT exp claim — match the default Session.expires_at window so the
# JWT and the server-side session run on the same clock.  Combined
# with the sliding-session window in AuthService.get_player_by_session
# (extends expires_at on each authenticated request), an active user
# only sees a re-login prompt after 7 days of *idleness*, not after
# 7 days from any single request.  See the
# `test_session_slides_on_authenticated_request` test for the
# observable behaviour.
#
# Pre-2026-04 this was 15 minutes, which bounced active users every
# 15 min because the client has no refresh path — way too aggressive
# for a chess-coaching app's threat model.
ACCESS_EXPIRE_MINUTES = 60 * 24 * 7  # 7 days


def create_access_token(player_id: str, session_id: str) -> str:
    payload = {
        "player_id": player_id,
        "session_id": session_id,
        "exp": datetime.utcnow() + timedelta(minutes=ACCESS_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
