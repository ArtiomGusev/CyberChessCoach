import jwt
from datetime import datetime, timedelta

SECRET_KEY = "a68eb6934bcd7d50420706f08ba0ca5f4959211f28dfe98a70f05e298483c528"
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
