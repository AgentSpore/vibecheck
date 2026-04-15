from fastapi import APIRouter
from vibecheck.core.config import settings

router = APIRouter(tags=["health"])


@router.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "vibecheck",
        "model": settings.agent_model,
        "api_key_configured": bool(settings.openrouter_api_key),
    }
