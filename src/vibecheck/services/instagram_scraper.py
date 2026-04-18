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

from vibecheck.core.config import settings
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
    # Multiple hosts — some datacenter IPs get blocked on i.instagram.com but
    # pass through on www./b.i./api. subdomains.
    HOSTS = [
        "https://i.instagram.com",
        "https://www.instagram.com",
        "https://b.i.instagram.com",
        "https://api.instagram.com",
    ]
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
        session_kwargs: dict = {}
        if settings.ig_proxy_url:
            session_kwargs["proxy"] = settings.ig_proxy_url
            logger.debug("IG: using residential proxy")
        async with AsyncSession(**session_kwargs) as session:
            profile = await self._fetch_profile(session, username, cookies)
            if not profile:
                return []
            user_id = profile.get("id")
            out: list[SocialPost] = [self._build_bio(profile, username)]
            if profile.get("is_private", False) or not user_id:
                logger.info("Instagram: {} items for @{} (bio only)", len(out), username)
                return out

            # Try each feed host until one works (datacenter IP blocks vary per host)
            for host in self.HOSTS:
                posts = await self._paginate_feed(session, user_id, cookies, host)
                if posts:
                    out.extend(self._build_posts(posts, username))
                    logger.info("Instagram: {} items for @{} (via {})", len(out), username, host)
                    return out

            # Fallback: 12 posts already embedded in web_profile_info (if ALL feed
            # hosts blocked — happens on some datacenter egresses)
            edges = profile.get("edge_owner_to_timeline_media", {}).get("edges", [])
            out.extend(self._build_posts_from_edges(edges, username))
            logger.info("Instagram: {} items for @{} (via web_profile fallback)", len(out), username)
            return out

    async def _fetch_profile(
        self, session: AsyncSession, username: str, cookies: dict | None,
    ) -> dict | None:
        # Try each host — skip to next on non-200 immediately (no sleep).
        for host in self.HOSTS:
            url = f"{host}/api/v1/users/web_profile_info/"
            try:
                resp = await session.get(
                    url,
                    params={"username": username},
                    headers=self.HEADERS,
                    cookies=cookies,
                    impersonate=self.IMPERSONATE,
                    timeout=self.TIMEOUT_S,
                )
                if resp.status_code == 200:
                    user = resp.json().get("data", {}).get("user") or None
                    if user:
                        logger.info("IG profile ok via {} for @{}", host, username)
                        return user
                else:
                    logger.info("IG profile {} via {} for @{}", resp.status_code, host, username)
            except Exception as exc:
                logger.warning("IG profile via {} failed: {}", host, exc)
        logger.warning("IG profile: all hosts failed for @{}", username)
        return None

    async def _paginate_feed(
        self, session: AsyncSession, user_id: str, cookies: dict | None, host: str,
    ) -> list[dict]:
        items: list[dict] = []
        max_id: str | None = None
        url = f"{host}/api/v1/feed/user/{user_id}/"
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
                logger.warning("IG feed {} p{} failed: {}", host, page, exc)
                break
            if resp.status_code != 200:
                logger.info("IG feed {} p{} HTTP {}", host, page, resp.status_code)
                break
            try:
                d = resp.json()
            except Exception:
                logger.info("IG feed {} p{} non-JSON", host, page)
                break
            page_items = d.get("items", []) or []
            if not page_items and page == 0:
                break  # empty first page → this host doesn't work
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
