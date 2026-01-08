#!/usr/bin/env python3
"""Telegram bot for scanning documents using libinsane."""

import json
import logging
import os
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from .config import load_config

import gi
import httpx
try:
    import cups
except ImportError:  # pragma: no cover - guarded for environments without CUPS
    cups = None
from telegram import Update, InputMediaPhoto, Bot
from telegram.ext import (
    Updater,
    CommandHandler,
    CallbackContext,  # <<< FIX: Import CallbackContext for v13.x type hinting
    MessageHandler,
    filters,
)


config = load_config()


# Setup GObject introspection for libinsane
gi.require_version("Libinsane", "1.0")
from gi.repository import Libinsane
from PIL import Image
import socket

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)


HA_BASE_URL = "http://supervisor/core"


class HomeAssistantClient:
    """Small helper for Home Assistant Core API calls via Supervisor proxy."""

    def __init__(self, token: Optional[str]) -> None:
        self._enabled = bool(token)
        self._client = None
        if self._enabled:
            self._client = httpx.Client(
                base_url=HA_BASE_URL,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                timeout=10.0,
            )

    @property
    def enabled(self) -> bool:
        return self._enabled

    def _post(self, path: str, payload: dict) -> None:
        if not self._client:
            return
        try:
            response = self._client.post(path, json=payload)
            response.raise_for_status()
        except Exception as exc:
            logger.warning("Home Assistant API call failed (%s): %s", path, exc)

    def call_service(self, domain: str, service: str, data: Optional[dict] = None) -> None:
        self._post(f"/api/services/{domain}/{service}", data or {})

    def fire_event(self, event_type: str, event_data: Optional[dict] = None) -> None:
        self._post(f"/api/events/{event_type}", event_data or {})

    def system_log(self, message: str, level: str = "info") -> None:
        self.call_service("system_log", "write", {"message": message, "level": level})


ha_client = HomeAssistantClient(os.environ.get("SUPERVISOR_TOKEN"))


PDF_QUEUE_WINDOW = timedelta(minutes=30)
RESOLUTION_OVERRIDE_WINDOW = timedelta(minutes=30)
RESOLUTION_PRESETS = {
    "low": 150,
    "medium": 300,
    "high": 600,
    "xhigh": 1200,
}


@dataclass
class QueuedImage:
    path: Path
    scanned_at: datetime
    chat_id: Optional[int]
    message_id: Optional[int]


class ScannerBot:
    """Telegram bot for document scanning using libinsane."""

    def __init__(self, token: str, allowed_chat_ids: list[str] = None):
        """Initialize the bot with token and allowed chat IDs."""
        self.token = token
        self.allowed_chat_ids = allowed_chat_ids or []
        self.api = None

    def initialize_libinsane(self):
        """Initialize libinsane API."""
        try:
            self.api = Libinsane.Api.new_safebet()
            logger.info("libinsane API initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize libinsane API: {e}")
            raise

    def list_scanner_devices(self):
        """List available scanner devices."""
        if not self.api:
            self.initialize_libinsane()
        try:
            devices = self.api.list_devices(Libinsane.DeviceLocations.ANY)
            if not devices:
                logger.warning("No scanner devices found")
                return []
            logger.info(f"Found {len(devices)} scanner device(s)")
            device_list = []
            for i, dev in enumerate(devices):
                device_info = {
                    "index": i,
                    "id": dev.get_dev_id(),
                    "name": dev.get_dev_model(),
                    "type": dev.get_dev_type(),
                }
                device_list.append(device_info)
                logger.info(
                    f"Device [{i}]: ID='{device_info['id']}', Name='{device_info['name']}', Type='{device_info['type']}'"
                )
            return device_list
        except Exception as e:
            logger.error(f"Error listing devices: {e}")
            return []

    def scan_document(self, device_id: str = None) -> list[Path]:
        """Scan document and return list of saved image paths."""
        if not self.api:
            self.initialize_libinsane()
        session = None
        try:
            if device_id:
                device = self.api.get_device(device_id)
            else:
                devices = self.api.list_devices(Libinsane.DeviceLocations.ANY)
                if not devices:
                    raise Exception("No scanner devices found")
                device = self.api.get_device(devices[0].get_dev_id())
                logger.info(f"Using first available device: {device.get_name()}")
            logger.info(f"Using device: {device.get_name()}")
            sources = device.get_children()
            if not sources:
                raise Exception("No scan sources found for this device")
            source = sources[0]
            logger.info(f"Using source: {source.get_name()}")
            resolution_dpi, _, is_override = get_active_resolution()
            apply_resolution(source, resolution_dpi)
            logger.info(
                "Using scan resolution %s DPI%s",
                resolution_dpi,
                " (override)" if is_override else "",
            )
            session = source.scan_start()
            logger.info("Scanning started...")
            if session.end_of_feed():
                raise Exception("No document found in the scanner")
            output_dir = get_output_dir()
            output_dir.mkdir(parents=True, exist_ok=True)
            saved_files = []
            page_num = 0
            while not session.end_of_feed():
                scan_params = session.get_scan_parameters()
                img_data = b""
                while True:
                    try:
                        chunk_data = session.read_bytes(128 * 1024).get_data()
                        if not chunk_data:
                            break
                        img_data += chunk_data
                    except Exception:
                        break
                if not img_data:
                    continue
                width = scan_params.get_width()
                if width == 0:
                    logger.warning(
                        "Scan returned image with zero width. Skipping page."
                    )
                    continue
                bytes_per_pixel = 3
                height = int(len(img_data) / (width * bytes_per_pixel))
                if height == 0:
                    logger.warning(
                        "Scan returned image with zero height. Skipping page."
                    )
                    continue
                if scan_params.get_format() == Libinsane.ImgFormat.RAW_RGB_24:
                    image = Image.frombytes("RGB", (width, height), img_data)
                else:
                    logger.warning(
                        f"Unsupported image format: {scan_params.get_format()}"
                    )
                    continue
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                output_file = output_dir / f"scan_{timestamp}_page{page_num}.png"
                image.save(output_file, format="PNG")
                saved_files.append(output_file)
                logger.info(f"Saved page {page_num} to '{output_file}'")
                page_num += 1
            return saved_files
        except Exception as e:
            logger.error(f"Error during scanning: {e}")
            raise
        finally:
            if session:
                session.cancel()

    def is_chat_allowed(self, chat_id: str) -> bool:
        """Check if a chat ID is allowed to use the bot."""
        if not self.allowed_chat_ids:
            return True
        return str(chat_id) in self.allowed_chat_ids


scanner_bot = ScannerBot(
    config.telegram.bot_token,
    [config.telegram.chat_id] if config.telegram.chat_id else [],
)
scan_lock = threading.Lock()
telegram_sender = Bot(config.telegram.bot_token) if config.telegram.bot_token else None
pdf_queue: list[QueuedImage] = []
pdf_queue_lock = threading.Lock()
resolution_override_lock = threading.Lock()
resolution_override_dpi: Optional[int] = None
resolution_override_expires_at: Optional[datetime] = None


def log_ha_event(message: str, level: str = "info") -> None:
    """Write a message into Home Assistant's system log when available."""
    if ha_client.enabled:
        ha_client.system_log(message, level=level)


def parse_chat_id(chat_id: str) -> Optional[int]:
    if not chat_id:
        return None
    try:
        return int(chat_id)
    except ValueError:
        return None


def get_output_dir() -> Path:
    base = "/media" if config.save_to == "media" else "/share"
    subdir = config.subdir.strip().strip("/")
    return Path(base) / subdir


def list_discovered_destinations() -> list:
    found = []

    def on_dest(_user_data, _flags, dest) -> int:
        found.append(dest)
        return 1

    cups.enumDests(on_dest)
    return found


def resolve_printer_name(conn) -> str:
    preferred = (config.printer_name or "").strip()
    printers = conn.getPrinters() if conn else {}
    if preferred:
        if preferred in printers:
            return preferred
        for dest in list_discovered_destinations():
            if getattr(dest, "name", None) == preferred:
                return preferred
        raise ValueError(f"Printer '{preferred}' not found.")

    default_printer = None
    try:
        default_printer = conn.getDefault()
    except Exception:
        default_printer = None

    if default_printer:
        return default_printer
    for name, attrs in printers.items():
        if attrs.get("printer-is-default"):
            return name
    if printers:
        return sorted(printers.keys())[0]

    destinations = list_discovered_destinations()
    for dest in destinations:
        if getattr(dest, "is_default", False):
            return dest.name
    if destinations:
        return destinations[0].name
    raise ValueError("No printers discovered by CUPS.")


def resolve_resolution_level(level: str) -> Optional[int]:
    if not level:
        return None
    return RESOLUTION_PRESETS.get(level.strip().lower())


def set_resolution_override(dpi: int, source: str) -> datetime:
    expires_at = datetime.now() + RESOLUTION_OVERRIDE_WINDOW
    with resolution_override_lock:
        global resolution_override_dpi
        global resolution_override_expires_at
        resolution_override_dpi = dpi
        resolution_override_expires_at = expires_at
    log_ha_event(
        f"Resolution override set to {dpi} DPI by {source} (expires {expires_at.isoformat(timespec='seconds')})",
        level="info",
    )
    if ha_client.enabled:
        ha_client.fire_event(
            "scanner_resolution_override",
            {
                "dpi": dpi,
                "expires_at": expires_at.isoformat(timespec="seconds"),
                "source": source,
            },
        )
    return expires_at


def get_active_resolution() -> tuple[int, Optional[datetime], bool]:
    global resolution_override_dpi
    global resolution_override_expires_at
    now = datetime.now()
    with resolution_override_lock:
        if resolution_override_dpi and resolution_override_expires_at:
            if resolution_override_expires_at > now:
                return resolution_override_dpi, resolution_override_expires_at, True
            resolution_override_dpi = None
            resolution_override_expires_at = None
    return config.resolution, None, False


def apply_resolution(source, dpi: int) -> None:
    option_names = ("resolution", "x-resolution", "y-resolution", "scan-resolution")
    for option in option_names:
        try:
            source.set_option(option, dpi)
            logger.info("Set scan resolution to %s DPI via %s", dpi, option)
            return
        except Exception:
            continue
    logger.warning("Unable to set scan resolution to %s DPI", dpi)


def queue_scanned_files(
    scanned_files: list[Path],
    chat_id: Optional[int],
    message_ids: Optional[list[int]] = None,
) -> None:
    if not scanned_files:
        return
    scanned_at = datetime.now()
    with pdf_queue_lock:
        cutoff = scanned_at - PDF_QUEUE_WINDOW
        pdf_queue[:] = [item for item in pdf_queue if item.scanned_at >= cutoff]
        for index, path in enumerate(scanned_files):
            message_id = None
            if message_ids and index < len(message_ids):
                message_id = message_ids[index]
            pdf_queue.append(
                QueuedImage(
                    path=path,
                    scanned_at=scanned_at,
                    chat_id=chat_id,
                    message_id=message_id,
                )
            )


def get_recent_queue_items(chat_id: Optional[int]) -> list[QueuedImage]:
    cutoff = datetime.now() - PDF_QUEUE_WINDOW
    with pdf_queue_lock:
        pdf_queue[:] = [item for item in pdf_queue if item.scanned_at >= cutoff]
        items = [
            item
            for item in pdf_queue
            if chat_id is None or item.chat_id == chat_id
        ]
    return items


def remove_queue_items(items: list[QueuedImage]) -> None:
    if not items:
        return
    item_ids = {id(item) for item in items}
    with pdf_queue_lock:
        pdf_queue[:] = [item for item in pdf_queue if id(item) not in item_ids]


def remove_queue_item_by_message(
    chat_id: int, message_id: int
) -> Optional[QueuedImage]:
    with pdf_queue_lock:
        for index, item in enumerate(pdf_queue):
            if item.chat_id == chat_id and item.message_id == message_id:
                return pdf_queue.pop(index)
    return None


def images_to_pdf(image_paths: list[Path], output_pdf: Path) -> int:
    if not image_paths:
        raise ValueError("No images provided.")
    images = []
    for path in image_paths:
        if not path.exists():
            logger.warning("Skipping missing image for PDF: %s", path)
            continue
        img = Image.open(path)
        if img.mode in ("RGBA", "P") or img.mode != "RGB":
            img = img.convert("RGB")
        images.append(img)
    if not images:
        raise ValueError("No valid images available for PDF.")
    first_image, remaining_images = images[0], images[1:]
    output_pdf.parent.mkdir(parents=True, exist_ok=True)
    first_image.save(
        output_pdf,
        save_all=True,
        append_images=remaining_images,
    )
    return len(images)


def build_pdf_from_queue(chat_id: Optional[int]) -> tuple[Optional[Path], int]:
    items = get_recent_queue_items(chat_id)
    if not items:
        return None, 0
    items.sort(key=lambda item: (item.scanned_at, item.path.name))
    output_dir = get_output_dir()
    pdf_name = datetime.now().strftime("scan_%Y%m%d_%H%M%S.pdf")
    output_path = output_dir / pdf_name
    image_paths = [item.path for item in items]
    page_count = images_to_pdf(image_paths, output_path)
    remove_queue_items(items)
    return output_path, page_count


def send_scanned_files(
    bot: Bot, chat_id: int, scanned_files: list[Path], caption_prefix: str
) -> list[int]:
    if not scanned_files:
        return []
    if len(scanned_files) == 1:
        with open(scanned_files[0], "rb") as photo:
            message = bot.send_photo(
                photo=photo,
                chat_id=chat_id,
                caption=caption_prefix,
            )
        return [message.message_id]
    media_group = []
    for i, file_path in enumerate(scanned_files):
        file_bytes = file_path.read_bytes()
        media_group.append(
            InputMediaPhoto(
                media=file_bytes,
                caption=f"{caption_prefix} - Page {i + 1}" if i == 0 else None,
            )
        )
    messages = bot.send_media_group(chat_id=chat_id, media=media_group)
    return [message.message_id for message in messages]


def perform_scan(device_id: Optional[str] = None) -> list[Path]:
    with scan_lock:
        return scanner_bot.scan_document(device_id=device_id)


def is_authorized(update: Update) -> bool:
    """Check if the user is authorized to use the bot."""
    chat_id = str(update.effective_chat.id)
    return scanner_bot.is_chat_allowed(chat_id)


def start_command(update: Update, context: CallbackContext) -> None:
    """Handle /start command."""
    if not is_authorized(update):
        update.message.reply_text(
            "Sorry, you are not authorized to use this bot."
        )
        return
    welcome_message = (
        "Welcome to the Document Scanner Bot! 📄\n\n"
        "Available commands:\n"
        "/scan - Scan a document using the connected scanner\n"
        "/devices - List available scanner devices\n"
        "/pdf - Combine recent scans into a single PDF\n"
        "/delete - Reply to a scan to delete it and remove from the PDF queue\n"
        "/print - Print an attached image (black and white)\n"
        "/print_color - Print an attached image (color)\n"
        "/res <low|medium|high|xhigh> - Set DPI for 30 minutes\n"
        "/help - Show this help message\n\n"
        "Simply place a document in your scanner and use /scan to start scanning."
    )
    update.message.reply_text(welcome_message)


def help_command(update: Update, context: CallbackContext) -> None:
    """Handle /help command."""
    if not is_authorized(update):
        update.message.reply_text(
            "Sorry, you are not authorized to use this bot."
        )
        return
    help_text = (
        "Document Scanner Bot Help:\n\n"
        "• /scan - Scan a document from the connected scanner\n"
        "• /devices - List available scanner devices\n"
        "• /pdf - Combine scans from the last 30 minutes into a PDF\n"
        "• /delete - Reply to a scan to delete it and remove from the PDF queue\n"
        "• /print - Print an attached image (black and white)\n"
        "• /print_color - Print an attached image (color)\n"
        "• /res <low|medium|high|xhigh> - Set DPI for 30 minutes\n"
        "• /help - Show this help message\n\n"
        "To scan a document:\n"
        "1. Place your document in the scanner\n"
        "2. Use the /scan command\n"
        "3. The bot will scan and send the document back to you"
    )
    update.message.reply_text(help_text)


def devices_command(update: Update, context: CallbackContext) -> None:
    """Handle /devices command to list available scanners."""
    if not is_authorized(update):
        update.message.reply_text(
            "Sorry, you are not authorized to use this bot."
        )
        return
    try:
        devices = scanner_bot.list_scanner_devices()
        if not devices:
            update.message.reply_text(
                "No scanner devices found. Please check your scanner connection."
            )
            return
        device_list = "Available scanner devices:\n\n"
        for device in devices:
            device_list += (
                f"• {device['name']} (Type: {device['type']}, ID: {device['id']})\n"
            )
        update.message.reply_text(device_list)
    except Exception as e:
        logger.error(f"Error listing devices: {e}")
        update.message.reply_text(f"Error listing devices: {str(e)}")


def res_command(update: Update, context: CallbackContext) -> None:
    """Handle /res command to set temporary scan resolution."""
    if not is_authorized(update):
        update.message.reply_text(
            "Sorry, you are not authorized to use this bot."
        )
        return
    if not context.args:
        current_dpi, expires_at, is_override = get_active_resolution()
        if is_override and expires_at:
            update.message.reply_text(
                f"Current DPI override: {current_dpi} (expires {expires_at.strftime('%H:%M')})."
            )
        else:
            update.message.reply_text(
                f"Current DPI: {current_dpi}. Use /res <low|medium|high|xhigh> to set for 30 minutes."
            )
        return
    level = context.args[0].lower()
    dpi = resolve_resolution_level(level)
    if not dpi:
        update.message.reply_text(
            "Invalid resolution. Use /res <low|medium|high|xhigh>."
        )
        return
    username = update.effective_user.username or update.effective_user.full_name or "unknown"
    expires_at = set_resolution_override(dpi, f"telegram:{username}")
    update.message.reply_text(
        f"Resolution set to {dpi} DPI for 30 minutes (expires {expires_at.strftime('%H:%M')})."
    )


def scan_command(update: Update, context: CallbackContext) -> None:
    """Handle /scan command to scan a document."""
    if not is_authorized(update):
        update.message.reply_text(
            "Sorry, you are not authorized to use this bot."
        )
        return
    username = update.effective_user.username or update.effective_user.full_name or "unknown"
    chat_id = update.effective_chat.id
    log_ha_event(
        f"Telegram scan requested by {username} (chat_id={chat_id})",
        level="info",
    )
    try:
        update.message.reply_text("Starting scan process... Please wait.")
        scanned_files = perform_scan()
        if not scanned_files:
            update.message.reply_text(
                "No pages were scanned. Please check if a document is loaded in the scanner."
            )
            return
        message_ids = send_scanned_files(
            context.bot,
            chat_id,
            scanned_files,
            "Here's your scanned document!",
        )
        queue_scanned_files(scanned_files, chat_id, message_ids)
        update.message.reply_text(
            f"Scan complete! Sent {len(scanned_files)} page(s)."
        )
        log_ha_event(
            f"Telegram scan completed for {username} (chat_id={chat_id}), pages={len(scanned_files)}",
            level="info",
        )
    except Exception as e:
        logger.error(f"Error during scan: {e}")
        log_ha_event(
            f"Telegram scan failed for {username} (chat_id={chat_id}): {e}",
            level="error",
        )
        update.message.reply_text(
            f"Error during scanning: {str(e)}\n\nPlease check:\n• Scanner is connected and powered on\n• Document is properly loaded\n• Scanner drivers are installed"
        )


def pdf_command(update: Update, context: CallbackContext) -> None:
    """Handle /pdf command to combine recent scans into a single PDF."""
    if not is_authorized(update):
        update.message.reply_text(
            "Sorry, you are not authorized to use this bot."
        )
        return
    chat_id = update.effective_chat.id
    try:
        update.message.reply_text("Preparing PDF from recent scans...")
        pdf_path, page_count = build_pdf_from_queue(chat_id)
        if not pdf_path:
            update.message.reply_text(
                "No scans found in the last 30 minutes."
            )
            return
        with open(pdf_path, "rb") as pdf_file:
            context.bot.send_document(
                chat_id=chat_id,
                document=pdf_file,
                caption=f"PDF ready ({page_count} page(s)).",
            )
        update.message.reply_text(
            f"PDF saved to {pdf_path}."
        )
    except Exception as exc:
        logger.error("PDF generation failed: %s", exc)
        update.message.reply_text(
            f"Failed to generate PDF: {exc}"
        )


def delete_command(update: Update, context: CallbackContext) -> None:
    """Handle /delete command to remove a scan from chat and PDF queue."""
    if not is_authorized(update):
        update.message.reply_text(
            "Sorry, you are not authorized to use this bot."
        )
        return
    if not update.message.reply_to_message:
        update.message.reply_text(
            "Reply to the scan you want to delete."
        )
        return
    chat_id = update.effective_chat.id
    reply_message = update.message.reply_to_message
    message_id = reply_message.message_id
    removed_item = remove_queue_item_by_message(chat_id, message_id)
    file_deleted = False
    if removed_item and removed_item.path.exists():
        try:
            removed_item.path.unlink()
            file_deleted = True
        except Exception as exc:
            logger.warning("Failed to delete scan file %s: %s", removed_item.path, exc)
    try:
        context.bot.delete_message(chat_id=chat_id, message_id=message_id)
    except Exception as exc:
        logger.warning("Failed to delete Telegram message %s: %s", message_id, exc)
    if removed_item:
        update.message.reply_text(
            "Scan removed from the PDF queue."
            + (" File deleted." if file_deleted else "")
        )
    else:
        update.message.reply_text(
            "Scan message removed from chat. It was not in the PDF queue."
        )


def handle_text(update: Update, context: CallbackContext) -> None:
    """Handle text messages."""
    if not is_authorized(update):
        return
    update.message.reply_text(
        "Please use commands to interact with the bot. Type /help for available commands."
    )


def is_image_document(document) -> bool:
    return bool(
        document and document.mime_type and document.mime_type.startswith("image/")
    )


def is_pdf_document(document) -> bool:
    return bool(
        document and document.mime_type and document.mime_type == "application/pdf"
    )


def download_telegram_image(
    update: Update, context: CallbackContext
) -> Optional[Path]:
    message = update.message
    source = message
    if not (message.photo or is_image_document(message.document) or is_pdf_document(message.document)):
        if message.reply_to_message:
            source = message.reply_to_message
    file_id = None
    filename = None
    if source.photo:
        file_id = source.photo[-1].file_id
        filename = f"telegram_{source.message_id}.jpg"
    elif is_image_document(source.document) or is_pdf_document(source.document):
        file_id = source.document.file_id
        filename = source.document.file_name or f"telegram_{source.message_id}"
    else:
        return None
    output_dir = get_output_dir()
    output_dir.mkdir(parents=True, exist_ok=True)
    suffix = Path(filename).suffix or ".jpg"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    output_path = output_dir / f"print_{timestamp}{suffix}"
    file_obj = context.bot.get_file(file_id)
    file_obj.download(custom_path=str(output_path))
    return output_path


def print_image_file(path: Path, monochrome: bool) -> tuple[str, int]:
    if cups is None:
        raise RuntimeError("CUPS Python bindings are not available.")
    conn = cups.Connection()
    printer_name = resolve_printer_name(conn)
    options = {
        "media": "A4",
        "fit-to-page": "true",
        "orientation-requested": "3",
        "print-color-mode": "monochrome" if monochrome else "color",
    }
    job_id = conn.printFile(
        printer_name,
        str(path),
        f"Telegram print {path.name}",
        options,
    )
    return printer_name, job_id


def handle_print_command(
    update: Update, context: CallbackContext, monochrome: bool
) -> None:
    if not is_authorized(update):
        update.message.reply_text(
            "Sorry, you are not authorized to use this bot."
        )
        return
    if cups is None:
        update.message.reply_text("Printing is not available in this add-on build.")
        return
    image_path = download_telegram_image(update, context)
    if not image_path:
        update.message.reply_text(
            "Send /print as a caption to an image or reply to an image with /print."
        )
        return
    username = update.effective_user.username or update.effective_user.full_name or "unknown"
    chat_id = update.effective_chat.id
    try:
        printer_name, job_id = print_image_file(image_path, monochrome=monochrome)
        update.message.reply_text(
            f"Print job sent to {printer_name} (job {job_id})."
        )
        log_ha_event(
            f"Telegram print sent by {username} (chat_id={chat_id}) to {printer_name}, job={job_id}",
            level="info",
        )
    except Exception as exc:
        logger.error("Telegram print failed: %s", exc)
        log_ha_event(
            f"Telegram print failed for {username} (chat_id={chat_id}): {exc}",
            level="error",
        )
        update.message.reply_text(f"Failed to print image: {exc}")


def print_bw_command(update: Update, context: CallbackContext) -> None:
    handle_print_command(update, context, monochrome=True)


def print_color_command(update: Update, context: CallbackContext) -> None:
    handle_print_command(update, context, monochrome=False)


def handle_stdin_scan(command: dict) -> None:
    device_id = command.get("device_id")
    notify_telegram = bool(command.get("notify_telegram", False))
    chat_id = parse_chat_id(config.telegram.chat_id)
    log_ha_event(
        f"STDIN scan requested (device_id={device_id or 'default'})",
        level="info",
    )
    scanned_files: list[Path] = []
    try:
        scanned_files = perform_scan(device_id=device_id)
        if not scanned_files:
            log_ha_event("STDIN scan completed with no pages.", level="warning")
            ha_client.fire_event("scanner_scan_completed", {"pages": 0})
            return
        message_ids: list[int] = []
        if notify_telegram and telegram_sender and chat_id:
            message_ids = send_scanned_files(
                telegram_sender,
                chat_id,
                scanned_files,
                "Scan from Home Assistant",
            )
        queue_scanned_files(scanned_files, chat_id, message_ids or None)
        ha_client.fire_event("scanner_scan_completed", {"pages": len(scanned_files)})
        log_ha_event(
            f"STDIN scan completed, pages={len(scanned_files)}",
            level="info",
        )
    except Exception as exc:
        logger.error("STDIN scan failed: %s", exc)
        log_ha_event(f"STDIN scan failed: {exc}", level="error")
        ha_client.fire_event("scanner_scan_failed", {"error": str(exc)})


def handle_stdin_pdf(command: dict) -> None:
    chat_id = parse_chat_id(config.telegram.chat_id)
    log_ha_event("STDIN PDF requested", level="info")
    try:
        pdf_path, page_count = build_pdf_from_queue(chat_id)
        if not pdf_path:
            log_ha_event("STDIN PDF completed with no recent scans.", level="warning")
            ha_client.fire_event("scanner_pdf_completed", {"pages": 0})
            return
        if telegram_sender and chat_id:
            with open(pdf_path, "rb") as pdf_file:
                telegram_sender.send_document(
                    chat_id=chat_id,
                    document=pdf_file,
                    caption=f"PDF ready ({page_count} page(s)).",
                )
        ha_client.fire_event("scanner_pdf_completed", {"pages": page_count})
        log_ha_event(
            f"STDIN PDF completed, pages={page_count}",
            level="info",
        )
    except Exception as exc:
        logger.error("STDIN PDF failed: %s", exc)
        log_ha_event(f"STDIN PDF failed: {exc}", level="error")
        ha_client.fire_event("scanner_pdf_failed", {"error": str(exc)})


def handle_stdin_resolution(command: dict) -> None:
    level = command.get("level")
    dpi_value = command.get("dpi")
    dpi = resolve_resolution_level(level) if level else None
    if dpi is None and dpi_value is not None:
        try:
            dpi = int(dpi_value)
        except (TypeError, ValueError):
            dpi = None
    if not dpi:
        log_ha_event(
            f"STDIN resolution override failed: {command}",
            level="warning",
        )
        return
    expires_at = set_resolution_override(dpi, "stdin")
    log_ha_event(
        f"STDIN resolution set to {dpi} DPI (expires {expires_at.isoformat(timespec='seconds')})",
        level="info",
    )


def handle_stdin_line(line: str) -> None:
    line = line.strip()
    if not line:
        return
    try:
        payload = json.loads(line)
    except json.JSONDecodeError:
        logger.warning("Invalid STDIN payload: %s", line)
        log_ha_event(f"Invalid STDIN payload: {line}", level="warning")
        return
    if isinstance(payload, dict) and "input" in payload:
        payload = payload["input"]
    if isinstance(payload, str):
        stripped = payload.strip()
        if stripped.startswith("{") or stripped.startswith("["):
            try:
                payload = json.loads(stripped)
            except json.JSONDecodeError:
                logger.warning("Invalid STDIN payload: %s", payload)
                log_ha_event(f"Invalid STDIN payload: {payload}", level="warning")
                return
        else:
            logger.warning("Invalid STDIN payload: %s", payload)
            log_ha_event(f"Invalid STDIN payload: {payload}", level="warning")
            return
    if not isinstance(payload, dict):
        logger.warning("Invalid STDIN payload: %s", payload)
        log_ha_event(f"Invalid STDIN payload: {payload}", level="warning")
        return
    command = payload.get("command")
    if command == "scan":
        handle_stdin_scan(payload)
        return
    if command == "pdf":
        handle_stdin_pdf(payload)
        return
    if command in ("resolution", "res"):
        handle_stdin_resolution(payload)
        return
    logger.warning("Unknown STDIN command: %s", payload)
    log_ha_event(f"Unknown STDIN command: {payload}", level="warning")


def stdin_socket_server() -> None:
    socket_path = Path("/tmp/ha_stdin.sock")
    if socket_path.exists():
        try:
            socket_path.unlink()
        except Exception as exc:
            logger.warning("Failed to remove existing stdin socket: %s", exc)
    server = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
    server.bind(str(socket_path))
    logger.info("STDIN socket server listening at %s", socket_path)
    while True:
        data, _ = server.recvfrom(65535)
        if not data:
            continue
        try:
            handle_stdin_line(data.decode("utf-8", errors="replace"))
        except Exception as exc:
            logger.warning("STDIN socket handling error: %s", exc)


def main() -> None:
    """Run the bot."""
    stdin_thread = threading.Thread(
        target=stdin_socket_server,
        name="stdin-socket",
        daemon=True,
    )
    stdin_thread.start()
    if not config.telegram.bot_token:
        logger.info("Telegram bot disabled; running in STDIN-only mode.")
        threading.Event().wait()
        return
    try:
        scanner_bot.initialize_libinsane()
    except Exception as e:
        logger.error(f"Failed to initialize scanner: {e}")
        return
    updater = Updater(config.telegram.bot_token, use_context=True)
    dispatcher = updater.dispatcher
    dispatcher.add_handler(CommandHandler("start", start_command))
    dispatcher.add_handler(CommandHandler("help", help_command))
    dispatcher.add_handler(CommandHandler("devices", devices_command))
    dispatcher.add_handler(CommandHandler("scan", scan_command))
    dispatcher.add_handler(CommandHandler("print", print_bw_command))
    dispatcher.add_handler(CommandHandler("print_color", print_color_command))
    dispatcher.add_handler(CommandHandler("res", res_command))
    dispatcher.add_handler(CommandHandler("pdf", pdf_command))
    dispatcher.add_handler(CommandHandler("delete", delete_command))
    dispatcher.add_handler(MessageHandler(filters.Filters.text, handle_text))
    logger.info("Starting Telegram bot...")
    updater.start_polling()
    updater.idle()


if __name__ == "__main__":
    main()
