import json
import os
from fastapi import APIRouter, Depends, HTTPException, Header, Request
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session, Session as DBSession
from llm.seca.shared_limiter import limiter

from .models import Base

# --- ensure ALL models are registered ---
from llm.seca.auth.models import *  # noqa: F401,F403
from llm.seca.events.models import *  # noqa: F401,F403
from llm.seca.brain.models import *  # noqa: F401,F403
from llm.seca.analytics.models import *  # noqa: F401,F403
from .service import AuthService
from .tokens import decode_token

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///data/seca.db")
_is_sqlite = DATABASE_URL.startswith("sqlite")

if _is_sqlite:
    os.makedirs("data", exist_ok=True)
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
else:
    engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(bind=engine)

Base.metadata.create_all(bind=engine)

# Add player_embedding column if missing (schema upgrade for SQLite instances
# created before this column was added to the Player model).
# On Postgres, create_all() generates the full schema, so no migration needed.
if _is_sqlite:
    with engine.connect() as conn:
        rows = conn.execute(text("PRAGMA table_info(players)")).fetchall()
        if "player_embedding" not in {r[1] for r in rows}:
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
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=401, detail="Invalid token")
    try:
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
from pydantic import BaseModel, field_validator


class RegisterRequest(BaseModel):
    email: str
    password: str

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 3 or "@" not in v or len(v) > 320:
            raise ValueError("Invalid email address")
        return v

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) > 1000:
            raise ValueError("password too long (max 1000 chars)")
        return v


class LoginRequest(BaseModel):
    email: str
    password: str
    device_info: str = ""

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) > 1000:
            raise ValueError("password too long (max 1000 chars)")
        return v

    @field_validator("device_info")
    @classmethod
    def validate_device_info(cls, v: str) -> str:
        if len(v) > 200:
            raise ValueError("device_info too long (max 200 chars)")
        return v


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str

    @field_validator("current_password", "new_password")
    @classmethod
    def validate_password_length(cls, v: str) -> str:
        if len(v) > 1000:
            raise ValueError("password too long (max 1000 chars)")
        return v


# ---------------------------
# Endpoints
# ---------------------------
@router.post("/register")
@limiter.limit("5/minute")
def register(request: Request, req: RegisterRequest, db: DBSession = Depends(get_db)):
    service = AuthService(db)
    try:
        player = service.register(req.email, req.password)
    except ValueError:
        raise HTTPException(status_code=400, detail="Registration failed")
    token, _ = service.login(req.email, req.password, device_info="register")
    return {
        "access_token": token,
        "player_id": str(player.id),
        "token_type": "bearer",
    }


@router.post("/login")
@limiter.limit("10/minute")
def login(request: Request, req: LoginRequest, db: Session = Depends(get_db)):
    service = AuthService(db)
    try:
        token, player = service.login(req.email, req.password, req.device_info)
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid credentials")
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
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    try:
        payload = decode_token(token)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    AuthService(db).logout(payload["session_id"])
    return {"status": "logged_out"}


@router.get("/me")
def me(player=Depends(get_current_player)):
    try:
        skill_vector = json.loads(player.skill_vector_json or "{}")
        skill_vector = {k: float(v) for k, v in skill_vector.items() if isinstance(v, (int, float))}
    except (ValueError, TypeError):
        skill_vector = {}
    return {
        "id": player.id,
        "email": player.email,
        "rating": player.rating,
        "confidence": player.confidence,
        "skill_vector": skill_vector,
    }


@router.post("/change-password")
@limiter.limit("5/minute")
def change_password(
    req: ChangePasswordRequest,
    request: Request,
    player=Depends(get_current_player),
    db: DBSession = Depends(get_db),
):
    service = AuthService(db)
    try:
        service.change_password(player, req.current_password, req.new_password)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"status": "updated"}
