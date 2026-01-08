# Changelog

All notable changes to the Libinsane Scanner add-on will be documented in this file.

## [0.1.41] - 2026-01-07

### Added
- Telegram /print and /print_color commands to print attached images or PDFs via CUPS.
- CUPS service startup and optional printer selection via config.

## [0.1.40] - 2026-01-07

### Fixed
- STDIN payload parsing now handles wrapped `input` and JSON strings.

## [0.1.39] - 2026-01-07

### Fixed
- Start scanner service via module execution to preserve package imports.

## [0.1.38] - 2026-01-07

### Fixed
- STDIN bridge now forwards Supervisor input to the scanner daemon via a Unix socket.

## [0.1.37] - 2026-01-07

### Fixed
- STDIN reader retry loop now stops after 15 attempts.

## [0.1.36] - 2026-01-07

### Fixed
- STDIN reader now reopens after EOF to handle Supervisor writes.

## [0.1.35] - 2026-01-07

### Fixed
- STDIN reader now attaches to Supervisor-provided stdin under s6.

## [0.1.34] - 2026-01-07

### Added
- Telegram `/res` command for temporary DPI overrides.
- STDIN `resolution` command for automation-driven DPI overrides.

### Changed
- Scan resolution now applies default DPI from config unless overridden.

## [0.1.33] - 2026-01-07

### Fixed
- Supervisor API base URL for system log and event calls.

## [0.1.32] - 2026-01-07

### Added
- Telegram `/pdf` command to combine scans from the last 30 minutes into a PDF saved to the output folder.
- Telegram `/delete` command to remove a scanned image from chat and the PDF queue.
- STDIN `pdf` command for automation-driven PDF generation and delivery.

## [0.1.31] - 2026-01-07

### Added
- STDIN scan command handling with Home Assistant system log/event reporting.
- Telegram scan logging to Home Assistant including username and chat id.
- Scan output directory now respects add-on `save_to` and `subdir` options.

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
