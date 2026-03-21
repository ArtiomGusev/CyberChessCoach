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
ACCESS_EXPIRE_MINUTES = 15


def create_access_token(player_id: str, session_id: str) -> str:
    payload = {
        "player_id": player_id,
        "session_id": session_id,
        "exp": datetime.utcnow() + timedelta(minutes=ACCESS_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
