# Changelog

All notable changes to the Libinsane Scanner add-on will be documented in this file.

## [0.1.63] - 2026-01-09

### Added
- Allow disabling on-disk scan storage with `save_to: none`.
- Add `printer_address` to connect to a custom CUPS server host.

## [0.1.62] - 2026-01-09

### Changed
- Allow a fixed admin user ID in authorization checks.

## [0.1.61] - 2026-01-09

### Changed
- Simplify parsing for `telegram.admin_ids`.

## [0.1.60] - 2026-01-09

### Fixed
- Robust parsing of `telegram.admin_ids` to ensure admin DMs authorize correctly.

## [0.1.59] - 2026-01-09

### Changed
- Default log level to DEBUG.

## [0.1.58] - 2026-01-09

### Added
- Debug logging for authorization decisions to help diagnose DM access.

## [0.1.57] - 2026-01-09

### Changed
- Only trigger device discovery after service start (no scan).

## [0.1.56] - 2026-01-09

### Added
- Trigger a scan immediately after service start.

## [0.1.55] - 2026-01-09

### Fixed
- Allow admin users to run commands in private chats reliably.

## [0.1.54] - 2026-01-09

### Added
- STDIN `delete` command to remove the latest queued scan and delete its Telegram message.

### Fixed
- Send a Telegram warning when STDIN `pdf` runs with an empty queue.

## [0.1.53] - 2026-01-07

### Fixed
- Normalize telegram.admin_ids parsing and ensure admin access works in private chats.

## [0.1.52] - 2026-01-07

### Fixed
- Accept comma-separated telegram.admin_ids strings and parse them into IDs.

## [0.1.51] - 2026-01-07

### Fixed
- Fix telegram.admin_ids schema validation for empty lists.

## [0.1.50] - 2026-01-07

### Fixed
- Restrict PDF queue usage to the requesting chat (or STDIN-only queue items).

## [0.1.49] - 2026-01-07

### Added
- `telegram.admin_ids` to allow admin users to use bot commands in direct chat.

## [0.1.48] - 2026-01-07

### Fixed
- Always deliver scanned images for /copy commands even if printing is unavailable.

## [0.1.47] - 2026-01-07

### Fixed
- Allow /print commands to use media from replied messages with images or PDFs.

## [0.1.46] - 2026-01-07

### Changed
- Expire cached scanner device after 8 hours and clear it on scan errors.

## [0.1.45] - 2026-01-07

### Changed
- Cache the selected scanner device after the first scan to speed up subsequent scans.

## [0.1.44] - 2026-01-07

### Changed
- Printing now applies monochrome-focused job options to speed up black-and-white jobs.

## [0.1.43] - 2026-01-07

### Fixed
- Telegram /print and /print_color now respond when sent as image/PDF captions.

## [0.1.42] - 2026-01-07

### Added
- Telegram /copy and /copy_color commands to scan and print immediately.
- STDIN commands `copy` and `copy_color` for scan-and-print automations.

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
