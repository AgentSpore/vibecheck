"""Instagram public profile scraper via web_profile_info endpoint.

Uses curl_cffi to mimic Safari iOS TLS fingerprint — bypasses IG's httpx detection.
Requires X-IG-App-ID header but no login. Works for public profiles.

Optional sessionid cookie allows reading private profiles the authenticated user follows.
Not stored on backend — single-use per request.
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
    ENDPOINT = "https://i.instagram.com/api/v1/users/web_profile_info/"
    IMPERSONATE = "safari_ios"
    MAX_RETRIES = 3
    TIMEOUT_S = 15

    async def scrape(
        self,
        username: str,
        max_posts: int = 12,
        ig_session: str | None = None,
    ) -> list[SocialPost]:
        username = username.lstrip("@").lstrip("/").strip()
        if not username:
            return []

        data = await self._fetch_profile(username, ig_session)
        if not data:
            return []

        return self._parse(data, username, max_posts)

    async def _fetch_profile(self, username: str, ig_session: str | None) -> dict | None:
        cookies = {"sessionid": ig_session.strip()} if ig_session else None
        try:
            async with AsyncSession() as session:
                for attempt in range(self.MAX_RETRIES):
                    try:
                        resp = await session.get(
                            self.ENDPOINT,
                            params={"username": username},
                            headers=self.HEADERS,
                            cookies=cookies,
                            impersonate=self.IMPERSONATE,
                            timeout=self.TIMEOUT_S,
                        )
                        if resp.status_code == 200:
                            return resp.json()
                        logger.info("IG {} for @{}, retry {}",
                                    resp.status_code, username, attempt + 1)
                        await asyncio.sleep(2)
                    except Exception as exc:
                        logger.warning("IG attempt {} failed: {}", attempt + 1, exc)
                        await asyncio.sleep(1)
            logger.warning("IG all retries failed for @{}", username)
            return None
        except Exception as exc:
            logger.warning("IG request failed for @{}: {}", username, exc)
            return None

    def _parse(self, data: dict, username: str, max_posts: int) -> list[SocialPost]:
        posts: list[SocialPost] = []
        user = data.get("data", {}).get("user", {})
        if not user:
            logger.warning("IG: user not found for @{}", username)
            return posts

        posts.append(self._build_bio(user, username))
        if not user.get("is_private", False):
            posts.extend(self._build_posts(user, username, max_posts))
        logger.info("Instagram: {} items for @{}", len(posts), username)
        return posts

    @staticmethod
    def _build_bio(user: dict, username: str) -> SocialPost:
        bio = user.get("biography", "") or ""
        full_name = user.get("full_name", "") or ""
        category = user.get("category_name", "") or ""
        external_url = user.get("external_url", "") or ""
        followers = user.get("edge_followed_by", {}).get("count", 0)
        following = user.get("edge_follow", {}).get("count", 0)
        posts_count = user.get("edge_owner_to_timeline_media", {}).get("count", 0)

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
    def _build_posts(user: dict, username: str, max_posts: int) -> list[SocialPost]:
        out: list[SocialPost] = []
        edges = user.get("edge_owner_to_timeline_media", {}).get("edges", [])
        for edge in edges[:max_posts]:
            node = edge.get("node", {})
            caps = node.get("edge_media_to_caption", {}).get("edges", [])
            caption = caps[0]["node"]["text"] if caps else ""
            likes = node.get("edge_liked_by", {}).get("count", 0)
            comments = node.get("edge_media_to_comment", {}).get("count", 0)
            media_type = node.get("__typename", "GraphImage")
            is_video = node.get("is_video", False)

            kind = (
                "video" if is_video
                else ("carousel" if media_type == "GraphSidecar" else "photo")
            )
            text = f"[{likes:,} likes, {comments:,} comments] {caption}"[:600]
            out.append(SocialPost(platform="instagram", kind=kind, context=username, text=text))
        return out
