#!/usr/bin/env python3
"""Telegram bot for scanning documents using libinsane."""

import logging
import tempfile
from datetime import datetime
from pathlib import Path

import gi
from telegram import Update, InputMediaPhoto
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# Import configuration
from app.config import load_config

# Setup GObject introspection for libinsane
gi.require_version("Libinsane", "1.0")
from gi.repository import Libinsane
from PIL import Image

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Load configuration
config = load_config()


class ScannerBot:
    """Telegram bot for document scanning using libinsane."""

    def __init__(self, token: str, allowed_chat_ids: list[str] = None):
        """Initialize the bot with token and allowed chat IDs."""
        self.token = token
        self.allowed_chat_ids = allowed_chat_ids or []
        self.application = None
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

        try:
            # Get device
            if device_id:
                device = self.api.get_device(device_id)
            else:
                devices = self.api.list_devices(Libinsane.DeviceLocations.ANY)
                if not devices:
                    raise Exception("No scanner devices found")
                device = devices[0]
                logger.info(f"Using first available device: {device.get_name()}")

            logger.info(f"Using device: {device.get_name()}")

            # Get first available scan source
            sources = device.get_children()
            if not sources:
                raise Exception("No scan sources found for this device")

            source = sources[0]
            logger.info(f"Using source: {source.get_name()}")

            # Start scanning
            session = source.scan_start()
            logger.info("Scanning started...")

            if session.end_of_feed():
                raise Exception("No document found in the scanner")

            # Create temporary directory for scans
            temp_dir = Path(tempfile.mkdtemp())
            saved_files = []
            page_num = 0

            while not session.end_of_feed():
                scan_params = session.get_scan_parameters()
                img_data = b""

                # Read image data
                while True:
                    try:
                        chunk = session.read_bytes(128 * 1024)
                        if not chunk:
                            break
                        img_data += chunk.get_data()
                    except Exception:
                        break  # End of page

                if not img_data:
                    continue

                # Process image based on format
                width = scan_params.get_width()
                height = int(len(img_data) / (width * 3))  # Assuming 24-bit RGB

                if scan_params.get_format() == Libinsane.ImgFormat.RAW_RGB_24:
                    image = Image.frombytes("RGB", (width, height), img_data)
                else:
                    logger.warning(
                        f"Unsupported image format: {scan_params.get_format()}"
                    )
                    continue

                # Save as PNG
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_file = temp_dir / f"scan_{timestamp}_page{page_num}.png"
                image.save(output_file, format="PNG")
                saved_files.append(output_file)
                logger.info(f"Saved page {page_num} to '{output_file}'")

                page_num += 1

            session.cancel()
            return saved_files

        except Exception as e:
            logger.error(f"Error during scanning: {e}")
            raise
        finally:
            if "session" in locals() and session:
                session.cancel()

    def is_chat_allowed(self, chat_id: str) -> bool:
        """Check if a chat ID is allowed to use the bot."""
        if not self.allowed_chat_ids:
            return True  # Allow all if no restrictions set
        return str(chat_id) in self.allowed_chat_ids


# Global bot instance
scanner_bot = ScannerBot(
    config.telegram.bot_token,
    [config.telegram.chat_id] if config.telegram.chat_id else [],
)


def is_authorized(update: Update) -> bool:
    """Check if the user is authorized to use the bot."""
    chat_id = str(update.effective_chat.id)
    return scanner_bot.is_chat_allowed(chat_id)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command."""
    if not is_authorized(update):
        await update.message.reply_text(
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
    await update.message.reply_text(welcome_message)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /help command."""
    if not is_authorized(update):
        await update.message.reply_text(
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
    await update.message.reply_text(help_text)


async def devices_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /devices command to list available scanners."""
    if not is_authorized(update):
        await update.message.reply_text(
            "Sorry, you are not authorized to use this bot."
        )
        return

    try:
        devices = scanner_bot.list_scanner_devices()
        if not devices:
            await update.message.reply_text(
                "No scanner devices found. Please check your scanner connection."
            )
            return

        device_list = "Available scanner devices:\n\n"
        for device in devices:
            device_list += f"• {device['name']} (Type: {device['type']})\n"

        await update.message.reply_text(device_list)
    except Exception as e:
        logger.error(f"Error listing devices: {e}")
        await update.message.reply_text(f"Error listing devices: {str(e)}")


async def scan_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /scan command to scan a document."""
    if not is_authorized(update):
        await update.message.reply_text(
            "Sorry, you are not authorized to use this bot."
        )
        return

    try:
        await update.message.reply_text("Starting scan process... Please wait.")

        # Scan document
        scanned_files = scanner_bot.scan_document()

        if not scanned_files:
            await update.message.reply_text(
                "No pages were scanned. Please check if a document is loaded in the scanner."
            )
            return

        # Send scanned images
        if len(scanned_files) == 1:
            # Single page - send as photo
            with open(scanned_files[0], "rb") as photo:
                await update.message.reply_photo(
                    photo=photo, caption="Here's your scanned document!"
                )
        else:
            # Multiple pages - send as media group
            media_group = []
            for i, file_path in enumerate(scanned_files):
                with open(file_path, "rb") as photo:
                    media_group.append(
                        InputMediaPhoto(
                            photo,
                            caption=f"Scanned document - Page {i + 1}"
                            if i == 0
                            else f"Page {i + 1}",
                        )
                    )

            await update.message.reply_media_group(media_group)

        await update.message.reply_text(
            f"Scan complete! Sent {len(scanned_files)} page(s)."
        )

        # Cleanup temporary files
        for file_path in scanned_files:
            try:
                file_path.unlink()
            except Exception as e:
                logger.warning(f"Failed to delete temporary file {file_path}: {e}")

    except Exception as e:
        logger.error(f"Error during scan: {e}")
        await update.message.reply_text(
            f"Error during scanning: {str(e)}\n\nPlease check:\n• Scanner is connected and powered on\n• Document is properly loaded\n• Scanner drivers are installed"
        )


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle text messages."""
    if not is_authorized(update):
        return  # Ignore messages from unauthorized users

    await update.message.reply_text(
        "Please use commands to interact with the bot. Type /help for available commands."
    )


def main() -> None:
    """Run the bot."""
    if not config.telegram.bot_token:
        logger.error(
            "No bot token configured. Please set TELEGRAM_BOT_TOKEN in your configuration."
        )
        return

    # Initialize libinsane
    try:
        scanner_bot.initialize_libinsane()
    except Exception as e:
        logger.error(f"Failed to initialize scanner: {e}")
        return

    # Create application
    application = Application.builder().token(config.telegram.bot_token).build()
    scanner_bot.application = application

    # Add handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("devices", devices_command))
    application.add_handler(CommandHandler("scan", scan_command))

    # Add text message handler (for non-command messages)
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text)
    )

    # Start the bot
    logger.info("Starting Telegram bot...")
    application.run_polling()


if __name__ == "__main__":
    main()
