"""Orchestrator: parallel scrape all platforms → LLM analysis."""
from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator

from loguru import logger

from vibecheck.schemas.profile import (
    AnalysisMode,
    AnalyzeRequest,
    ScrapedProfile,
    VibeReport,
)
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
from vibecheck.services.reddit_scraper import RedditScraper
from vibecheck.services.steam_scraper import SteamScraper
from vibecheck.services.substack_scraper import SubstackScraper
from vibecheck.services.telegram_scraper import TelegramScraper


class ProfileAnalyzer:
    """Scrape in parallel, then run VibeAgent."""

    def __init__(
        self,
        reddit: RedditScraper,
        github: GitHubScraper,
        instagram: InstagramScraper,
        bluesky: BlueskyScraper,
        hackernews: HackerNewsScraper,
        habr: HabrScraper,
        telegram: TelegramScraper,
        mastodon: MastodonScraper,
        devto: DevtoScraper,
        substack: SubstackScraper,
        steam: SteamScraper,
        letterboxd: LetterboxdScraper,
        goodreads: GoodreadsScraper,
        pikabu: PikabuScraper,
        agent: VibeAgent,
    ) -> None:
        self.reddit = reddit
        self.github = github
        self.instagram = instagram
        self.bluesky = bluesky
        self.hackernews = hackernews
        self.habr = habr
        self.telegram = telegram
        self.mastodon = mastodon
        self.devto = devto
        self.substack = substack
        self.steam = steam
        self.letterboxd = letterboxd
        self.goodreads = goodreads
        self.pikabu = pikabu
        self.agent = agent

    async def scrape(self, req: AnalyzeRequest) -> ScrapedProfile:
        tasks: list[tuple[str, asyncio.Future]] = []
        if req.reddit_username:
            tasks.append(("reddit", self.reddit.scrape(req.reddit_username)))
        if req.github_username:
            tasks.append(("github", self.github.scrape(req.github_username)))
        if req.instagram_username:
            tasks.append(
                ("instagram", self.instagram.scrape(req.instagram_username, ig_session=req.ig_session))
            )
        if req.bluesky_handle:
            tasks.append(("bluesky", self.bluesky.scrape(req.bluesky_handle)))
        if req.hackernews_username:
            tasks.append(("hackernews", self.hackernews.scrape(req.hackernews_username)))
        if req.habr_username:
            tasks.append(("habr", self.habr.scrape(req.habr_username)))
        if req.telegram_channel:
            tasks.append(("telegram", self.telegram.scrape(req.telegram_channel)))
        if req.mastodon_handle:
            tasks.append(("mastodon", self.mastodon.scrape(req.mastodon_handle)))
        if req.devto_username:
            tasks.append(("devto", self.devto.scrape(req.devto_username)))
        if req.substack_username:
            tasks.append(("substack", self.substack.scrape(req.substack_username)))
        if req.steam_id:
            tasks.append(("steam", self.steam.scrape(req.steam_id)))
        if req.letterboxd_username:
            tasks.append(("letterboxd", self.letterboxd.scrape(req.letterboxd_username)))
        if req.goodreads_user_id:
            tasks.append(("goodreads", self.goodreads.scrape(req.goodreads_user_id)))
        if req.pikabu_username:
            tasks.append(("pikabu", self.pikabu.scrape(req.pikabu_username)))

        profile = ScrapedProfile(
            reddit_username=req.reddit_username,
            github_username=req.github_username,
            instagram_username=req.instagram_username,
            bluesky_handle=req.bluesky_handle,
            hackernews_username=req.hackernews_username,
            habr_username=req.habr_username,
            telegram_channel=req.telegram_channel,
            mastodon_handle=req.mastodon_handle,
            devto_username=req.devto_username,
            substack_username=req.substack_username,
            steam_id=req.steam_id,
            letterboxd_username=req.letterboxd_username,
            goodreads_user_id=req.goodreads_user_id,
            pikabu_username=req.pikabu_username,
        )
        if not tasks:
            return profile

        results = await asyncio.gather(*(t[1] for t in tasks), return_exceptions=True)
        for (platform, _), result in zip(tasks, results, strict=True):
            if isinstance(result, Exception):
                profile.errors.append(f"{platform}: {type(result).__name__}")
                logger.warning("Scraper {} failed: {}", platform, result)
            else:
                profile.posts.extend(result)
        return profile

    async def analyze(self, profile: ScrapedProfile, mode: AnalysisMode) -> VibeReport:
        return await self.agent.analyze(profile, mode)


def items_by_platform(profile: ScrapedProfile) -> dict[str, int]:
    """Count posts per platform for the breakdown plaque in UI."""
    counts: dict[str, int] = {}
    for post in profile.posts:
        counts[post.platform] = counts.get(post.platform, 0) + 1
    return counts
