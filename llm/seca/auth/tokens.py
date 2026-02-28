import os
import secrets
from datetime import datetime, timedelta

import jwt

SECRET_KEY = os.getenv("SECRET_KEY", secrets.token_hex(32))
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
