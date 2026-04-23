# seca/inference/router.py

from fastapi import APIRouter
from pydantic import BaseModel

from llm.seca.inference.pipeline import explain_position

router = APIRouter()


class ExplainRequest(BaseModel):
    fen: str


@router.post("/explain")
async def explain(req: ExplainRequest):
    return await explain_position(req.fen)
