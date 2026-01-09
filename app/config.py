"""Configuration models for the scanner addon."""

import json
import re
from pathlib import Path

from pydantic import BaseModel, Field, validator


def parse_admin_ids(value) -> list[int]:
    if not value:
        return []
    if isinstance(value, int):
        return [value]
    if isinstance(value, list):
        ids = []
        for item in value:
            if item is None or item == "":
                continue
            try:
                ids.append(int(str(item).strip()))
            except ValueError:
                continue
        return ids
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return []
        parts = re.split(r"[,\s]+", raw)
        ids = []
        for part in parts:
            if not part:
                continue
            try:
                ids.append(int(part))
            except ValueError:
                continue
        return ids
    return []


class TelegramConfig(BaseModel):
    """Telegram delivery configuration."""

    enabled: bool = False
    bot_token: str = ""
    chat_id: str = ""
    admin_ids: list[int] = Field(default_factory=list)
    caption: str = "Scanned document"
    use_album: bool = True

    @validator("admin_ids", pre=True)
    def _parse_admin_ids(cls, value):
        return parse_admin_ids(value)


class AppConfig(BaseModel):
    """Main application configuration loaded from options.json."""

    device_id: str = ""
    output_format: str = "jpeg"
    quality: int = 90
    filename_pattern: str = "scan_{datetime}_{page}.{format}"
    save_to: str = "media"
    subdir: str = "scanner"
    resolution: int = 300
    printer_address: str = ""
    printer_name: str = ""
    telegram: TelegramConfig = Field(default_factory=TelegramConfig)

    @validator("telegram", pre=True)
    def _coerce_telegram(cls, value):
        if value is None:
            return {}
        return value


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
