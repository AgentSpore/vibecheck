"""Vibe profile DTOs."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class SocialPost(BaseModel):
    """Single post/comment/activity."""

    platform: Literal[
        "reddit", "github", "instagram", "bluesky", "hackernews",
        "habr", "telegram", "mastodon", "devto", "substack",
        "steam", "letterboxd", "goodreads", "pikabu",
    ]
    kind: str  # post, comment, star, bio, etc.
    context: str = ""  # subreddit, repo, etc.
    text: str


class ScrapedProfile(BaseModel):
    """Raw data from scrapers."""

    reddit_username: str | None = None
    github_username: str | None = None
    instagram_username: str | None = None
    bluesky_handle: str | None = None
    hackernews_username: str | None = None
    habr_username: str | None = None
    telegram_channel: str | None = None
    mastodon_handle: str | None = None  # format: @user@instance.social
    devto_username: str | None = None
    substack_username: str | None = None  # subdomain
    steam_id: str | None = None  # custom id or steamid64
    letterboxd_username: str | None = None
    goodreads_user_id: str | None = None  # numeric id from profile URL
    pikabu_username: str | None = None
    posts: list[SocialPost] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)

    @property
    def total_items(self) -> int:
        return len(self.posts)


class VibeTrait(BaseModel):
    name: str = Field(description="Short trait name, e.g. 'Curious', 'Opinionated', 'Wholesome'")
    evidence: str = Field(description="1 sentence with concrete evidence from posts")
    strength: int = Field(ge=1, le=5, description="1=weak signal, 5=strong signal")


class RedFlag(BaseModel):
    category: str = Field(description="e.g. 'Controversial content', 'Aggressive tone', 'Toxic subs'")
    description: str = Field(description="What specifically was observed")
    severity: int = Field(ge=1, le=5)


Gender = Literal["boy", "girl", "neutral"]
Mood = Literal["joyful", "chill", "curious", "focused", "shy", "sad", "angry", "suspicious"]
Accessory = Literal[
    "glasses", "shades", "headphones", "cap", "beanie", "crown",
    "flowers", "laptop", "gamepad", "camera", "paintbrush", "mic",
    "book", "mask", "hoodie", "earring", "piercing", "scarf"
]


class AvatarSpec(BaseModel):
    gender: Gender = Field(description="Apparent gender expression from profile: boy / girl / neutral")
    mood: Mood = Field(description="Dominant emotional mood derived from content + score")
    vibe_color: str = Field(description="Hex color capturing overall vibe (e.g. '#ff6b9d' for playful, '#7c4dff' for artsy)")
    accessories: list[Accessory] = Field(
        default_factory=list, max_length=3,
        description="1-3 accessories matching dominant interests/identity"
    )
    emoji: str = Field(description="Single emoji that captures the person")


class VibeReport(BaseModel):
    """Full vibe analysis output."""

    headline: str = Field(description="One-sentence summary of this person's vibe")
    top_interests: list[str] = Field(
        default_factory=list, description="5-10 topics, sorted by strength"
    )
    personality_traits: list[VibeTrait] = Field(default_factory=list, min_length=0, max_length=8)
    red_flags: list[RedFlag] = Field(default_factory=list)
    green_flags: list[str] = Field(
        default_factory=list, description="Positive signals — wholesome, thoughtful, skilled"
    )
    vibe_score: int = Field(ge=0, le=100, description="Overall 'good vibe' score, 0-100")
    summary: str = Field(description="2-3 paragraph human-readable summary")
    avatar: AvatarSpec = Field(description="Cartoon avatar spec derived from analysis")


AnalysisMode = Literal["vibe", "self", "catfish"]


class AnalyzeRequest(BaseModel):
    reddit_username: str | None = None
    github_username: str | None = None
    instagram_username: str | None = None
    bluesky_handle: str | None = None
    hackernews_username: str | None = None
    habr_username: str | None = None
    telegram_channel: str | None = None
    mastodon_handle: str | None = None
    devto_username: str | None = None
    substack_username: str | None = None
    steam_id: str | None = None
    letterboxd_username: str | None = None
    goodreads_user_id: str | None = None
    pikabu_username: str | None = None
    ig_session: str | None = None
    mode: AnalysisMode = "vibe"
