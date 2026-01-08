"""Configuration models for the scanner addon."""

import json
from pathlib import Path

from pydantic import BaseModel, Field


class TelegramConfig(BaseModel):
    """Telegram delivery configuration."""

    enabled: bool = False
    bot_token: str = ""
    chat_id: str = ""
    admin_ids: list[int] = Field(default_factory=list)


class AppConfig(BaseModel):
    """Main application configuration loaded from options.json."""

    save_to: str = "media"
    subdir: str = "scanner"
    resolution: int = 300
    printer_name: str = ""
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
        telegram = data.get("telegram")
        if isinstance(telegram, dict):
            admin_ids = telegram.get("admin_ids")
            if isinstance(admin_ids, str):
                parsed_ids = []
                for entry in admin_ids.split(","):
                    entry = entry.strip()
                    if not entry:
                        continue
                    try:
                        parsed_ids.append(int(entry))
                    except ValueError:
                        continue
                telegram["admin_ids"] = parsed_ids
        return AppConfig(**data)
    except Exception as e:
        print(f"Warning: Failed to load options.json, using defaults: {e}")
        return AppConfig()
