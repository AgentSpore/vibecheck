"""Unit tests for profile_analyzer helper functions (hot-path ranking)."""
from __future__ import annotations

from vibecheck.schemas.profile import ScrapedProfile, SocialPost
from vibecheck.services.profile_analyzer import items_by_platform


def _post(platform: str, text: str = "hi") -> SocialPost:
    return SocialPost(platform=platform, kind="post", context="x", text=text)


def test_items_by_platform_empty() -> None:
    profile = ScrapedProfile()
    assert items_by_platform(profile) == {}


def test_items_by_platform_counts() -> None:
    profile = ScrapedProfile(posts=[
        _post("reddit"), _post("reddit"), _post("reddit"),
        _post("github"), _post("github"),
        _post("pikabu"),
    ])
    counts = items_by_platform(profile)
    assert counts == {"reddit": 3, "github": 2, "pikabu": 1}


def test_items_by_platform_sum_matches_total() -> None:
    profile = ScrapedProfile(posts=[
        _post("reddit"), _post("github"), _post("habr"),
        _post("mastodon"), _post("devto"),
    ])
    counts = items_by_platform(profile)
    assert sum(counts.values()) == profile.total_items == 5


def test_items_by_platform_single_platform() -> None:
    profile = ScrapedProfile(posts=[_post("steam") for _ in range(7)])
    assert items_by_platform(profile) == {"steam": 7}
