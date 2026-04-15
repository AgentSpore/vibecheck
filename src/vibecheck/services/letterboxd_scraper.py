"""Letterboxd RSS scraper — recent film diary.

User input: letterboxd handle (e.g. "davidehrlich" from letterboxd.com/davidehrlich).
"""
from __future__ import annotations

from vibecheck.services._rss_base import RSSScraperBase


class LetterboxdScraper(RSSScraperBase):
    PLATFORM = "letterboxd"

    def build_url(self, username: str) -> str:
        return f"https://letterboxd.com/{username.strip().lower()}/rss/"

    def kind_for(self, item_body: str) -> str:
        return "film"
