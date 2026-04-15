"""Smoke test — exercises scrapers + health endpoint without requiring LLM key.

Usage:
    make smoke         # requires server running on :8895 for HTTP part
    python smoke_test.py --scrapers-only   # only hit scrapers (no server)
"""
from __future__ import annotations

import argparse
import asyncio
import sys

import httpx
from loguru import logger

from vibecheck.core.config import settings
from vibecheck.services.bluesky_scraper import BlueskyScraper
from vibecheck.services.devto_scraper import DevtoScraper
from vibecheck.services.github_scraper import GitHubScraper
from vibecheck.services.goodreads_scraper import GoodreadsScraper
from vibecheck.services.habr_scraper import HabrScraper
from vibecheck.services.hackernews_scraper import HackerNewsScraper
from vibecheck.services.letterboxd_scraper import LetterboxdScraper
from vibecheck.services.mastodon_scraper import MastodonScraper
from vibecheck.services.pikabu_scraper import PikabuScraper
from vibecheck.services.reddit_scraper import RedditScraper
from vibecheck.services.steam_scraper import SteamScraper
from vibecheck.services.substack_scraper import SubstackScraper
from vibecheck.services.telegram_scraper import TelegramScraper


SAMPLES: dict[str, tuple[object, str]] = {
    "reddit": (RedditScraper(), "spez"),
    "github": (GitHubScraper(), "torvalds"),
    "bluesky": (BlueskyScraper(), "bsky.app"),
    "hackernews": (HackerNewsScraper(), "pg"),
    "habr": (HabrScraper(), "Boomburum"),
    "telegram": (TelegramScraper(), "durov"),
    "mastodon": (MastodonScraper(), "@Gargron@mastodon.social"),
    "devto": (DevtoScraper(), "ben"),
    "substack": (SubstackScraper(), "astralcodexten"),
    "steam": (SteamScraper(), "76561198017975643"),
    "letterboxd": (LetterboxdScraper(), "davidehrlich"),
    "goodreads": (GoodreadsScraper(), "21901974"),
    "pikabu": (PikabuScraper(), "Zergeich"),
}


async def check_scrapers() -> int:
    failures = 0
    for name, (scraper, sample) in SAMPLES.items():
        try:
            items = await asyncio.wait_for(scraper.scrape(sample), timeout=30)
            status = "OK" if items else "WARN (0 items)"
            logger.info("{:12s} {:4s} — {} items", name, status, len(items))
        except Exception as exc:
            logger.error("{:12s} FAIL — {}: {}", name, type(exc).__name__, exc)
            failures += 1
    return failures


def check_http(port: int) -> int:
    try:
        r = httpx.get(f"http://127.0.0.1:{port}/api/health", timeout=5)
        r.raise_for_status()
        logger.info("GET /api/health — {}", r.json())
        return 0
    except Exception as exc:
        logger.error("HTTP check failed: {}", exc)
        return 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scrapers-only", action="store_true")
    args = parser.parse_args()

    failures = asyncio.run(check_scrapers())
    if not args.scrapers_only:
        failures += check_http(settings.port)
    if failures:
        logger.error("smoke test FAILED ({} failure(s))", failures)
        return 1
    logger.info("smoke test PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
