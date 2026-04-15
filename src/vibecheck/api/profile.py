"""Profile analysis endpoint — thin controller, delegates to ProfileAnalyzer."""
from __future__ import annotations

import html
import json

from fastapi import APIRouter, Depends
from loguru import logger
from sse_starlette.sse import EventSourceResponse

from vibecheck.core.deps import enforce_rate_limit, get_profile_analyzer
from vibecheck.schemas.profile import AnalyzeRequest
from vibecheck.services.profile_analyzer import ProfileAnalyzer

router = APIRouter(tags=["profile"])


@router.post("/analyze", dependencies=[Depends(enforce_rate_limit)])
async def analyze(
    req: AnalyzeRequest,
    analyzer: ProfileAnalyzer = Depends(get_profile_analyzer),
) -> EventSourceResponse:
    """Stream analysis: scrape all platforms in parallel → LLM analysis."""

    async def events():
        yield json.dumps({"stage": "scraping", "progress": 10, "message": "Fetching public activity..."})

        profile = await analyzer.scrape(req)

        if not any([
            req.reddit_username, req.github_username, req.instagram_username,
            req.bluesky_handle, req.hackernews_username,
            req.habr_username, req.telegram_channel,
            req.mastodon_handle, req.devto_username,
            req.substack_username,
            req.steam_id, req.letterboxd_username,
            req.goodreads_user_id, req.pikabu_username,
        ]):
            yield json.dumps({"stage": "error", "progress": 0, "message": "No usernames provided"})
            return

        yield json.dumps({
            "stage": "scraped",
            "progress": 40,
            "message": f"Got {profile.total_items} items. Analyzing vibe...",
        })

        if profile.total_items == 0:
            yield json.dumps({
                "stage": "error",
                "progress": 0,
                "message": "No public data found. Check usernames or try another platform.",
            })
            return

        try:
            report = await analyzer.analyze(profile, mode=req.mode)
        except Exception as exc:
            logger.error("Analysis failed: {}", exc)
            yield json.dumps({
                "stage": "error",
                "progress": 0,
                "message": "LLM service unavailable. Try again shortly.",
            })
            return

        yield json.dumps({
            "stage": "done",
            "progress": 100,
            "message": "Analysis complete",
            "data": {
                "profile": {
                    "reddit_username": profile.reddit_username,
                    "github_username": profile.github_username,
                    "instagram_username": profile.instagram_username,
                    "bluesky_handle": profile.bluesky_handle,
                    "hackernews_username": profile.hackernews_username,
                    "habr_username": profile.habr_username,
                    "telegram_channel": profile.telegram_channel,
                    "mastodon_handle": profile.mastodon_handle,
                    "devto_username": profile.devto_username,
                    "substack_username": profile.substack_username,
                    "steam_id": profile.steam_id,
                    "letterboxd_username": profile.letterboxd_username,
                    "goodreads_user_id": profile.goodreads_user_id,
                    "pikabu_username": profile.pikabu_username,
                    "total_items": profile.total_items,
                    "errors": profile.errors,
                },
                "report": _escape_report(report.model_dump()),
            },
        })

    return EventSourceResponse(events())


def _escape_report(report: dict) -> dict:
    """html.escape all LLM-generated strings (skill-mandated)."""
    def esc(v):
        if isinstance(v, str):
            return html.escape(v, quote=False)
        if isinstance(v, list):
            return [esc(x) for x in v]
        if isinstance(v, dict):
            return {k: esc(x) for k, x in v.items()}
        return v
    return esc(report)
