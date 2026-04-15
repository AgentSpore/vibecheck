"""HackerNews public user activity via Algolia + official API.

Free, no auth. Algolia: full-text search of all comments/stories by author.
Official: user metadata (karma, about, created_at).
"""
from __future__ import annotations

import html
import re

import httpx
from loguru import logger

from vibecheck.schemas.profile import SocialPost


class HackerNewsScraper:
    """Scrape HN user: karma + bio + recent comments/stories via Algolia."""

    OFFICIAL = "https://hacker-news.firebaseio.com/v0"
    ALGOLIA = "https://hn.algolia.com/api/v1"
    UA = {"User-Agent": "VibeCheck/0.1"}
    TIMEOUT_S = 15.0
    MAX_ITEMS = 25
    HTML_TAG_RE = re.compile(r"<[^>]+>")

    async def scrape(self, username: str) -> list[SocialPost]:
        username = username.lstrip("@").strip()
        if not username:
            return []

        posts: list[SocialPost] = []
        async with httpx.AsyncClient(timeout=self.TIMEOUT_S, headers=self.UA) as client:
            bio = await self._fetch_bio(client, username)
            if bio:
                posts.append(bio)
            posts.extend(await self._fetch_items(client, username))

        logger.info("HackerNews: {} items for {}", len(posts), username)
        return posts

    @classmethod
    def _clean(cls, text: str) -> str:
        text = html.unescape(text or "")
        text = cls.HTML_TAG_RE.sub(" ", text)
        return re.sub(r"\s+", " ", text).strip()

    async def _fetch_bio(self, client: httpx.AsyncClient, username: str) -> SocialPost | None:
        try:
            resp = await client.get(f"{self.OFFICIAL}/user/{username}.json")
            if resp.status_code != 200 or resp.text == "null":
                return None
            u = resp.json() or {}
            about = self._clean(u.get("about", ""))
            karma = u.get("karma", 0)
            submitted = len(u.get("submitted", []))
            parts = [
                f"Karma: {karma:,} | Submitted: {submitted:,}",
                about,
            ]
            text = "\n".join(p for p in parts if p).strip()
            if not text:
                return None
            return SocialPost(platform="hackernews", kind="bio", context=username, text=text[:800])
        except Exception as exc:
            logger.warning("HN bio failed for {}: {}", username, exc)
            return None

    async def _fetch_items(self, client: httpx.AsyncClient, username: str) -> list[SocialPost]:
        try:
            resp = await client.get(
                f"{self.ALGOLIA}/search_by_date",
                params={
                    "tags": f"(comment,story),author_{username}",
                    "hitsPerPage": self.MAX_ITEMS,
                },
            )
            if resp.status_code != 200:
                return []
            out: list[SocialPost] = []
            for hit in resp.json().get("hits", [])[:self.MAX_ITEMS]:
                is_comment = hit.get("comment_text") is not None
                text = self._clean(hit.get("comment_text") or hit.get("story_text") or hit.get("title") or "")
                if not text:
                    continue
                ctx = hit.get("story_title") or "HN"
                points = hit.get("points") or 0
                kind = "comment" if is_comment else "story"
                prefix = f"[↑{points}] " if not is_comment else ""
                out.append(SocialPost(
                    platform="hackernews",
                    kind=kind,
                    context=ctx[:80],
                    text=f"{prefix}{text}"[:500],
                ))
            return out
        except Exception as exc:
            logger.warning("HN items failed for {}: {}", username, exc)
            return []
