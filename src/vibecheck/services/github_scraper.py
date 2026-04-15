"""GitHub public profile scraper via REST API."""
from __future__ import annotations

import httpx
from loguru import logger

from vibecheck.schemas.profile import SocialPost


class GitHubScraper:
    """Scrape public GitHub profile: bio, starred repos, recent events."""

    UA = {"User-Agent": "VibeCheck/0.1", "Accept": "application/vnd.github+json"}
    TIMEOUT_S = 15.0
    MAX_STARS = 30
    MAX_EVENTS = 20

    async def scrape(self, username: str) -> list[SocialPost]:
        username = username.lstrip("@").strip()
        if not username:
            return []

        posts: list[SocialPost] = []
        async with httpx.AsyncClient(timeout=self.TIMEOUT_S, headers=self.UA) as client:
            bio = await self._fetch_bio(client, username)
            if bio:
                posts.append(bio)
            posts.extend(await self._fetch_stars(client, username))
            posts.extend(await self._fetch_events(client, username))

        logger.info("GitHub: {} items for @{}", len(posts), username)
        return posts

    async def _fetch_bio(self, client: httpx.AsyncClient, username: str) -> SocialPost | None:
        try:
            resp = await client.get(f"https://api.github.com/users/{username}")
            if resp.status_code != 200:
                return None
            u = resp.json()
            parts = [
                u.get("bio") or "",
                f"Location: {u.get('location', '')}" if u.get("location") else "",
                f"Company: {u.get('company', '')}" if u.get("company") else "",
                f"Repos: {u.get('public_repos', 0)} | Followers: {u.get('followers', 0)}",
            ]
            bio = "\n".join([p for p in parts if p])
            if not bio:
                return None
            return SocialPost(platform="github", kind="bio", context=username, text=bio)
        except Exception as exc:
            logger.warning("GitHub profile failed: {}", exc)
            return None

    async def _fetch_stars(self, client: httpx.AsyncClient, username: str) -> list[SocialPost]:
        try:
            resp = await client.get(
                f"https://api.github.com/users/{username}/starred",
                params={"per_page": self.MAX_STARS, "sort": "created"},
            )
            if resp.status_code != 200:
                return []
            out: list[SocialPost] = []
            for repo in resp.json()[:self.MAX_STARS]:
                desc = repo.get("description") or ""
                lang = repo.get("language") or "?"
                topics = ", ".join(repo.get("topics", [])[:5])
                out.append(SocialPost(
                    platform="github",
                    kind="star",
                    context=f"{repo.get('full_name', '?')} ({lang})",
                    text=f"{desc} [topics: {topics}]".strip(),
                ))
            return out
        except Exception as exc:
            logger.warning("GitHub stars failed: {}", exc)
            return []

    async def _fetch_events(self, client: httpx.AsyncClient, username: str) -> list[SocialPost]:
        try:
            resp = await client.get(
                f"https://api.github.com/users/{username}/events/public",
                params={"per_page": self.MAX_EVENTS + 10},
            )
            if resp.status_code != 200:
                return []
            out: list[SocialPost] = []
            for ev in resp.json()[:self.MAX_EVENTS]:
                etype = ev.get("type", "")
                repo = ev.get("repo", {}).get("name", "?")
                payload = ev.get("payload", {})
                text = self._format_event(etype, payload)
                out.append(SocialPost(
                    platform="github",
                    kind=etype.replace("Event", "").lower(),
                    context=repo,
                    text=text,
                ))
            return out
        except Exception as exc:
            logger.warning("GitHub events failed: {}", exc)
            return []

    @staticmethod
    def _format_event(etype: str, payload: dict) -> str:
        if etype == "PushEvent":
            msgs = [c.get("message", "")[:120] for c in payload.get("commits", [])[:2]]
            return " | ".join(msgs)
        if etype == "IssuesEvent":
            return f"Issue: {payload.get('issue', {}).get('title', '')[:200]}"
        if etype == "PullRequestEvent":
            return f"PR: {payload.get('pull_request', {}).get('title', '')[:200]}"
        if etype == "IssueCommentEvent":
            return f"Comment: {payload.get('comment', {}).get('body', '')[:300]}"
        return etype
