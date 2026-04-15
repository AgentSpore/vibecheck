"""Telegram public channel scraper via t.me/s/{channel} HTML preview.

No auth, no API key. Returns last ~20 posts + channel meta (bio, subs).
Works only for PUBLIC channels. Private channels / user DMs not accessible.
"""
from __future__ import annotations

import html
import re

import httpx
from loguru import logger

from vibecheck.schemas.profile import SocialPost


class TelegramScraper:
    """Scrape public Telegram channel recent posts + bio via t.me preview."""

    BASE = "https://t.me"
    UA = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5_0) AppleWebKit/605.1.15 "
            "(KHTML, like Gecko) Version/17.5 Safari/605.1.15"
        )
    }
    TIMEOUT_S = 15.0
    MAX_POSTS = 20

    # Post block: div with class tgme_widget_message_text — content
    POST_TEXT_RE = re.compile(
        r'<div class="tgme_widget_message_text[^"]*"[^>]*>(.*?)</div>',
        re.DOTALL,
    )
    VIEWS_RE = re.compile(
        r'<span class="tgme_widget_message_views">([^<]+)</span>'
    )
    # Channel meta
    TITLE_RE = re.compile(
        r'<div class="tgme_channel_info_header_title"[^>]*><span[^>]*>([^<]+)</span>'
    )
    DESC_RE = re.compile(
        r'<div class="tgme_channel_info_description">(.*?)</div>',
        re.DOTALL,
    )
    COUNTER_RE = re.compile(
        r'<div class="tgme_channel_info_counter">\s*<span class="counter_value">([^<]+)</span>\s*'
        r'<span class="counter_type">([^<]+)</span>'
    )
    HTML_TAG_RE = re.compile(r"<[^>]+>")

    async def scrape(self, channel: str) -> list[SocialPost]:
        channel = self._normalize(channel)
        if not channel:
            return []

        posts: list[SocialPost] = []
        async with httpx.AsyncClient(timeout=self.TIMEOUT_S, headers=self.UA, follow_redirects=True) as client:
            html_body = await self._fetch(client, channel)
            if not html_body:
                return posts

            bio = self._parse_bio(html_body, channel)
            if bio:
                posts.append(bio)
            posts.extend(self._parse_posts(html_body, channel))

        logger.info("Telegram: {} items for @{}", len(posts), channel)
        return posts

    @staticmethod
    def _normalize(channel: str) -> str:
        channel = channel.strip().lstrip("@").lstrip("/")
        if channel.startswith("https://t.me/"):
            channel = channel.split("/")[-1]
        return channel

    @classmethod
    def _clean(cls, text: str) -> str:
        text = cls.HTML_TAG_RE.sub(" ", text or "")
        text = html.unescape(text)
        return re.sub(r"\s+", " ", text).strip()

    async def _fetch(self, client: httpx.AsyncClient, channel: str) -> str | None:
        try:
            resp = await client.get(f"{self.BASE}/s/{channel}")
            if resp.status_code != 200:
                logger.warning("Telegram {} for @{}", resp.status_code, channel)
                return None
            if "tgme_page_description" in resp.text and "tgme_widget_message" not in resp.text:
                logger.warning("Telegram @{} is not a public channel or empty", channel)
            return resp.text
        except Exception as exc:
            logger.warning("Telegram fetch failed for @{}: {}", channel, exc)
            return None

    def _parse_bio(self, body: str, channel: str) -> SocialPost | None:
        title_m = self.TITLE_RE.search(body)
        desc_m = self.DESC_RE.search(body)
        title = self._clean(title_m.group(1)) if title_m else ""
        desc = self._clean(desc_m.group(1)) if desc_m else ""

        counters = []
        for val, typ in self.COUNTER_RE.findall(body):
            counters.append(f"{self._clean(val)} {self._clean(typ)}")
        meta = " | ".join(counters)

        parts = [title, desc, meta]
        text = "\n".join(p for p in parts if p).strip()
        if not text:
            return None
        return SocialPost(platform="telegram", kind="bio", context=channel, text=text[:800])

    def _parse_posts(self, body: str, channel: str) -> list[SocialPost]:
        out: list[SocialPost] = []
        texts = self.POST_TEXT_RE.findall(body)
        views = self.VIEWS_RE.findall(body)
        for idx, raw in enumerate(texts[-self.MAX_POSTS:]):
            text = self._clean(raw)
            if not text:
                continue
            view_count = views[-self.MAX_POSTS:][idx] if idx < len(views[-self.MAX_POSTS:]) else ""
            prefix = f"[👁 {view_count}] " if view_count else ""
            out.append(SocialPost(
                platform="telegram",
                kind="post",
                context=channel,
                text=f"{prefix}{text}"[:500],
            ))
        return out
