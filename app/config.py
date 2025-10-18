"""Configuration models for the scanner addon."""

import json
from pathlib import Path
from typing import Literal, Optional

from pydantic import BaseModel, Field


class TelegramConfig(BaseModel):
    """Telegram delivery configuration."""

    enabled: bool = False
    bot_token: str = ""
    chat_id: str = ""
    caption: str = "Scanned document"
    use_album: bool = True


class AppConfig(BaseModel):
    """Main application configuration loaded from options.json."""

    device_id: str = ""
    output_format: Literal["jpeg", "png"] = "jpeg"
    quality: int = Field(default=90, ge=1, le=100)
    filename_pattern: str = "scan_{datetime}_{page}.{format}"
    save_to: Literal["media", "share"] = "media"
    subdir: str = "scanner"
    resolution: int = Field(default=300, ge=75, le=1200)
    telegram: TelegramConfig = Field(default_factory=TelegramConfig)
    port: int = 46201

    @property
    def output_dir(self) -> Path:
        """Get the output directory path."""
        base_path = Path("/media" if self.save_to == "media" else "/share")
        return base_path / self.subdir


class ScanOverrides(BaseModel):
    """Optional overrides for scan requests."""

    device_id: Optional[str] = None
    output_format: Optional[Literal["jpeg", "png"]] = None
    quality: Optional[int] = Field(None, ge=1, le=100)
    filename_pattern: Optional[str] = None
    caption: Optional[str] = None
    send_to_telegram: Optional[bool] = None
    resolution: Optional[int] = Field(None, ge=75, le=1200)


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
