from fastapi import APIRouter
from vibecheck.core.config import settings

router = APIRouter(tags=["health"])


@router.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "vibecheck",
        "version": "0.1.5-enhancements",
        "model": settings.agent_model,
        "fallback_models": settings.fallback_models,
        "api_key_configured": bool(settings.openrouter_api_key),
        "ig_proxy_configured": bool(settings.ig_proxy_url),
        "steam_api_key_configured": bool(settings.steam_api_key),
    }
