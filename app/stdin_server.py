"""STDIN command server for Home Assistant integration."""

from __future__ import annotations

import asyncio
import json
import logging
import sys
import threading
import uuid
from typing import Any, Callable, Dict, Optional

from pydantic import ValidationError

from .config import AppConfig, ScanOverrides
from .scanner import DeviceNotFoundError, ScannerError, list_devices, scan_document
from .telegram import send_to_telegram

logger = logging.getLogger(__name__)


class StdinCommandServer:
    """Background STDIN listener that handles Home Assistant commands."""

    def __init__(self, loop: asyncio.AbstractEventLoop, config_provider: Callable[[], AppConfig]):
        self._loop = loop
        self._config_provider = config_provider
        self._thread: Optional[threading.Thread] = None
        self._running = False

    def start(self) -> None:
        """Start the background thread that reads STDIN."""
        if self._running:
            logger.warning("STDIN command server already running")
            return

        self._running = True
        self._thread = threading.Thread(target=self._reader, name="stdin-command-server", daemon=True)
        self._thread.start()
        logger.info("STDIN server ready for Home Assistant commands")

    def stop(self) -> None:
        """Signal the background thread to stop."""
        self._running = False

    def wait(self) -> None:
        """Wait for the background thread to exit (if running)."""
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)

    def _reader(self) -> None:
        """Read JSON commands from STDIN and dispatch them to the event loop."""
        while self._running:
            try:
                line = sys.stdin.readline()
            except Exception as exc:  # pragma: no cover - defensive logging
                logger.error(f"STDIN read error: {exc}")
                break

            if not line:
                logger.warning("STDIN input stream closed; continuing without STDIN commands")
                break

            payload = line.strip()
            if not payload:
                continue

            future = asyncio.run_coroutine_threadsafe(self._handle_payload(payload), self._loop)
            try:
                future.result()
            except Exception as exc:  # pragma: no cover - already logged in coroutine
                logger.error(f"Unhandled error processing STDIN command: {exc}")

    async def _handle_payload(self, raw_payload: str) -> None:
        """Parse and process a single STDIN payload."""
        try:
            message = json.loads(raw_payload)
        except json.JSONDecodeError as exc:
            logger.error(f"Invalid STDIN payload (JSON decode error): {exc}")
            self._send_response({"success": False, "error": "invalid_json", "detail": str(exc)})
            return

        if not isinstance(message, dict):
            logger.error("Invalid STDIN payload: expected JSON object")
            self._send_response({"success": False, "error": "invalid_payload", "detail": "Expected JSON object"})
            return

        command = message.get("command")
        if not command:
            logger.error("STDIN payload missing 'command' field")
            self._send_response({"success": False, "error": "missing_command"})
            return

        if command == "list_devices":
            await self._handle_list_devices()
        elif command == "scan":
            overrides = message.get("overrides") or {}
            await self._handle_scan(overrides)
        else:
            logger.error(f"Unknown STDIN command: {command}")
            self._send_response({"success": False, "error": "unknown_command", "command": command})

    async def _handle_list_devices(self) -> None:
        """Handle the list_devices command."""
        logger.info("STDIN command: list_devices")
        try:
            devices = await asyncio.to_thread(list_devices)
            response = {
                "success": True,
                "command": "list_devices",
                "devices": [device.to_dict() for device in devices],
            }
            self._send_response(response)
        except ScannerError as exc:
            logger.error(f"Failed to list devices: {exc}")
            self._send_response({"success": False, "error": "scanner_error", "detail": str(exc)})

    async def _handle_scan(self, overrides_data: Dict[str, Any]) -> None:
        """Handle the scan command with optional overrides."""
        request_id = uuid.uuid4().hex[:8]
        logger.info(f"[{request_id}] STDIN command: scan {overrides_data}")

        try:
            overrides = ScanOverrides(**overrides_data) if overrides_data else None
        except ValidationError as exc:
            logger.error(f"[{request_id}] Invalid scan overrides: {exc}")
            self._send_response(
                {
                    "success": False,
                    "error": "invalid_overrides",
                    "request_id": request_id,
                    "detail": exc.errors(),
                }
            )
            return

        config = self._config_provider()
        if config is None:
            error_msg = "Application configuration not available"
            logger.error(f"[{request_id}] {error_msg}")
            self._send_response({"success": False, "error": "config_missing", "request_id": request_id})
            return

        try:
            saved_files = await asyncio.to_thread(scan_document, config, overrides)
            saved_paths = [str(path) for path in saved_files]
            logger.info(f"[{request_id}] Saved {len(saved_files)} file(s): {saved_paths}")

            telegram_result: Optional[Dict[str, Any]] = None
            should_send = (
                overrides.send_to_telegram if overrides and overrides.send_to_telegram is not None else config.telegram.enabled
            )

            if should_send:
                if not config.telegram.bot_token or not config.telegram.chat_id:
                    logger.warning(f"[{request_id}] Telegram enabled but missing bot_token or chat_id")
                    telegram_result = {"sent": False, "error": "Missing Telegram credentials"}
                else:
                    caption = overrides.caption if overrides and overrides.caption else config.telegram.caption
                    telegram_result = await asyncio.to_thread(
                        send_to_telegram,
                        saved_files,
                        config.telegram.bot_token,
                        config.telegram.chat_id,
                        caption,
                        config.telegram.use_album,
                    )
                    logger.info(f"[{request_id}] Telegram result: {telegram_result}")

            self._send_response(
                {
                    "success": True,
                    "command": "scan",
                    "request_id": request_id,
                    "saved": saved_paths,
                    "telegram": telegram_result,
                }
            )
        except DeviceNotFoundError as exc:
            logger.error(f"[{request_id}] Device not found: {exc}")
            self._send_response(
                {"success": False, "error": "device_not_found", "request_id": request_id, "detail": str(exc)}
            )
        except ScannerError as exc:
            logger.error(f"[{request_id}] Scanner error: {exc}")
            self._send_response({"success": False, "error": "scanner_error", "request_id": request_id, "detail": str(exc)})
        except Exception as exc:  # pragma: no cover - safety net
            logger.exception(f"[{request_id}] Unexpected error during scan")
            self._send_response(
                {"success": False, "error": "unexpected_error", "request_id": request_id, "detail": str(exc)}
            )

    @staticmethod
    def _send_response(payload: Dict[str, Any]) -> None:
        """Emit a JSON response to STDOUT for Home Assistant to consume."""
        try:
            sys.stdout.write(json.dumps(payload) + "\n")
            sys.stdout.flush()
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.error(f"Failed to write STDIN response: {exc}")