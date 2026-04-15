"""Reddit public activity via RSS (JSON endpoints return 403 without auth)."""
from __future__ import annotations

import asyncio
import html
import random
import re

import httpx
from loguru import logger

from vibecheck.schemas.profile import SocialPost


class RedditScraper:
    """Scrape public Reddit profile activity via old.reddit.com RSS."""

    UA = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5_0) AppleWebKit/605.1.15 "
            "(KHTML, like Gecko) Version/17.5 Safari/605.1.15"
        )
    }
    ENTRY_RE = re.compile(r"<entry>(.+?)</entry>", re.DOTALL)
    CATEGORY_RE = re.compile(r'<category[^>]+label="([^"]+)"')
    TITLE_RE = re.compile(r"<title>([^<]+)</title>")
    CONTENT_RE = re.compile(r'<content[^>]*>(.+?)</content>', re.DOTALL)
    HTML_TAG_RE = re.compile(r"<[^>]+>")
    MAX_RETRIES = 3
    TIMEOUT_S = 15.0

    @classmethod
    def _clean(cls, text: str) -> str:
        text = html.unescape(text)
        text = cls.HTML_TAG_RE.sub(" ", text)
        return re.sub(r"\s+", " ", text).strip()

    async def scrape(self, username: str, limit: int = 25) -> list[SocialPost]:
        username = username.lstrip("u/").lstrip("/").strip()
        if not username:
            return []

        url = f"https://old.reddit.com/user/{username}/.rss?limit={limit}"
        posts: list[SocialPost] = []

        async with httpx.AsyncClient(timeout=self.TIMEOUT_S, headers=self.UA) as client:
            resp = await self._fetch_with_retry(client, url, username)
            if resp is None or resp.status_code != 200:
                return posts

            posts.extend(self._parse_entries(resp.text, username))
            logger.info("Reddit: {} items for u/{}", len(posts), username)

        return posts

    async def _fetch_with_retry(
        self, client: httpx.AsyncClient, url: str, username: str
    ) -> httpx.Response | None:
        for attempt in range(self.MAX_RETRIES):
            try:
                resp = await client.get(url)
                if resp.status_code == 200:
                    return resp
                if resp.status_code in (429, 403):
                    wait = 2 + random.random() * 3
                    logger.info("Reddit {} for u/{}, retry {} after {:.1f}s",
                                resp.status_code, username, attempt + 1, wait)
                    await asyncio.sleep(wait)
                    continue
                logger.warning("Reddit RSS {} for u/{}", resp.status_code, username)
                return resp
            except Exception as exc:
                logger.warning("Reddit attempt {} failed: {}", attempt + 1, exc)
                await asyncio.sleep(1 + random.random())
        logger.warning("Reddit RSS retries exhausted for u/{}", username)
        return None

    def _parse_entries(self, body: str, username: str) -> list[SocialPost]:
        posts: list[SocialPost] = []
        for entry in self.ENTRY_RE.findall(body):
            cat = self.CATEGORY_RE.search(entry)
            title = self.TITLE_RE.search(entry)
            content = self.CONTENT_RE.search(entry)

            subreddit = cat.group(1) if cat else "?"
            if subreddit.startswith("r/"):
                subreddit = subreddit[2:]
            title_txt = title.group(1) if title else ""
            content_txt = self._clean(content.group(1) if content else "")[:500]

            is_comment = title_txt.startswith(f"/u/{username}")
            kind = "comment" if is_comment else "post"
            text = content_txt if is_comment else f"{self._clean(title_txt)}\n{content_txt}".strip()

            posts.append(SocialPost(
                platform="reddit",
                kind=kind,
                context=f"r/{subreddit}",
                text=text[:500],
            ))
        return posts
