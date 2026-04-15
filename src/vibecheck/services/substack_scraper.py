"""Substack newsletter RSS scraper.

User input: subdomain (e.g. "platformer" for platformer.substack.com) OR
full domain (e.g. "read.noahpinion.com" for custom domains).
"""
from __future__ import annotations

from vibecheck.services._rss_base import RSSScraperBase


class SubstackScraper(RSSScraperBase):
    PLATFORM = "substack"

    def build_url(self, username: str) -> str:
        username = username.strip().lower()
        if "." in username:
            return f"https://{username}/feed"
        return f"https://{username}.substack.com/feed"
