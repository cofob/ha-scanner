# Print Scanner for Home Assistant

A Home Assistant add-on that provides document scanning capabilities with optional Telegram integration. Scan documents directly from Home Assistant automations using USB or network scanners.

## Features

- 🖨️ **Universal Scanner Support**: Works with any SANE-compatible scanner (USB/Network)
- 🏠 **Home Assistant Integration**: Trigger scans from automations via `hassio.addon_stdin`
- 📱 **Telegram Delivery**: Automatically send scanned documents to Telegram chats
- 🎨 **Flexible Output**: Save as JPEG or PNG with configurable quality
- 📁 **Media Integration**: Files saved to Home Assistant Media Browser
- 🏷️ **Template Filenames**: Dynamic naming with date/time/page placeholders
- 🔌 **HTTP API**: Optional REST endpoints for advanced use cases

## Supported Scanners

This add-on works with any scanner supported by SANE (Scanner Access Now Easy):

- **USB Scanners**: Canon, Epson, HP, Brother, Xerox, and many others
- **Network Scanners**: eSCL/AirScan compatible devices
- **Multi-function Printers**: Most modern printers with scan capability

## Installation

### Method 1: Local Add-on Repository (Recommended)

1. **Add Repository to Home Assistant**
   - Go to **Settings** → **Add-ons** → **Add-on Store**
   - Click the **⋮** menu → **Repositories**
   - Add this repository URL: `https://github.com/cofob/print-scanner`
   - Click **Add** → **Close**

2. **Install the Add-on**
   - Find "Libinsane Scanner" in the add-on store
   - Click **Install**
   - Wait for installation to complete

3. **Configure the Add-on**
   - Go to the **Configuration** tab
   - Set your preferences (see Configuration section below)
   - Click **Save**

4. **Start the Add-on**
   - Go to the **Info** tab
   - Click **Start**
   - Enable **Start on boot** and **Watchdog** if desired

### Method 2: Manual Installation

1. **Clone Repository**
   ```bash
   git clone https://github.com/cofob/print-scanner.git
   cd print-scanner
   ```

2. **Copy Add-on Files**
   Copy the `addon/scanner/` directory to your Home Assistant `addons` folder:
   ```bash
   # For Home Assistant OS/Supervised
   cp -r addon/scanner /usr/share/hassio/addons/local/
   
   # For Home Assistant Container
   cp -r addon/scanner /path/to/homeassistant/addons/
   ```

3. **Reload Add-ons and Install**
   - Go to **Settings** → **Add-ons** → **Add-on Store**
   - Click **⋮** → **Reload**
   - Find "Libinsane Scanner" and install

## Configuration

### Basic Configuration

```yaml
device_id: ""                          # Auto-detect scanner (recommended)
output_format: "jpeg"                  # Image format: jpeg or png
quality: 90                            # JPEG quality (1-100)
filename_pattern: "scan_{datetime}_{page}.{format}"
save_to: "media"                       # Save location: media or share
subdir: "scanner"                      # Subdirectory name
resolution: 300                        # Scan resolution in DPI
```

### Telegram Integration

```yaml
telegram:
  enabled: true
  bot_token: "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
  chat_id: "123456789"
  caption: "Scanned document"
  use_album: true                      # Send multiple pages as album
```

### Advanced Configuration Options

| Option | Description | Default | Valid Values |
|--------|-------------|---------|--------------||
| `device_id` | Specific scanner ID (empty = auto-detect) | `""` | Device ID string |
| `output_format` | Image format | `"jpeg"` | `jpeg`, `png` |
| `quality` | JPEG compression quality | `90` | `1-100` |
| `filename_pattern` | Output filename template | `"scan_{datetime}_{page}.{format}"` | Template string |
| `save_to` | Storage location | `"media"` | `media`, `share` |
| `subdir` | Subdirectory under save location | `"scanner"` | Directory name |
| `resolution` | Scan resolution in DPI | `300` | `75-1200` |

### Filename Template Variables

Use these placeholders in `filename_pattern`:

- `{date}` → `2023-12-01`
- `{time}` → `14-30-15`
- `{datetime}` → `2023-12-01_14-30-15`
- `{timestamp}` → `1701429015`
- `{page}` → `0`, `1`, `2`...
- `{device_id}` → Sanitized scanner ID
- `{format}` → `jpeg` or `png`

## Usage

### From Home Assistant Automations

The primary way to use this add-on is through Home Assistant automations:

```yaml
automation:
  - alias: "Scan Document"
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
                "send_to_telegram": true,
                "caption": "Document scanned at {{ now().strftime('%H:%M') }}"
              }
            }
```

### Available Commands

**List Scanners:**
```json
{"command": "list_devices"}
```

**Scan Document:**
```json
{
  "command": "scan",
  "overrides": {
    "device_id": "epson2:libusb:001:005",
    "output_format": "jpeg",
    "quality": 90,
    "filename_pattern": "scan_{datetime}_{page}.{format}",
    "send_to_telegram": true,
    "caption": "My scanned document"
  }
}
```

### HTTP API (Optional)

The add-on also exposes an HTTP API on port 8099:

- `GET /healthz` - Health check
- `GET /v1/devices` - List available scanners  
- `POST /v1/scan` - Trigger scan with JSON payload

### Using REST Commands

```yaml
rest_command:
  scanner_scan:
    url: "http://homeassistant.local:8099/v1/scan"
    method: POST
    headers:
      Content-Type: "application/json"
    payload: |
      {
        "output_format": "{{ output_format | default('jpeg') }}",
        "quality": {{ quality | default(90) }},
        "send_to_telegram": {{ send_telegram | default('false') }}
      }
```

## Scanner Setup

### Finding Your Scanner

1. **Connect Your Scanner**
   - For USB: Connect scanner to Home Assistant host
   - For Network: Ensure scanner and HA are on same network

2. **Check Add-on Logs**
   - Start the add-on
   - Check the **Log** tab for detected devices
   - Look for entries like: `Found device: EPSON Scanner (epson2:libusb:001:005)`

3. **Use the API**
   ```bash
   curl http://homeassistant.local:8099/v1/devices
   ```

### Common Device IDs

- **USB**: `epson2:libusb:001:005`, `hp:libusb:002:003`
- **Network**: `airscan:escl:Canon TR8500:http://192.168.1.100:80/eSCL/`

### Permissions

Ensure the add-on has proper permissions:
- **USB Access**: Enabled in add-on configuration
- **Device Mapping**: `/dev/bus/usb:/dev/bus/usb:rwm` (automatic)

## Telegram Setup

### 1. Create Telegram Bot

1. Message [@BotFather](https://t.me/BotFather) on Telegram
2. Send `/newbot` and follow instructions
3. Copy the bot token (format: `123456:ABC-DEF...`)

### 2. Get Chat ID

**For personal chat:**
1. Message your bot first
2. Visit: `https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates`
3. Find your chat ID in the response

**For group chat:**
1. Add bot to group with admin permissions
2. Send a message mentioning the bot
3. Use the same URL to get the group chat ID (negative number)

### 3. Test Configuration

Send a test message to verify setup:
```bash
curl -X POST "https://api.telegram.org/bot<YOUR_TOKEN>/sendMessage" \
     -d "chat_id=<CHAT_ID>&text=Test from Home Assistant Scanner"
```

## File Access

### Home Assistant Media Browser

Files saved with `save_to: "media"` appear in:
- **Media** → **local media** → **scanner** (or your configured subdirectory)

### File Share Add-ons

Files saved with `save_to: "share"` can be accessed via:
- Samba share add-on
- FTP add-on  
- File Editor add-on

## Troubleshooting

### Scanner Not Detected

1. **Check USB Connection**
   - Verify scanner is powered on and connected
   - Ensure USB mapping is enabled in add-on configuration

2. **Network Scanners**
   - Verify scanner supports eSCL/AirScan
   - Check network connectivity between scanner and HA
   - Try static IP for scanner

3. **Check SANE Support**
   - Visit [SANE Project](http://www.sane-project.org/sane-supported-devices.html)
   - Search for your specific scanner model

### Permission Issues

```bash
# Check USB devices (on HA host)
lsusb

# Check device permissions
ls -la /dev/bus/usb/
```

### Telegram Not Working

1. **Verify Bot Token**: Test with Telegram API directly
2. **Check Chat ID**: Ensure correct format (positive for users, negative for groups)
3. **Bot Permissions**: Ensure bot can send messages to target chat
4. **File Size**: Telegram has 50MB limit per file

### Performance Issues

- **Lower Resolution**: Reduce DPI for faster scans
- **JPEG Format**: Use JPEG instead of PNG for smaller files
- **Quality Setting**: Lower JPEG quality for faster processing

### Common Errors

**"No module named gi"**: PyGObject installation issue
- Check add-on logs during startup
- Verify libinsane installation completed successfully

**"Device busy"**: Scanner in use by another process
- Restart the scanner
- Check for other scanning software on the host

**"No document found"**: Scanner empty or not ready
- Ensure document is properly placed
- Check scanner's ready status

## Development

### CLI Usage (Outside Home Assistant)

The original CLI functionality is preserved:

```bash
# Install dependencies
uv sync

# List scanners
uv run python main.py --list

# Scan document
uv run python main.py --scan --output "scan_{dateandtime}.{format_suffix}" --format jpeg
```

### Development API Server

```bash
# Run development server
uv run python -m app.main
```

### Building the Add-on

```bash
# Build Docker image
docker build -f addon/scanner/Dockerfile \
  --build-arg BUILD_FROM=ghcr.io/home-assistant/amd64-base-debian:bookworm \
  -t ha-scanner:dev .
```

## License

MIT License - See LICENSE file for details.

## Support

- **Issues**: [GitHub Issues](https://github.com/cofob/print-scanner/issues)
- **Discussions**: [GitHub Discussions](https://github.com/cofob/print-scanner/discussions)
- **Documentation**: [Add-on Documentation Tab](./addon/scanner/DOCS.md)

## Contributing

Contributions welcome! Please read the contributing guidelines and submit pull requests.

---

**Made with ❤️ for the Home Assistant community**