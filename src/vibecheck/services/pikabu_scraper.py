"""Pikabu user profile scraper via HTML (RSS was discontinued).

Parses the public user page `https://pikabu.ru/@{user}`:
  - story titles (class="story__title-link")
  - story body text (class="story-block_type_text")

Pikabu sits behind DDoS-Guard but a realistic browser User-Agent passes through.
Response encoding is windows-1251 — httpx decodes automatically via charset header.
"""
from __future__ import annotations

import re

import httpx
from loguru import logger

from vibecheck.schemas.profile import SocialPost
from vibecheck.services._rss_base import RSSScraperBase


class PikabuScraper:
    UA = RSSScraperBase.UA
    TIMEOUT_S = 20.0
    MAX_ITEMS = 20

    ARTICLE_RE = re.compile(
        r'<article[^>]*class="story\b[^"]*"[^>]*>(.+?)</article>',
        re.DOTALL | re.IGNORECASE,
    )
    TITLE_RE = re.compile(
        r'class="story__title-link"[^>]*>([^<]+)</a>', re.IGNORECASE
    )
    TEXT_BLOCK_RE = re.compile(
        r'story-block_type_text[^>]*>(.+?)(?:</div>\s*</div>|</section>)',
        re.DOTALL | re.IGNORECASE,
    )
    TAG_RE = re.compile(r'<[^>]+>')

    @staticmethod
    def _normalize(raw: str) -> str:
        raw = raw.strip().lstrip("@").lstrip("/")
        if "pikabu.ru" in raw:
            raw = raw.rsplit("/", 1)[-1].lstrip("@")
        return raw

    async def scrape(self, username: str) -> list[SocialPost]:
        username = self._normalize(username)
        if not username:
            return []
        url = f"https://pikabu.ru/@{username}"
        try:
            async with httpx.AsyncClient(
                timeout=self.TIMEOUT_S, headers=self.UA, follow_redirects=True,
            ) as client:
                resp = await client.get(url)
                if resp.status_code != 200:
                    logger.warning("Pikabu {} for {}", resp.status_code, username)
                    return []
                return self._parse(resp.text, username)
        except Exception as exc:
            logger.warning("Pikabu fetch failed for {}: {}", username, exc)
            return []

    def _parse(self, body: str, username: str) -> list[SocialPost]:
        out: list[SocialPost] = []
        for raw in self.ARTICLE_RE.findall(body)[: self.MAX_ITEMS]:
            title_m = self.TITLE_RE.search(raw)
            title = RSSScraperBase.clean(title_m.group(1)) if title_m else ""
            text_parts = self.TEXT_BLOCK_RE.findall(raw)
            body_txt = " ".join(RSSScraperBase.clean(t) for t in text_parts)
            text = f"{title}\n{body_txt}".strip() if title and body_txt else (title or body_txt)
            if not text:
                continue
            out.append(SocialPost(
                platform="pikabu",
                kind="post",
                context=f"@{username}",
                text=text[:500],
            ))
        logger.info("Pikabu: {} items for @{}", len(out), username)
        return out
