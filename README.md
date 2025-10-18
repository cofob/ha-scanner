# Libinsane Scanner Home Assistant Add-on

Scan documents using your USB or network scanner directly from Home Assistant automations with optional Telegram delivery.

## Features

- **Multiple Scanner Support**: Works with USB and network scanners via libinsane/SANE
- **Automation Integration**: Trigger scans via `hassio.addon_stdin` service calls (continuous STDIN listener)
- **Telegram Integration**: Automatically send scanned documents to Telegram
- **Flexible Output**: Save to Home Assistant media or share folders
- **Configurable Quality**: JPEG/PNG output with quality settings
- **Template Filenames**: Use date/time/page templates in filenames
- **HTTP API**: Optional REST endpoints for manual triggering

## Supported Scanners

This add-on supports any scanner that works with SANE, including:
- USB scanners (Canon, Epson, HP, Brother, etc.)
- Network scanners via eSCL/AirScan
- Multi-function printer scanners

## Quick Start

1. Install the add-on from the Home Assistant Add-on Store
2. Configure your scanner settings in the add-on options
3. (Optional) Set up Telegram integration
4. Start the add-on
5. Create automations to trigger scans

## Basic Configuration

```yaml
device_id: ""  # Leave empty to auto-detect
output_format: "jpeg"
quality: 90
save_to: "media"
subdir: "scanner"
telegram:
  enabled: false
```

## Example Automation

```yaml
automation:
  - alias: "Scan Document on Button Press"
    trigger:
      - platform: state
        entity_id: input_button.scan_document
    action:
      - service: hassio.addon_stdin
        data:
          addon: local_print_scanner_scanner
          input: |
            {"command": "scan", "overrides": {"send_to_telegram": true}}
```

### STDIN Responses

Each command sent via `hassio.addon_stdin` now receives a JSON response on the add-on logs/stdout.
Example success response:

```json
{"success": true, "command": "scan", "request_id": "5f92c3d1", "saved": ["/media/scanner/scan_2025-10-18_08-31-02_0.jpeg"]}
```

If an error occurs, a structured payload is returned with `success: false` along with `error` and `detail` fields.
The STDIN listener stays active for the lifetime of the add-on and safely ignores EOF conditions, preventing the HTTP server from shutting down unexpectedly.

For detailed documentation, see the **Documentation** tab.