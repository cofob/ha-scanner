"""Configuration models for the scanner addon."""

import json
from pathlib import Path

from pydantic import BaseModel, Field


class TelegramConfig(BaseModel):
    """Telegram delivery configuration."""

    bot_token: str = ""
    chat_id: str = ""


class AppConfig(BaseModel):
    """Main application configuration loaded from options.json."""

    telegram: TelegramConfig = Field(default_factory=TelegramConfig)


def load_config() -> AppConfig:
    """Load configuration from Home Assistant options.json."""
    config_path = Path("/data/options.json")
    if not config_path.exists():
        # Default config for development/testing
        return AppConfig()

    try:
        with open(config_path, "r") as f:
            data = json.load(f)
        return AppConfig(**data)
    except Exception as e:
        print(f"Warning: Failed to load options.json, using defaults: {e}")
        return AppConfig()
