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
            parsed_ids: list[int] = []
            if isinstance(admin_ids, str):
                raw_entries = admin_ids.split(",")
            elif isinstance(admin_ids, list):
                raw_entries = admin_ids
            elif isinstance(admin_ids, int):
                raw_entries = [admin_ids]
            else:
                raw_entries = []
            for entry in raw_entries:
                if entry is None:
                    continue
                if isinstance(entry, str):
                    entry = entry.strip()
                    if not entry:
                        continue
                try:
                    parsed_ids.append(int(entry))
                except (TypeError, ValueError):
                    continue
            telegram["admin_ids"] = parsed_ids
        return AppConfig(**data)
    except Exception as e:
        print(f"Warning: Failed to load options.json, using defaults: {e}")
        return AppConfig()
