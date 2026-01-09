"""Configuration models for the scanner addon."""

import json
import re
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


def parse_admin_ids(value) -> list[int]:
    if value is None:
        return []
    raw_entries = []
    if isinstance(value, str):
        trimmed = value.strip()
        if not trimmed:
            return []
        if trimmed.startswith("["):
            try:
                parsed = json.loads(trimmed)
            except json.JSONDecodeError:
                parsed = trimmed
            value = parsed
        if isinstance(value, str):
            raw_entries = re.split(r"[,\s]+", value)
        else:
            raw_entries = value if isinstance(value, list) else [value]
    elif isinstance(value, list):
        raw_entries = value
    elif isinstance(value, int):
        raw_entries = [value]
    else:
        return []
    parsed_ids: list[int] = []
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
    return parsed_ids


def load_config() -> AppConfig:
    """Load configuration from Home Assistant options.json."""
    config_path = Path("/data/options.json")
    if not config_path.exists():
        # Default config for development/testing
        return AppConfig()

    try:
        with open(config_path, "r") as f:
            data = json.load(f)
        if isinstance(data, dict) and "admin_ids" in data and "telegram" not in data:
            data["telegram"] = {"admin_ids": data.get("admin_ids")}
        telegram = data.get("telegram")
        if isinstance(telegram, dict):
            telegram["admin_ids"] = parse_admin_ids(telegram.get("admin_ids"))
        return AppConfig(**data)
    except Exception as e:
        print(f"Warning: Failed to load options.json, using defaults: {e}")
        return AppConfig()
