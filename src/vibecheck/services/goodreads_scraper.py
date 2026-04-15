"""Goodreads RSS scraper — user's read shelf.

User input: numeric user_id from the profile URL (goodreads.com/user/show/{id}-name).
Accepts plain id, id-name slug, or a full profile URL.
"""
from __future__ import annotations

import re

from vibecheck.services._rss_base import RSSScraperBase


class GoodreadsScraper(RSSScraperBase):
    PLATFORM = "goodreads"
    ID_RE = re.compile(r"(\d+)")

    def build_url(self, username: str) -> str:
        m = self.ID_RE.search(username)
        user_id = m.group(1) if m else username.strip()
        return f"https://www.goodreads.com/review/list_rss/{user_id}?shelf=read"

    def kind_for(self, item_body: str) -> str:
        return "book"
