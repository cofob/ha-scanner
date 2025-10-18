#!/usr/bin/env python3
"""Telegram bot for scanning documents using libinsane."""

import logging
import tempfile
from datetime import datetime
from pathlib import Path
from .config import load_config

import gi
from telegram import Update, InputMediaPhoto
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

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)


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
                    "name": dev.get_name(),
                    "type": dev.get_type(),
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
                device = devices[0]
                logger.info(f"Using first available device: {device.get_name()}")
            logger.info(f"Using device: {device.get_name()}")
            sources = device.get_children()
            if not sources:
                raise Exception("No scan sources found for this device")
            source = sources[0]
            logger.info(f"Using source: {source.get_name()}")
            session = source.scan_start()
            logger.info("Scanning started...")
            if session.end_of_feed():
                raise Exception("No document found in the scanner")
            temp_dir = Path(tempfile.mkdtemp())
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
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_file = temp_dir / f"scan_{timestamp}_page{page_num}.png"
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
            device_list += f"• {device['name']} (Type: {device['type']})\n"
        update.message.reply_text(device_list)
    except Exception as e:
        logger.error(f"Error listing devices: {e}")
        update.message.reply_text(f"Error listing devices: {str(e)}")


def scan_command(update: Update, context: CallbackContext) -> None:
    """Handle /scan command to scan a document."""
    if not is_authorized(update):
        update.message.reply_text(
            "Sorry, you are not authorized to use this bot."
        )
        return
    try:
        update.message.reply_text("Starting scan process... Please wait.")
        scanned_files = scanner_bot.scan_document()
        if not scanned_files:
            update.message.reply_text(
                "No pages were scanned. Please check if a document is loaded in the scanner."
            )
            return
        if len(scanned_files) == 1:
            with open(scanned_files[0], "rb") as photo:
                update.message.reply_photo(
                    photo=photo, caption="Here's your scanned document!"
                )
        else:
            media_group = []
            for i, file_path in enumerate(scanned_files):
                file_bytes = file_path.read_bytes()
                media_group.append(
                    InputMediaPhoto(
                        media=file_bytes,
                        caption=f"Scanned document - Page {i + 1}" if i == 0 else None,
                    )
                )
            context.bot.send_media_group(
                chat_id=update.effective_chat.id, media=media_group
            )
        update.message.reply_text(
            f"Scan complete! Sent {len(scanned_files)} page(s)."
        )
        for file_path in scanned_files:
            try:
                file_path.unlink()
            except Exception as e:
                logger.warning(f"Failed to delete temporary file {file_path}: {e}")
    except Exception as e:
        logger.error(f"Error during scan: {e}")
        update.message.reply_text(
            f"Error during scanning: {str(e)}\n\nPlease check:\n• Scanner is connected and powered on\n• Document is properly loaded\n• Scanner drivers are installed"
        )


def handle_text(update: Update, context: CallbackContext) -> None:
    """Handle text messages."""
    if not is_authorized(update):
        return
    update.message.reply_text(
        "Please use commands to interact with the bot. Type /help for available commands."
    )


def main() -> None:
    """Run the bot."""
    if not config.telegram.bot_token:
        logger.error(
            "No bot token configured. Please edit the script and set TELEGRAM_BOT_TOKEN."
        )
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
    dispatcher.add_handler(MessageHandler(filters.Filters.text, handle_text))
    logger.info("Starting Telegram bot...")
    updater.start_polling()
    updater.idle()


if __name__ == "__main__":
    main()
