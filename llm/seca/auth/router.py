from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session, Session as DBSession

from .models import Base

# --- ensure ALL models are registered ---
from llm.seca.auth.models import *  # noqa: F401,F403
from llm.seca.events.models import *  # noqa: F401,F403
from llm.seca.brain.models import *  # noqa: F401,F403
from llm.seca.analytics.models import *  # noqa: F401,F403
from .service import AuthService
from .tokens import decode_token

DATABASE_URL = "sqlite:///data/seca.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine)

Base.metadata.create_all(bind=engine)
with engine.connect() as conn:
    rows = conn.execute(
        text("PRAGMA table_info(players)")
    ).fetchall()
    columns = {r[1] for r in rows}
    if "player_embedding" not in columns:
        conn.execute(
            text("ALTER TABLE players ADD COLUMN player_embedding TEXT DEFAULT '[]'")
        )
        conn.commit()

router = APIRouter(prefix="/auth", tags=["auth"])


# ---------------------------
# Dependency
# ---------------------------
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_player(
    authorization: str = Header(...),
    db: DBSession = Depends(get_db),
):
    try:
        token = authorization.replace("Bearer ", "")
        payload = decode_token(token)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")

    service = AuthService(db)
    player = service.get_player_by_session(payload["session_id"], token)

    if not player:
        raise HTTPException(status_code=401, detail="Session invalid")

    return player


# ---------------------------
# Schemas
# ---------------------------
from pydantic import BaseModel


class RegisterRequest(BaseModel):
    email: str
    password: str


class LoginRequest(BaseModel):
    email: str
    password: str
    device_info: str = ""


# ---------------------------
# Endpoints
# ---------------------------
@router.post("/register")
def register(req: RegisterRequest, db: DBSession = Depends(get_db)):
    service = AuthService(db)
    player = service.register(req.email, req.password)
    return {"player_id": player.id}


@router.post("/login")
def login(req: LoginRequest, db: Session = Depends(get_db)):
    service = AuthService(db)
    try:
        token, player = service.login(req.email, req.password, req.device_info)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))
    return {
        "access_token": token,
        "player_id": str(player.id),
        "token_type": "bearer",
    }


@router.post("/logout")
def logout(
    authorization: str = Header(...),
    db: DBSession = Depends(get_db),
):
    token = authorization.replace("Bearer ", "")
    payload = decode_token(token)

    AuthService(db).logout(payload["session_id"])
    return {"status": "logged_out"}


@router.get("/me")
def me(player=Depends(get_current_player)):
    return {
        "id": player.id,
        "email": player.email,
        "rating": player.rating,
        "confidence": player.confidence,
    }
