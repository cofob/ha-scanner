"""Telegram integration for sending scanned documents."""

import logging
import json
from pathlib import Path
from typing import List, Optional, Dict, Any
import asyncio
import mimetypes

import httpx


logger = logging.getLogger(__name__)


class TelegramError(Exception):
    """Telegram API error."""

    pass


async def send_document(
    bot_token: str, chat_id: str, file_path: Path, caption: Optional[str] = None
) -> Dict[str, Any]:
    """Send a single document to Telegram."""
    url = f"https://api.telegram.org/bot{bot_token}/sendDocument"

    # Determine MIME type
    mime_type, _ = mimetypes.guess_type(str(file_path))
    if not mime_type:
        mime_type = "application/octet-stream"

    files = {"document": (file_path.name, file_path.read_bytes(), mime_type)}

    data = {
        "chat_id": chat_id,
    }

    if caption:
        data["caption"] = caption

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(url, files=files, data=data)
            response.raise_for_status()
            result = response.json()

            if not result.get("ok"):
                raise TelegramError(
                    f"Telegram API error: {result.get('description', 'Unknown error')}"
                )

            logger.info(f"Sent document {file_path.name} to Telegram chat {chat_id}")
            return result["result"]

        except httpx.HTTPStatusError as e:
            logger.error(
                f"HTTP error sending to Telegram: {e.response.status_code} - {e.response.text}"
            )
            raise TelegramError(f"HTTP {e.response.status_code}: {e.response.text}")
        except Exception as e:
            logger.error(f"Error sending document to Telegram: {e}")
            raise TelegramError(str(e))


async def send_media_group(
    bot_token: str, chat_id: str, file_paths: List[Path], caption: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Send multiple files as a media group (album) to Telegram."""
    if len(file_paths) > 10:
        raise TelegramError("Telegram media groups can contain at most 10 items")

    if len(file_paths) == 1:
        # Use sendDocument for single files
        result = await send_document(bot_token, chat_id, file_paths[0], caption)
        return [result]

    url = f"https://api.telegram.org/bot{bot_token}/sendMediaGroup"

    # Prepare media array and files
    media = []
    files = {}

    for i, file_path in enumerate(file_paths):
        file_key = f"file_{i}"

        # Determine MIME type
        mime_type, _ = mimetypes.guess_type(str(file_path))
        if not mime_type:
            mime_type = "application/octet-stream"

        # Add to files dict
        files[file_key] = (file_path.name, file_path.read_bytes(), mime_type)

        # Create media object
        media_item = {"type": "document", "media": f"attach://{file_key}"}

        # Add caption to first item
        if i == 0 and caption:
            media_item["caption"] = caption

        media.append(media_item)

    data = {"chat_id": chat_id, "media": json.dumps(media)}

    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            response = await client.post(url, files=files, data=data)
            response.raise_for_status()
            result = response.json()

            if not result.get("ok"):
                raise TelegramError(
                    f"Telegram API error: {result.get('description', 'Unknown error')}"
                )

            logger.info(
                f"Sent media group with {len(file_paths)} files to Telegram chat {chat_id}"
            )
            return result["result"]

        except httpx.HTTPStatusError as e:
            logger.error(
                f"HTTP error sending media group to Telegram: {e.response.status_code} - {e.response.text}"
            )
            raise TelegramError(f"HTTP {e.response.status_code}: {e.response.text}")
        except Exception as e:
            logger.error(f"Error sending media group to Telegram: {e}")
            raise TelegramError(str(e))


def send_to_telegram(
    files: List[Path],
    bot_token: str,
    chat_id: str,
    caption: Optional[str] = None,
    as_media_group: bool = True,
) -> Dict[str, Any]:
    """
    Send files to Telegram chat.

    Returns:
        Dict with 'sent' (bool) and 'message_ids' (list) or 'error' (str)
    """
    if not files:
        return {"sent": False, "error": "No files to send"}

    if not bot_token or not chat_id:
        return {"sent": False, "error": "Missing bot_token or chat_id"}

    try:
        # Run async function
        if as_media_group and len(files) > 1:
            messages = asyncio.run(send_media_group(bot_token, chat_id, files, caption))
        else:
            # Send individual documents
            messages = []
            for file_path in files:
                message = asyncio.run(
                    send_document(
                        bot_token,
                        chat_id,
                        file_path,
                        caption if len(files) == 1 else None,
                    )
                )
                messages.append(message)

        message_ids = [msg["message_id"] for msg in messages]

        return {"sent": True, "message_ids": message_ids, "files_sent": len(files)}

    except TelegramError as e:
        logger.error(f"Telegram error: {e}")
        return {"sent": False, "error": str(e)}
    except Exception as e:
        logger.error(f"Unexpected error sending to Telegram: {e}")
        return {"sent": False, "error": f"Unexpected error: {e}"}
