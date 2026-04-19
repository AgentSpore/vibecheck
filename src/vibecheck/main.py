"""VibeCheck FastAPI app."""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger

from vibecheck.api import health, profile

STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(
    title="VibeCheck",
    description="Vibe analysis from public social profiles",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api")
app.include_router(profile.router, prefix="/api")


@app.get("/")
async def index():
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return {"error": "static/index.html missing"}


@app.get("/s/{share_id}")
async def share_page(share_id: str):  # noqa: ARG001 — share_id consumed client-side via /api/share
    share_file = STATIC_DIR / "share.html"
    if share_file.exists():
        return FileResponse(share_file)
    return {"error": "static/share.html missing"}


if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

logger.info("VibeCheck ready")
