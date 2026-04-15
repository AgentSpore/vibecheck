"""Mastodon public RSS scraper — any instance.

Handle format: `@user@instance.social` or `user@instance.social`.
RSS endpoint: https://{instance}/@{user}.rss (works on all standard Mastodon).
"""
from __future__ import annotations

from loguru import logger

from vibecheck.schemas.profile import SocialPost
from vibecheck.services._rss_base import RSSScraperBase


class MastodonScraper(RSSScraperBase):
    PLATFORM = "mastodon"

    def build_url(self, username: str) -> str:
        user, instance = self._parse_handle(username)
        if not (user and instance):
            raise ValueError("invalid Mastodon handle (expected user@instance)")
        return f"https://{instance}/@{user}.rss"

    async def scrape(self, username: str) -> list[SocialPost]:
        try:
            return await super().scrape(username)
        except ValueError as exc:
            logger.warning("Mastodon: {}", exc)
            return []

    @staticmethod
    def _parse_handle(handle: str) -> tuple[str, str]:
        handle = handle.strip().lstrip("@")
        if "@" not in handle:
            return "", ""
        parts = handle.split("@", 1)
        if len(parts) != 2:
            return "", ""
        return parts[0].strip(), parts[1].strip()
