# seca/api/main.py

from fastapi import FastAPI
from llm.seca.inference.router import router as inference_router

app = FastAPI()
app.include_router(inference_router)
