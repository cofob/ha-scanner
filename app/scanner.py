"""Scanner core functionality using libinsane."""

import logging
from pathlib import Path
from typing import List, Dict, Optional

import gi

gi.require_version("Libinsane", "1.0")
from gi.repository import Libinsane
from PIL import Image

from .config import AppConfig, ScanOverrides
from .filename import format_filename, ensure_unique_filename


logger = logging.getLogger(__name__)


class ScannerDevice:
    """Represents a scanner device."""

    def __init__(self, device_id: str, name: str, vendor: str = "", model: str = ""):
        self.id = device_id
        self.name = name
        self.vendor = vendor
        self.model = model

    def to_dict(self) -> Dict[str, str]:
        return {
            "id": self.id,
            "name": self.name,
            "vendor": self.vendor,
            "model": self.model,
        }


class ScannerError(Exception):
    """Base exception for scanner operations."""

    pass


class DeviceNotFoundError(ScannerError):
    """Raised when a requested device is not found."""

    pass


class ScanError(ScannerError):
    """Raised when scanning fails."""

    pass


def initialize_api() -> Libinsane.Api:
    """Initialize libinsane API."""
    try:
        return Libinsane.Api.new_safebet()
    except Exception as e:
        raise ScannerError(f"Failed to initialize libinsane API: {e}")


def list_devices() -> List[ScannerDevice]:
    """List all available scanner devices."""
    api = initialize_api()

    try:
        devices = api.list_devices(Libinsane.DeviceLocations.ANY)
        result = []

        for dev in devices:
            device = ScannerDevice(
                device_id=dev.get_dev_id(),
                name=dev.get_name(),
                vendor=getattr(dev, "get_vendor", lambda: "")() or "",
                model=getattr(dev, "get_model", lambda: "")() or "",
            )
            result.append(device)
            logger.info(f"Found device: {device.name} ({device.id})")

        return result
    except Exception as e:
        logger.error(f"Failed to list devices: {e}")
        raise ScannerError(f"Failed to list devices: {e}")


def get_device(api: Libinsane.Api, device_id: Optional[str] = None):
    """Get a specific device or the first available one."""
    if device_id:
        try:
            return api.get_device(device_id)
        except Exception as e:
            raise DeviceNotFoundError(f"Device '{device_id}' not found: {e}")

    # Get first available device
    devices = api.list_devices(Libinsane.DeviceLocations.ANY)
    if not devices:
        raise DeviceNotFoundError("No scanner devices found")

    device = devices[0]
    logger.info(f"Using first available device: {device.get_name()}")
    return device


def get_scan_source(device):
    """Get the first available scan source from device."""
    sources = device.get_children()
    if not sources:
        # Use device itself if no sources
        return device
    return sources[0]


def configure_scan_options(source, resolution: int = 300):
    """Configure scan options like resolution."""
    try:
        opts = source.get_options()
        opts_dict = {opt.get_name(): opt for opt in opts}

        # Set resolution if supported
        if "resolution" in opts_dict:
            try:
                opts_dict["resolution"].set_value(resolution)
                logger.info(f"Set resolution to {resolution} DPI")
            except Exception as e:
                logger.warning(f"Failed to set resolution: {e}")

        # Log available options
        for opt in opts:
            try:
                logger.debug(
                    f"Option {opt.get_name()}: {opt.get_value()} (constraint: {opt.get_constraint()})"
                )
            except Exception:
                pass

    except Exception as e:
        logger.warning(f"Failed to configure scan options: {e}")


def raw_to_image(scan_params, img_data: bytes) -> Image.Image:
    """Convert raw scan data to PIL Image."""
    fmt = scan_params.get_format()
    if fmt != Libinsane.ImgFormat.RAW_RGB_24:
        raise ScanError(f"Unsupported image format: {fmt}")

    width = scan_params.get_width()
    height = int(len(img_data) / (width * 3))  # 3 bytes per pixel for RGB

    logger.debug(f"Converting raw image: {width}x{height}, {len(img_data)} bytes")

    try:
        return Image.frombytes("RGB", (width, height), img_data, "raw", "RGB", 0, 1)
    except Exception as e:
        raise ScanError(f"Failed to convert raw image data: {e}")


def save_image(
    image: Image.Image, file_path: Path, output_format: str, quality: int = 90
):
    """Save PIL Image to file with specified format and quality."""
    try:
        file_path.parent.mkdir(parents=True, exist_ok=True)

        if output_format.lower() == "jpeg":
            image.save(file_path, format="JPEG", quality=quality, optimize=True)
        elif output_format.lower() == "png":
            image.save(file_path, format="PNG", compress_level=9, optimize=True)
        else:
            raise ScanError(f"Unsupported output format: {output_format}")

        logger.info(f"Saved image to {file_path}")
    except Exception as e:
        raise ScanError(f"Failed to save image: {e}")


def scan_document(
    config: AppConfig, overrides: Optional[ScanOverrides] = None
) -> List[Path]:
    """
    Scan document(s) and save to configured directory.
    Returns list of saved file paths.
    """
    # Apply overrides to config
    effective_config = config.copy()
    if overrides:
        for field, value in overrides.dict(exclude_unset=True).items():
            if hasattr(effective_config, field):
                setattr(effective_config, field, value)

    api = initialize_api()
    saved_files = []
    session = None

    try:
        # Get device and source
        device = get_device(api, effective_config.device_id or None)
        source = get_scan_source(device)

        logger.info(f"Using device: {device.get_name()}")
        logger.info(f"Using source: {source.get_name()}")

        # Configure scan options
        configure_scan_options(source, effective_config.resolution)

        # Start scanning session
        session = source.scan_start()

        if session.end_of_feed():
            raise ScanError("No document found in scanner")

        page_num = 0
        while not session.end_of_feed() and page_num < 20:  # Limit to prevent runaway
            try:
                # Get scan parameters
                scan_params = session.get_scan_parameters()
                logger.info(
                    f"Scanning page {page_num}: {scan_params.get_width()}x{scan_params.get_height()}"
                )

                # Read image data
                img_data = b""
                while not session.end_of_page():
                    try:
                        chunk = session.read_bytes(128 * 1024)
                        if not chunk:
                            break
                        img_data += chunk.get_data()
                    except Exception:
                        break  # End of page

                if not img_data:
                    logger.warning(f"No data for page {page_num}")
                    break

                # Convert to PIL Image
                image = raw_to_image(scan_params, img_data)

                # Generate filename
                filename = format_filename(
                    effective_config.filename_pattern,
                    page_num,
                    effective_config.output_format,
                    device.get_dev_id(),
                )

                # Ensure unique filename and save
                file_path = ensure_unique_filename(
                    effective_config.output_dir, filename
                )
                save_image(
                    image,
                    file_path,
                    effective_config.output_format,
                    effective_config.quality,
                )
                saved_files.append(file_path)

                page_num += 1

            except Exception as e:
                logger.error(f"Error scanning page {page_num}: {e}")
                break

        if page_num == 0:
            raise ScanError("No pages were scanned successfully")

        logger.info(f"Successfully scanned {page_num} page(s)")
        return saved_files

    except Exception as e:
        logger.error(f"Scan failed: {e}")
        raise ScanError(str(e))

    finally:
        if session:
            try:
                session.cancel()
            except Exception:
                pass
