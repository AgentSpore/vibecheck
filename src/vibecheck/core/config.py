"""App config."""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    openrouter_api_key: str = ""
    agent_model: str = "openai/gpt-oss-120b:free"
    fallback_models: list[str] = [
        "openai/gpt-oss-120b:free",
        "z-ai/glm-4.5-air:free",
        "google/gemma-3-27b-it:free",
        "meta-llama/llama-3.3-70b-instruct:free",
        "nvidia/nemotron-3-super-120b-a12b:free",
        "qwen/qwen3-next-80b-a3b-instruct:free",
    ]
    retries_per_model: int = 2
    port: int = 8895

    # Residential proxy for Instagram (Smartproxy/Bright Data/etc.)
    # Format: "http://user:password@gate.smartproxy.com:7000"
    # Leave empty to fall back to direct requests (works locally, blocked on prod IPs).
    ig_proxy_url: str = ""

    # Steam Web API key — enables vanity URL -> SteamID64 resolution.
    # Obtain free at https://steamcommunity.com/dev/apikey. Empty = numeric IDs only.
    steam_api_key: str = ""


settings = Settings()
