"""FastAPI HTTP API for scanner control."""

import logging
import uuid
from typing import List, Dict, Any, Optional

from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel

from .config import AppConfig, ScanOverrides
from .scanner import list_devices, scan_document, ScannerError, DeviceNotFoundError
from .telegram import send_to_telegram


logger = logging.getLogger(__name__)


class ScanRequest(BaseModel):
    """Request model for scan endpoint."""

    device_id: Optional[str] = None
    output_format: Optional[str] = None
    quality: Optional[int] = None
    filename_pattern: Optional[str] = None
    caption: Optional[str] = None
    send_to_telegram: Optional[bool] = None
    resolution: Optional[int] = None


class ScanResponse(BaseModel):
    """Response model for scan endpoint."""

    success: bool
    request_id: str
    saved: List[str]
    telegram: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class DeviceInfo(BaseModel):
    """Device information model."""

    id: str
    name: str
    vendor: str = ""
    model: str = ""


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    version: str = "0.1.10"


# Global config will be injected
_app_config: Optional[AppConfig] = None


def get_app_config() -> AppConfig:
    """Dependency to get app configuration."""
    if _app_config is None:
        raise HTTPException(status_code=500, detail="Application not configured")
    return _app_config


def set_app_config(config: AppConfig):
    """Set the global app configuration."""
    global _app_config
    _app_config = config


def create_app() -> FastAPI:
    """Create FastAPI application."""
    app = FastAPI(
        title="Scanner API",
        description="Home Assistant Scanner Add-on API",
        version="0.1.10",
    )

    @app.get("/healthz", response_model=HealthResponse)
    async def health_check():
        """Health check endpoint."""
        return HealthResponse(status="ok")

    @app.get("/v1/devices", response_model=List[DeviceInfo])
    async def get_devices():
        """List available scanner devices."""
        try:
            devices = list_devices()
            return [
                DeviceInfo(
                    id=device.id,
                    name=device.name,
                    vendor=device.vendor,
                    model=device.model,
                )
                for device in devices
            ]
        except ScannerError as e:
            logger.error(f"Failed to list devices: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/v1/scan", response_model=ScanResponse)
    async def scan(request: ScanRequest, config: AppConfig = Depends(get_app_config)):
        """Trigger a scan operation."""
        request_id = str(uuid.uuid4())[:8]

        logger.info(f"[{request_id}] Scan request: {request.dict(exclude_unset=True)}")

        try:
            # Convert request to overrides
            overrides = ScanOverrides(**request.dict(exclude_unset=True))

            # Perform scan
            saved_files = scan_document(config, overrides)
            saved_paths = [str(path) for path in saved_files]

            logger.info(f"[{request_id}] Saved {len(saved_files)} files: {saved_paths}")

            # Handle Telegram delivery
            telegram_result = None
            should_send_telegram = (
                request.send_to_telegram
                if request.send_to_telegram is not None
                else config.telegram.enabled
            )

            if should_send_telegram:
                if not config.telegram.bot_token or not config.telegram.chat_id:
                    logger.warning(
                        f"[{request_id}] Telegram enabled but missing bot_token or chat_id"
                    )
                    telegram_result = {
                        "sent": False,
                        "error": "Missing Telegram credentials",
                    }
                else:
                    caption = request.caption or config.telegram.caption
                    telegram_result = send_to_telegram(
                        saved_files,
                        config.telegram.bot_token,
                        config.telegram.chat_id,
                        caption,
                        config.telegram.use_album,
                    )
                    logger.info(f"[{request_id}] Telegram result: {telegram_result}")

            return ScanResponse(
                success=True,
                request_id=request_id,
                saved=saved_paths,
                telegram=telegram_result,
            )

        except DeviceNotFoundError as e:
            logger.error(f"[{request_id}] Device not found: {e}")
            raise HTTPException(status_code=404, detail=str(e))
        except ScannerError as e:
            logger.error(f"[{request_id}] Scanner error: {e}")
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            logger.error(f"[{request_id}] Unexpected error: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    return app
