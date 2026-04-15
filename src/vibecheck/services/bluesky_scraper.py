"""Bluesky public profile scraper via atproto AppView API.

No auth required. Public endpoints:
- app.bsky.actor.getProfile — bio, followers, follows
- app.bsky.feed.getAuthorFeed — recent posts
"""
from __future__ import annotations

import httpx
from loguru import logger

from vibecheck.schemas.profile import SocialPost


class BlueskyScraper:
    """Scrape public Bluesky profile (bio + recent posts) via public AppView."""

    BASE = "https://public.api.bsky.app/xrpc"
    UA = {"User-Agent": "VibeCheck/0.1"}
    TIMEOUT_S = 15.0
    MAX_POSTS = 25

    async def scrape(self, handle: str) -> list[SocialPost]:
        handle = self._normalize(handle)
        if not handle:
            return []

        posts: list[SocialPost] = []
        async with httpx.AsyncClient(timeout=self.TIMEOUT_S, headers=self.UA) as client:
            bio = await self._fetch_profile(client, handle)
            if bio:
                posts.append(bio)
            posts.extend(await self._fetch_feed(client, handle))

        logger.info("Bluesky: {} items for @{}", len(posts), handle)
        return posts

    @staticmethod
    def _normalize(handle: str) -> str:
        handle = handle.lstrip("@").strip()
        if not handle:
            return ""
        if "." not in handle:
            handle = f"{handle}.bsky.social"
        return handle

    async def _fetch_profile(self, client: httpx.AsyncClient, handle: str) -> SocialPost | None:
        try:
            resp = await client.get(
                f"{self.BASE}/app.bsky.actor.getProfile",
                params={"actor": handle},
            )
            if resp.status_code != 200:
                return None
            u = resp.json()
            parts = [
                u.get("displayName") or "",
                u.get("description") or "",
                f"Followers: {u.get('followersCount', 0):,} | "
                f"Following: {u.get('followsCount', 0):,} | "
                f"Posts: {u.get('postsCount', 0):,}",
            ]
            text = "\n".join(p for p in parts if p).strip()
            if not text:
                return None
            return SocialPost(platform="bluesky", kind="bio", context=handle, text=text[:800])
        except Exception as exc:
            logger.warning("Bluesky profile failed for @{}: {}", handle, exc)
            return None

    async def _fetch_feed(self, client: httpx.AsyncClient, handle: str) -> list[SocialPost]:
        try:
            resp = await client.get(
                f"{self.BASE}/app.bsky.feed.getAuthorFeed",
                params={"actor": handle, "limit": self.MAX_POSTS, "filter": "posts_no_replies"},
            )
            if resp.status_code != 200:
                return []
            out: list[SocialPost] = []
            for item in resp.json().get("feed", [])[:self.MAX_POSTS]:
                post = item.get("post", {})
                record = post.get("record", {})
                text = record.get("text", "") or ""
                likes = post.get("likeCount", 0)
                reposts = post.get("repostCount", 0)
                replies = post.get("replyCount", 0)
                reason = item.get("reason", {}).get("$type", "")
                kind = "repost" if "repost" in reason else "post"
                if not text:
                    continue
                out.append(SocialPost(
                    platform="bluesky",
                    kind=kind,
                    context=handle,
                    text=f"[♥{likes} ↻{reposts} 💬{replies}] {text}"[:500],
                ))
            return out
        except Exception as exc:
            logger.warning("Bluesky feed failed for @{}: {}", handle, exc)
            return []
