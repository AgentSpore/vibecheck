"""Steam public profile scraper via community XML endpoint.

No auth. Returns bio + most-played games + groups.
Supports vanity URL (`/id/{name}`) and SteamID64 (`/profiles/{id}`).
"""
from __future__ import annotations

import html
import re

import httpx
from loguru import logger

from vibecheck.schemas.profile import SocialPost


class SteamScraper:
    """Parse Steam community XML profile."""

    UA = {"User-Agent": "VibeCheck/0.1"}
    TIMEOUT_S = 15.0
    MAX_GAMES = 10
    MAX_GROUPS = 5

    TAG_RE = {
        "steamID": re.compile(r"<steamID><!\[CDATA\[(.+?)\]\]></steamID>", re.DOTALL),
        "realname": re.compile(r"<realname>(?:<!\[CDATA\[)?(.+?)(?:\]\]>)?</realname>", re.DOTALL),
        "summary": re.compile(r"<summary>(?:<!\[CDATA\[)?(.+?)(?:\]\]>)?</summary>", re.DOTALL),
        "location": re.compile(r"<location>(?:<!\[CDATA\[)?(.+?)(?:\]\]>)?</location>", re.DOTALL),
        "memberSince": re.compile(r"<memberSince>(.+?)</memberSince>"),
        "privacyState": re.compile(r"<privacyState>(\w+)</privacyState>"),
        "vacBanned": re.compile(r"<vacBanned>(\d)</vacBanned>"),
        "tradeBanState": re.compile(r"<tradeBanState>(\w+)</tradeBanState>"),
        "hoursPlayed2Wk": re.compile(r"<hoursPlayed2Wk>([\d.]+)</hoursPlayed2Wk>"),
    }
    GAME_RE = re.compile(r"<mostPlayedGame>(.+?)</mostPlayedGame>", re.DOTALL)
    GAME_NAME_RE = re.compile(r"<gameName><!\[CDATA\[(.+?)\]\]></gameName>")
    GAME_HOURS_RE = re.compile(r"<hoursPlayed>([\d.]+)</hoursPlayed>")
    GROUP_RE = re.compile(r"<group[^>]*>(.+?)</group>", re.DOTALL)
    GROUP_NAME_RE = re.compile(r"<groupName><!\[CDATA\[(.+?)\]\]></groupName>")
    HTML_TAG_RE = re.compile(r"<[^>]+>")

    async def scrape(self, steam_id: str) -> list[SocialPost]:
        steam_id = steam_id.strip().lstrip("@").lstrip("/")
        if not steam_id:
            return []

        url = self._build_url(steam_id)
        try:
            async with httpx.AsyncClient(timeout=self.TIMEOUT_S, headers=self.UA, follow_redirects=True) as client:
                resp = await client.get(url)
                if resp.status_code != 200 or "<profile>" not in resp.text[:200]:
                    logger.warning("Steam {} for {} ({})", resp.status_code, steam_id, url)
                    return []
                posts = self._parse(resp.text, steam_id)
                logger.info("Steam: {} items for {}", len(posts), steam_id)
                return posts
        except Exception as exc:
            logger.warning("Steam fetch failed for {}: {}", steam_id, exc)
            return []

    @staticmethod
    def _build_url(ident: str) -> str:
        if ident.isdigit() and len(ident) >= 15:
            return f"https://steamcommunity.com/profiles/{ident}?xml=1"
        return f"https://steamcommunity.com/id/{ident}?xml=1"

    @classmethod
    def _extract(cls, pattern: re.Pattern, body: str) -> str:
        m = pattern.search(body)
        return m.group(1).strip() if m else ""

    @classmethod
    def _clean(cls, text: str) -> str:
        text = html.unescape(text or "")
        text = cls.HTML_TAG_RE.sub(" ", text)
        return re.sub(r"\s+", " ", text).strip()

    def _parse(self, body: str, ident: str) -> list[SocialPost]:
        out: list[SocialPost] = []
        bio = self._build_bio(body, ident)
        if bio:
            out.append(bio)
        out.extend(self._build_games(body, ident))
        out.extend(self._build_groups(body, ident))
        return out

    def _build_bio(self, body: str, ident: str) -> SocialPost | None:
        name = self._extract(self.TAG_RE["steamID"], body)
        real = self._extract(self.TAG_RE["realname"], body)
        summary = self._clean(self._extract(self.TAG_RE["summary"], body))
        location = self._extract(self.TAG_RE["location"], body)
        member = self._extract(self.TAG_RE["memberSince"], body)
        privacy = self._extract(self.TAG_RE["privacyState"], body)
        vac = self._extract(self.TAG_RE["vacBanned"], body)
        hours2wk = self._extract(self.TAG_RE["hoursPlayed2Wk"], body)

        header = [name, f"({real})" if real else ""]
        if privacy and privacy != "public":
            header.append(f"[{privacy}]")
        if vac == "1":
            header.append("[VAC-banned]")
        parts = [
            " ".join(p for p in header if p),
            summary,
            f"Location: {location}" if location else "",
            f"Member since: {member}" if member else "",
            f"Hours last 2wk: {hours2wk}" if hours2wk else "",
        ]
        text = "\n".join(p for p in parts if p).strip()
        if not text:
            return None
        return SocialPost(platform="steam", kind="bio", context=ident, text=text[:800])

    def _build_games(self, body: str, ident: str) -> list[SocialPost]:
        out: list[SocialPost] = []
        for raw in self.GAME_RE.findall(body)[:self.MAX_GAMES]:
            name = self._extract(self.GAME_NAME_RE, raw)
            hours = self._extract(self.GAME_HOURS_RE, raw)
            if not name:
                continue
            out.append(SocialPost(
                platform="steam",
                kind="game",
                context=ident,
                text=f"{name} · {hours}h played",
            ))
        return out

    def _build_groups(self, body: str, ident: str) -> list[SocialPost]:
        out: list[SocialPost] = []
        for raw in self.GROUP_RE.findall(body)[:self.MAX_GROUPS]:
            name = self._extract(self.GROUP_NAME_RE, raw)
            if not name:
                continue
            out.append(SocialPost(
                platform="steam",
                kind="group",
                context=ident,
                text=name,
            ))
        return out
