"""Base class for RSS-backed scrapers. Shared regex + HTTP fetch."""
from __future__ import annotations

import html
import re

import httpx
from loguru import logger

from vibecheck.schemas.profile import SocialPost


class RSSScraperBase:
    """Parent for Mastodon/DevTo/Substack/Letterboxd/Goodreads scrapers.

    Subclass must set: PLATFORM, UA (optional). Override build_url() and
    optionally kind_for(item).
    """

    PLATFORM: str = ""
    UA: dict[str, str] = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5_0) AppleWebKit/605.1.15 "
            "(KHTML, like Gecko) Version/17.5 Safari/605.1.15"
        )
    }
    TIMEOUT_S = 15.0
    MAX_ITEMS = 20

    ITEM_RE = re.compile(r"<item>(.+?)</item>", re.DOTALL | re.IGNORECASE)
    ENTRY_RE = re.compile(r"<entry>(.+?)</entry>", re.DOTALL | re.IGNORECASE)
    TITLE_RE = re.compile(
        r"<title[^>]*>(?:<!\[CDATA\[)?(.+?)(?:\]\]>)?</title>", re.DOTALL | re.IGNORECASE
    )
    DESC_RE = re.compile(
        r"<description>(?:<!\[CDATA\[)?(.+?)(?:\]\]>)?</description>", re.DOTALL | re.IGNORECASE
    )
    CONTENT_RE = re.compile(
        r"<content[^>]*>(?:<!\[CDATA\[)?(.+?)(?:\]\]>)?</content>", re.DOTALL | re.IGNORECASE
    )
    SUMMARY_RE = re.compile(
        r"<summary[^>]*>(?:<!\[CDATA\[)?(.+?)(?:\]\]>)?</summary>", re.DOTALL | re.IGNORECASE
    )
    HTML_TAG_RE = re.compile(r"<[^>]+>")

    def build_url(self, username: str) -> str:
        raise NotImplementedError

    def kind_for(self, item_body: str) -> str:
        return "post"

    def context_for(self, item_body: str, username: str) -> str:
        return username

    @classmethod
    def clean(cls, text: str) -> str:
        text = html.unescape(text or "")
        text = cls.HTML_TAG_RE.sub(" ", text)
        return re.sub(r"\s+", " ", text).strip()

    async def scrape(self, username: str) -> list[SocialPost]:
        username = username.strip().lstrip("@")
        if not username:
            return []
        url = self.build_url(username)
        try:
            async with httpx.AsyncClient(
                timeout=self.TIMEOUT_S, headers=self.UA, follow_redirects=True,
            ) as client:
                resp = await client.get(url)
                if resp.status_code != 200:
                    logger.warning("{} {} for {} ({})", self.PLATFORM, resp.status_code, username, url)
                    return []
                items = self._parse_feed(resp.text, username)
                logger.info("{}: {} items for {}", self.PLATFORM, len(items), username)
                return items
        except Exception as exc:
            logger.warning("{} fetch failed for {}: {}", self.PLATFORM, username, exc)
            return []

    def _parse_feed(self, body: str, username: str) -> list[SocialPost]:
        out: list[SocialPost] = []
        raw_items = self.ITEM_RE.findall(body) or self.ENTRY_RE.findall(body)
        for raw in raw_items[:self.MAX_ITEMS]:
            title = self._extract(self.TITLE_RE, raw)
            body_txt = (
                self._extract(self.CONTENT_RE, raw)
                or self._extract(self.DESC_RE, raw)
                or self._extract(self.SUMMARY_RE, raw)
            )
            body_txt = self.clean(body_txt)[:500]
            text = f"{title}\n{body_txt}".strip() if title and body_txt else (title or body_txt)
            if not text:
                continue
            out.append(SocialPost(
                platform=self.PLATFORM,
                kind=self.kind_for(raw),
                context=self.context_for(raw, username),
                text=text[:500],
            ))
        return out

    @staticmethod
    def _extract(pattern: re.Pattern, text: str) -> str:
        m = pattern.search(text)
        return m.group(1).strip() if m else ""
