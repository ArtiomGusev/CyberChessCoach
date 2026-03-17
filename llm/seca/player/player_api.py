from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict
import uuid

# ------------------------------------------------------------------
# In-memory store (replace with DB later)
# ------------------------------------------------------------------

PLAYER_STORE: Dict[str, dict] = {}


# ------------------------------------------------------------------
# Schemas
# ------------------------------------------------------------------


class PlayerCreateRequest(BaseModel):
    name: str
    initial_rating: int = 1200


class PlayerUpdateRequest(BaseModel):
    rating_delta: int
    tilt: float | None = None


class PlayerStateResponse(BaseModel):
    player_id: str
    name: str
    rating: int
    tilt: float


# ------------------------------------------------------------------
# Router
# ------------------------------------------------------------------

router = APIRouter(prefix="/player", tags=["player"])


# ------------------------------------------------------------------
# Create player
# ------------------------------------------------------------------


@router.post("/create", response_model=PlayerStateResponse)
def create_player(req: PlayerCreateRequest):
    player_id = str(uuid.uuid4())

    PLAYER_STORE[player_id] = {
        "name": req.name,
        "rating": req.initial_rating,
        "tilt": 0.0,
    }

    return PlayerStateResponse(
        player_id=player_id,
        name=req.name,
        rating=req.initial_rating,
        tilt=0.0,
    )


# ------------------------------------------------------------------
# Update player
# ------------------------------------------------------------------


@router.post("/update/{player_id}", response_model=PlayerStateResponse)
def update_player(player_id: str, req: PlayerUpdateRequest):
    if player_id not in PLAYER_STORE:
        raise HTTPException(status_code=404, detail="Player not found")

    player = PLAYER_STORE[player_id]

    player["rating"] += req.rating_delta

    if req.tilt is not None:
        player["tilt"] = max(0.0, min(1.0, req.tilt))

    return PlayerStateResponse(
        player_id=player_id,
        name=player["name"],
        rating=player["rating"],
        tilt=player["tilt"],
    )


# ------------------------------------------------------------------
# Get player state
# ------------------------------------------------------------------


@router.get("/state/{player_id}", response_model=PlayerStateResponse)
def get_player_state(player_id: str):
    if player_id not in PLAYER_STORE:
        raise HTTPException(status_code=404, detail="Player not found")

    player = PLAYER_STORE[player_id]

    return PlayerStateResponse(
        player_id=player_id,
        name=player["name"],
        rating=player["rating"],
        tilt=player["tilt"],
    )
