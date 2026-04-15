"""FastAPI DI wiring: singletons per-process, injected via Depends()."""
from __future__ import annotations

from functools import lru_cache

from fastapi import Depends, HTTPException, Request, status

from vibecheck.core.config import Settings, settings
from vibecheck.core.rate_limit import RateLimiter
from vibecheck.services.agent import VibeAgent
from vibecheck.services.bluesky_scraper import BlueskyScraper
from vibecheck.services.devto_scraper import DevtoScraper
from vibecheck.services.github_scraper import GitHubScraper
from vibecheck.services.goodreads_scraper import GoodreadsScraper
from vibecheck.services.habr_scraper import HabrScraper
from vibecheck.services.hackernews_scraper import HackerNewsScraper
from vibecheck.services.instagram_scraper import InstagramScraper
from vibecheck.services.letterboxd_scraper import LetterboxdScraper
from vibecheck.services.mastodon_scraper import MastodonScraper
from vibecheck.services.pikabu_scraper import PikabuScraper
from vibecheck.services.profile_analyzer import ProfileAnalyzer
from vibecheck.services.reddit_scraper import RedditScraper
from vibecheck.services.steam_scraper import SteamScraper
from vibecheck.services.substack_scraper import SubstackScraper
from vibecheck.services.telegram_scraper import TelegramScraper


def get_settings() -> Settings:
    return settings


@lru_cache(maxsize=1)
def _reddit_scraper() -> RedditScraper:
    return RedditScraper()


@lru_cache(maxsize=1)
def _github_scraper() -> GitHubScraper:
    return GitHubScraper()


@lru_cache(maxsize=1)
def _instagram_scraper() -> InstagramScraper:
    return InstagramScraper()


@lru_cache(maxsize=1)
def _bluesky_scraper() -> BlueskyScraper:
    return BlueskyScraper()


@lru_cache(maxsize=1)
def _hackernews_scraper() -> HackerNewsScraper:
    return HackerNewsScraper()


@lru_cache(maxsize=1)
def _habr_scraper() -> HabrScraper:
    return HabrScraper()


@lru_cache(maxsize=1)
def _telegram_scraper() -> TelegramScraper:
    return TelegramScraper()


@lru_cache(maxsize=1)
def _mastodon_scraper() -> MastodonScraper:
    return MastodonScraper()


@lru_cache(maxsize=1)
def _devto_scraper() -> DevtoScraper:
    return DevtoScraper()


@lru_cache(maxsize=1)
def _substack_scraper() -> SubstackScraper:
    return SubstackScraper()


@lru_cache(maxsize=1)
def _steam_scraper() -> SteamScraper:
    return SteamScraper()


@lru_cache(maxsize=1)
def _letterboxd_scraper() -> LetterboxdScraper:
    return LetterboxdScraper()


@lru_cache(maxsize=1)
def _goodreads_scraper() -> GoodreadsScraper:
    return GoodreadsScraper()


@lru_cache(maxsize=1)
def _pikabu_scraper() -> PikabuScraper:
    return PikabuScraper()


@lru_cache(maxsize=1)
def _vibe_agent() -> VibeAgent:
    return VibeAgent(settings)


@lru_cache(maxsize=1)
def _rate_limiter() -> RateLimiter:
    return RateLimiter(max_per_window=5, window_s=60)


def get_profile_analyzer() -> ProfileAnalyzer:
    return ProfileAnalyzer(
        reddit=_reddit_scraper(),
        github=_github_scraper(),
        instagram=_instagram_scraper(),
        bluesky=_bluesky_scraper(),
        hackernews=_hackernews_scraper(),
        habr=_habr_scraper(),
        telegram=_telegram_scraper(),
        mastodon=_mastodon_scraper(),
        devto=_devto_scraper(),
        substack=_substack_scraper(),
        steam=_steam_scraper(),
        letterboxd=_letterboxd_scraper(),
        goodreads=_goodreads_scraper(),
        pikabu=_pikabu_scraper(),
        agent=_vibe_agent(),
    )


async def enforce_rate_limit(
    request: Request,
    limiter: RateLimiter = Depends(_rate_limiter),
) -> None:
    ip = request.client.host if request.client else "unknown"
    if not await limiter.check(ip):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Try again in a minute.",
        )
