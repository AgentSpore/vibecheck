"""Habr user profile scraper via public RSS feed.

RSS endpoints (work without auth):
- /ru/users/{user}/posts/rss/ — posts
- /ru/users/{user}/comments/rss/ — comments

Cyrillic-heavy tech signal, strong Russian vibe marker.
"""
from __future__ import annotations

import html
import re

import httpx
from loguru import logger

from vibecheck.schemas.profile import SocialPost


class HabrScraper:
    """Scrape Habr user's posts + comments via RSS."""

    BASE = "https://habr.com/ru/rss/users"
    UA = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5_0) AppleWebKit/605.1.15 "
            "(KHTML, like Gecko) Version/17.5 Safari/605.1.15"
        )
    }
    TIMEOUT_S = 15.0
    MAX_ITEMS = 20
    ITEM_RE = re.compile(r"<item>(.+?)</item>", re.DOTALL)
    TITLE_RE = re.compile(r"<title>(?:<!\[CDATA\[)?(.+?)(?:\]\]>)?</title>", re.DOTALL)
    DESC_RE = re.compile(r"<description>(?:<!\[CDATA\[)?(.+?)(?:\]\]>)?</description>", re.DOTALL)
    CATEGORY_RE = re.compile(r"<category>(?:<!\[CDATA\[)?(.+?)(?:\]\]>)?</category>", re.DOTALL)
    HTML_TAG_RE = re.compile(r"<[^>]+>")

    async def scrape(self, username: str) -> list[SocialPost]:
        username = username.lstrip("@").strip()
        if not username:
            return []

        posts: list[SocialPost] = []
        async with httpx.AsyncClient(timeout=self.TIMEOUT_S, headers=self.UA, follow_redirects=True) as client:
            posts.extend(await self._fetch_rss(client, username, "posts", "post"))
            posts.extend(await self._fetch_rss(client, username, "comments", "comment"))

        logger.info("Habr: {} items for {}", len(posts), username)
        return posts

    @classmethod
    def _clean(cls, text: str) -> str:
        text = html.unescape(text or "")
        text = cls.HTML_TAG_RE.sub(" ", text)
        return re.sub(r"\s+", " ", text).strip()

    async def _fetch_rss(
        self,
        client: httpx.AsyncClient,
        username: str,
        feed: str,
        kind: str,
    ) -> list[SocialPost]:
        url = f"{self.BASE}/{username}/{feed}/"
        try:
            resp = await client.get(url)
            if resp.status_code != 200:
                return []
            out: list[SocialPost] = []
            for item in self.ITEM_RE.findall(resp.text)[:self.MAX_ITEMS]:
                title = self._extract(self.TITLE_RE, item)
                desc = self._clean(self._extract(self.DESC_RE, item))
                cats = self.CATEGORY_RE.findall(item)
                cat_txt = ", ".join(self._clean(c) for c in cats[:3])
                text = f"{title}\n{desc}".strip() if kind == "post" else desc
                if not text:
                    continue
                out.append(SocialPost(
                    platform="habr",
                    kind=kind,
                    context=cat_txt or username,
                    text=text[:500],
                ))
            return out
        except Exception as exc:
            logger.warning("Habr {} failed for {}: {}", feed, username, exc)
            return []

    @staticmethod
    def _extract(pattern: re.Pattern, text: str) -> str:
        match = pattern.search(text)
        return match.group(1).strip() if match else ""
