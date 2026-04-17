"""Instagram public profile scraper via web_profile_info + feed/user pagination.

Uses curl_cffi to mimic Safari iOS TLS fingerprint — bypasses IG's httpx detection.
Requires X-IG-App-ID header but no login. Works for public profiles.

Optional sessionid cookie allows reading private profiles the authenticated user follows.
Not stored on backend — single-use per request.

Pagination:
  1. web_profile_info → user_id, bio, profile meta
  2. /api/v1/feed/user/{uid}/ with max_id → все посты постранично (12/страница)
  Cap MAX_POSTS чтобы не словить 429 и не тормозить pipeline.
"""
from __future__ import annotations

import asyncio

from curl_cffi.requests import AsyncSession
from loguru import logger

from vibecheck.schemas.profile import SocialPost


class InstagramScraper:
    """Scrape public (or session-accessible) IG profile metadata + captions."""

    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (iPhone; CPU iPhone OS 14_7_1 like Mac OS X) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) "
            "Version/14.1.2 Mobile/15E148 Safari/604.1"
        ),
        "X-IG-App-ID": "936619743392459",
        "Accept": "*/*",
    }
    WEB_PROFILE_URL = "https://i.instagram.com/api/v1/users/web_profile_info/"
    FEED_URL = "https://i.instagram.com/api/v1/feed/user/{user_id}/"
    IMPERSONATE = "safari_ios"
    MAX_RETRIES = 3
    TIMEOUT_S = 15
    MAX_POSTS = 100
    MAX_PAGES = 10

    async def scrape(
        self,
        username: str,
        ig_session: str | None = None,
    ) -> list[SocialPost]:
        username = username.lstrip("@").lstrip("/").strip()
        if not username:
            return []

        cookies = {"sessionid": ig_session.strip()} if ig_session else None
        async with AsyncSession() as session:
            profile = await self._fetch_profile(session, username, cookies)
            if not profile:
                return []
            user_id = profile.get("id")
            out: list[SocialPost] = [self._build_bio(profile, username)]
            if profile.get("is_private", False) or not user_id:
                logger.info("Instagram: {} items for @{} (bio only)", len(out), username)
                return out

            # Primary: mobile feed endpoint for full pagination (up to MAX_POSTS)
            posts = await self._paginate_feed(session, user_id, cookies)
            if posts:
                out.extend(self._build_posts(posts, username))
                logger.info("Instagram: {} items for @{} (via feed)", len(out), username)
                return out

            # Fallback: 12 posts already embedded in web_profile_info (for IPs where
            # /api/v1/feed/user/{uid}/ is blocked — happens on some datacenter egresses)
            edges = profile.get("edge_owner_to_timeline_media", {}).get("edges", [])
            out.extend(self._build_posts_from_edges(edges, username))
            logger.info("Instagram: {} items for @{} (via web_profile fallback)", len(out), username)
            return out

    async def _fetch_profile(
        self, session: AsyncSession, username: str, cookies: dict | None,
    ) -> dict | None:
        for attempt in range(self.MAX_RETRIES):
            try:
                resp = await session.get(
                    self.WEB_PROFILE_URL,
                    params={"username": username},
                    headers=self.HEADERS,
                    cookies=cookies,
                    impersonate=self.IMPERSONATE,
                    timeout=self.TIMEOUT_S,
                )
                if resp.status_code == 200:
                    return resp.json().get("data", {}).get("user") or None
                logger.info("IG profile {} for @{}, retry {}", resp.status_code, username, attempt + 1)
                await asyncio.sleep(2)
            except Exception as exc:
                logger.warning("IG profile attempt {} failed: {}", attempt + 1, exc)
                await asyncio.sleep(1)
        logger.warning("IG profile all retries failed for @{}", username)
        return None

    async def _paginate_feed(
        self, session: AsyncSession, user_id: str, cookies: dict | None,
    ) -> list[dict]:
        items: list[dict] = []
        max_id: str | None = None
        url = self.FEED_URL.format(user_id=user_id)
        for page in range(self.MAX_PAGES):
            params = {"max_id": max_id} if max_id else {}
            try:
                resp = await session.get(
                    url,
                    params=params,
                    headers=self.HEADERS,
                    cookies=cookies,
                    impersonate=self.IMPERSONATE,
                    timeout=self.TIMEOUT_S,
                )
            except Exception as exc:
                logger.warning("IG feed page {} failed: {}", page, exc)
                break
            if resp.status_code != 200:
                logger.warning("IG feed page {} HTTP {}", page, resp.status_code)
                break
            d = resp.json()
            page_items = d.get("items", []) or []
            items.extend(page_items)
            if len(items) >= self.MAX_POSTS or not d.get("more_available"):
                break
            max_id = d.get("next_max_id")
            if not max_id:
                break
        return items[: self.MAX_POSTS]

    @staticmethod
    def _build_bio(user: dict, username: str) -> SocialPost:
        bio = user.get("biography", "") or ""
        full_name = user.get("full_name", "") or ""
        category = user.get("category_name", "") or ""
        external_url = user.get("external_url", "") or ""
        followers = user.get("edge_followed_by", {}).get("count", 0) or user.get("follower_count", 0)
        following = user.get("edge_follow", {}).get("count", 0) or user.get("following_count", 0)
        posts_count = (
            user.get("edge_owner_to_timeline_media", {}).get("count", 0)
            or user.get("media_count", 0)
        )

        header = [full_name]
        if user.get("is_verified"):
            header.append("[verified]")
        if category:
            header.append(f"[{category}]")
        if user.get("is_private"):
            header.append("[private]")

        text = (
            f"{' '.join(header)}\n{bio}"
            + (f"\nLink: {external_url}" if external_url else "")
            + f"\nFollowers: {followers:,} | Following: {following:,} | Posts: {posts_count:,}"
        ).strip()

        return SocialPost(platform="instagram", kind="bio", context=username, text=text[:800])

    @staticmethod
    def _build_posts_from_edges(edges: list[dict], username: str) -> list[SocialPost]:
        """Parse web_profile_info's edge_owner_to_timeline_media (GraphQL structure)."""
        out: list[SocialPost] = []
        for edge in edges:
            node = edge.get("node", {}) or {}
            caps = node.get("edge_media_to_caption", {}).get("edges", [])
            caption = caps[0]["node"]["text"] if caps else ""
            likes = node.get("edge_liked_by", {}).get("count", 0) or 0
            comments = node.get("edge_media_to_comment", {}).get("count", 0) or 0
            typename = node.get("__typename", "GraphImage")
            is_video = node.get("is_video", False)
            kind = (
                "video" if is_video
                else ("carousel" if typename == "GraphSidecar" else "photo")
            )
            text = f"[{likes:,} likes, {comments:,} comments] {caption}"[:600]
            out.append(SocialPost(platform="instagram", kind=kind, context=username, text=text))
        return out

    @staticmethod
    def _build_posts(items: list[dict], username: str) -> list[SocialPost]:
        out: list[SocialPost] = []
        for it in items:
            caption = ""
            cap_obj = it.get("caption")
            if isinstance(cap_obj, dict):
                caption = cap_obj.get("text", "") or ""
            elif isinstance(cap_obj, str):
                caption = cap_obj
            likes = it.get("like_count", 0) or 0
            comments = it.get("comment_count", 0) or 0
            media_type = it.get("media_type", 1)
            # IG media_type: 1 photo, 2 video, 8 carousel
            kind = "video" if media_type == 2 else ("carousel" if media_type == 8 else "photo")
            if not caption:
                caption = ""
            text = f"[{likes:,} likes, {comments:,} comments] {caption}"[:600]
            out.append(SocialPost(platform="instagram", kind=kind, context=username, text=text))
        return out
