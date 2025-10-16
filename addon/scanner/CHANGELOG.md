# Changelog

All notable changes to the Libinsane Scanner add-on will be documented in this file.

## [0.1.0] - 2024-01-16

### Added
- Initial release of Libinsane Scanner Home Assistant add-on
- Support for USB and network scanners via libinsane/SANE
- Home Assistant integration via `hassio.addon_stdin` service
- HTTP API with endpoints for device listing and scanning
- Telegram integration for automatic document delivery
- Configurable output formats (JPEG/PNG) with quality settings
- Template-based filename generation with placeholders
- Support for saving to Home Assistant media or share directories
- Multi-page scanning support with automatic page numbering
- Comprehensive error handling and JSON logging
- Documentation with automation examples and troubleshooting guide

### Technical Details
- Built on Home Assistant base images (Debian Bookworm)
- Uses uv for Python dependency management
- Libinsane compiled from source for latest compatibility
- FastAPI-based HTTP API with Pydantic validation
- Asynchronous Telegram delivery with httpx
- S6-overlay for proper service management