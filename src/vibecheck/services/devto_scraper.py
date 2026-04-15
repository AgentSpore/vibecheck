"""Dev.to public user RSS scraper."""
from __future__ import annotations

from vibecheck.services._rss_base import RSSScraperBase


class DevtoScraper(RSSScraperBase):
    PLATFORM = "devto"

    def build_url(self, username: str) -> str:
        return f"https://dev.to/feed/{username}"
