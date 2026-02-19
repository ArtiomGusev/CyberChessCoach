# seca/inference/router.py

from fastapi import APIRouter
from llm.seca.inference.pipeline import explain_position

router = APIRouter()

@router.post("/explain")
async def explain(req: dict):
    return await explain_position(req)
