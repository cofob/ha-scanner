# Libinsane Scanner Add-on Documentation

## Installation

### Local Add-on Repository

1. Add this repository as a local add-on repository in Home Assistant
2. Navigate to **Supervisor** > **Add-on Store** > **⋮** > **Repositories**
3. Add the URL of this repository
4. Find "Libinsane Scanner" in the add-on store and install it

## Configuration

### Basic Options

| Option | Description | Default |
|--------|-------------|---------|
| `device_id` | Specific scanner device ID (empty = auto-detect) | `""` |
| `output_format` | Image format: `jpeg` or `png` | `"jpeg"` |
| `quality` | JPEG quality (1-100) | `90` |
| `filename_pattern` | Template for output filenames | `"scan_{datetime}_{page}.{format}"` |
| `save_to` | Save location: `media` or `share` | `"media"` |
| `subdir` | Subdirectory name | `"scanner"` |
| `resolution` | Scan resolution in DPI (75-1200) | `300` |

### Telegram Integration

| Option | Description | Default |
|--------|-------------|---------|
| `telegram.enabled` | Enable Telegram delivery | `false` |
| `telegram.bot_token` | Telegram bot token | `""` |
| `telegram.chat_id` | Target chat ID | `""` |
| `telegram.caption` | Message caption | `"Scanned document"` |
| `telegram.use_album` | Send multiple pages as album | `true` |

## Scanner Device Discovery

### Finding Your Scanner ID

1. Start the add-on and check the logs for detected devices
2. Or use the HTTP API: `GET http://homeassistant.local:46201/v1/devices`
3. Device IDs typically look like:
   - USB: `epson2:libusb:001:005`
   - Network: `airscan:escl:Canon TR8500:http://192.168.1.100:80/eSCL/`

### Configuration Examples

**Auto-detect scanner:**
```yaml
device_id: ""
```

**Specific USB scanner:**
```yaml
device_id: "epson2:libusb:001:005"
```

**Network scanner:**
```yaml
device_id: "airscan:escl:Canon TR8500:http://192.168.1.100:80/eSCL/"
```

## Filename Templates

The `filename_pattern` supports these placeholders:

- `{date}` - Current date (YYYY-MM-DD)
- `{time}` - Current time (HH-MM-SS)
- `{datetime}` - Date and time (YYYY-MM-DD_HH-MM-SS)
- `{timestamp}` - Unix timestamp
- `{page}` - Page number (0-based)
- `{device_id}` - Scanner device ID (sanitized)
- `{format}` - File format (jpeg/png)

**Examples:**
- `scan_{datetime}_{page}.{format}` → `scan_2023-12-01_14-30-15_0.jpeg`
- `document_{date}_page{page}.{format}` → `document_2023-12-01_page0.jpeg`

## Home Assistant Integration

### Method 1: hassio.addon_stdin (Recommended)

This is the primary way to trigger scans from Home Assistant automations.

```yaml
automation:
  - alias: "Scan on button press"
    trigger:
      platform: state
      entity_id: input_button.scan_document
    action:
      - service: hassio.addon_stdin
        data:
          addon: local_print_scanner_scanner
          input: |
            {
              "command": "scan",
              "overrides": {
                "output_format": "jpeg",
                "quality": 95,
                "filename_pattern": "scan_{datetime}_{page}.{format}",
                "send_to_telegram": true,
                "caption": "Document scanned via automation"
              }
            }
```

**Available commands:**
- `{"command": "list_devices"}` - List available scanners
- `{"command": "scan", "overrides": {...}}` - Perform scan with optional overrides

### Method 2: HTTP API

The add-on also exposes an HTTP API on port 46201 for manual or advanced use cases.

```yaml
rest_command:
  scanner_scan:
    url: "http://127.0.0.1:46201/v1/scan"
    method: POST
    headers:
      Content-Type: "application/json"
    payload: |
      {
        "output_format": "{{ output_format | default('jpeg') }}",
        "quality": {{ quality | default(90) }},
        "send_to_telegram": {{ send_telegram | default(false) }}
      }
```

**API Endpoints:**
- `GET /healthz` - Health check
- `GET /v1/devices` - List available scanners
- `POST /v1/scan` - Trigger scan

## Telegram Setup

### 1. Create a Telegram Bot

1. Message [@BotFather](https://t.me/BotFather) on Telegram
2. Send `/newbot` and follow the prompts
3. Copy the bot token (looks like `123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11`)

### 2. Get Chat ID

**For personal chat:**
1. Message your bot
2. Visit: `https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates`
3. Find your chat ID in the response

**For group chat:**
1. Add the bot to the group
2. Send a message mentioning the bot
3. Visit: `https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates`
4. Find the group chat ID (negative number)

### 3. Configure Add-on

```yaml
telegram:
  enabled: true
  bot_token: "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
  chat_id: "123456789"  # or "-123456789" for groups
  caption: "Scanned document"
  use_album: true
```

**Album Behavior:**
- Single page: Sent as individual document
- 2-10 pages: Sent as media group (album)
- 10+ pages: Sent as individual documents

## File Access

### Media Browser

Files saved to the `media` location are accessible through Home Assistant's Media Browser:
1. Go to **Media** in the sidebar
2. Navigate to **local media** > **scanner** (or your configured subdirectory)

### File Paths

- **Media**: `/media/scanner/` (accessible via Media Browser)
- **Share**: `/share/scanner/` (accessible via file share add-ons)

## Troubleshooting

### Scanner Not Detected

1. **USB Permission**: Ensure USB mapping is enabled in add-on configuration
2. **Device Connection**: Check that the scanner is powered on and connected
3. **Driver Support**: Some scanners need specific SANE backends
4. **Check Logs**: Look for SANE device detection messages in add-on logs

### Network Scanner Issues

1. **Network Connectivity**: Ensure scanner and Home Assistant are on same network
2. **eSCL Support**: Scanner must support eSCL/AirScan protocol
3. **Firewall**: Check for network firewall blocking discovery
4. **IP Address**: Try configuring scanner with static IP

### Libinsane Import Errors

If you see Python import errors for libinsane:
1. Check add-on logs for build errors
2. Restart the add-on
3. Report issue with logs if problem persists

### Telegram Delivery Fails

1. **Bot Token**: Verify token is correct and bot is active
2. **Chat ID**: Ensure chat ID is correct (negative for groups)
3. **Bot Permissions**: Check bot can send messages to the chat
4. **File Size**: Telegram has a 50MB limit per file

### Performance Issues

1. **Resolution**: Lower DPI for faster scans
2. **Format**: JPEG is faster than PNG
3. **Quality**: Lower JPEG quality for smaller files

## Advanced Configuration

### Custom Output Directory

```yaml
save_to: "share"
subdir: "documents/scans"  # Creates /share/documents/scans/
```

### High-Quality Archival Scans

```yaml
output_format: "png"
resolution: 600
filename_pattern: "archive_{date}_{timestamp}_{page}.{format}"
```

### Batch Scanning with Telegram

```yaml
telegram:
  enabled: true
  use_album: true
  caption: "Batch scan completed at {datetime}"
```

## Security Notes

- **Telegram Token**: Stored in plain text in add-on options (visible to admins)
- **USB Access**: Add-on has access to all USB devices when USB mapping is enabled
- **Network Access**: Add-on can access local network for scanner discovery
- **File Access**: Add-on can read/write to mapped media and share directories

## Support

For issues and feature requests, please check the add-on logs first and then report issues on the project repository.