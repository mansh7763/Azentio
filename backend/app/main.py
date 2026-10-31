"""FastAPI app. Shared file: change with a heads-up in chat."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import alerts, cases, dashboard, records
from app.config import settings
from app.db import init_db
from app.detect import router as detect
from app.graph import router as graph

init_db()

app = FastAPI(title="FinShield", description="Digital Fraud Investigation System", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health():
    return {"status": "ok"}


for module in (records, alerts, cases, dashboard, detect, graph):
    app.include_router(module.router, prefix="/api")
