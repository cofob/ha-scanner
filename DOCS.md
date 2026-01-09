# Libinsane Scanner Add-on Docs

This add-on provides Telegram and Home Assistant automation support for scanning documents with libinsane, delivering images, and generating PDFs.

## Core Features

- Scan documents with libinsane and optionally save them to disk.
- Telegram bot commands for scanning, device listing, PDF creation, and cleanup.
- Telegram commands to print attached images via CUPS.
- Home Assistant automation support via STDIN commands.
- Outputs saved to `/media/<subdir>` or `/share/<subdir>` based on config (or kept temporary when storage is disabled).
- Temporary DPI overrides via Telegram or STDIN commands.

## Output and Storage

- Output directory is determined by:
  - `save_to: media` -> `/media/<subdir>`
  - `save_to: share` -> `/share/<subdir>`
- `save_to: none` uses a temporary `/tmp/ha_scanner/<subdir>` location and removes files when they fall out of the PDF queue.
- Each scan page is saved as a PNG file with a timestamped name.
- PDFs are saved in the same output folder.

## Telegram Commands

- `/start`
  - Shows the welcome message and available commands.
- `/help`
  - Shows usage help and command list.
- `/devices`
  - Lists available scanner devices.
- `/scan`
  - Scans a document from the connected scanner.
  - Sends scanned pages back as photos (single or album).
  - Adds the scanned pages to the in-memory PDF queue.
- `/copy`
  - Scans a document, prints it in black and white, and sends scans to the chat.
  - Adds the scanned pages to the in-memory PDF queue.
- `/copy_color`
  - Scans a document, prints it in color, and sends scans to the chat.
  - Adds the scanned pages to the in-memory PDF queue.
- `/res <low|medium|high|xhigh>`
  - Temporarily sets scan DPI for the next 30 minutes.
  - Presets: low=150, medium=300, high=600, xhigh=1200.
- `/print`
  - Print an attached image or PDF in black and white via CUPS.
  - Send the command as a caption to an image/PDF or reply to one.
- `/print_color`
  - Print an attached image or PDF in color via CUPS.
  - Send the command as a caption to an image/PDF or reply to one.
- `/pdf`
  - Combines queued scans from the last 30 minutes into a single PDF.
  - Sends the PDF to the chat and saves it to the output folder (unless storage is disabled).
  - Clears the queued items used for the PDF.
- `/delete`
  - Reply to a scan message to delete it from chat.
  - Removes the corresponding image from the PDF queue.
  - Deletes the image file from disk when possible.

## PDF Queue Behavior

- The PDF queue is in-memory only.
- Each scan page is queued when a scan completes.
- Queue entries expire after 30 minutes.
- `/pdf` uses only the last 30 minutes of queued scans.
- `/delete` removes a single queued entry by replied message.

## Home Assistant Automation (STDIN Commands)

The add-on accepts JSON commands via STDIN.

### Scan

```json
{"command": "scan", "device_id": "", "notify_telegram": true}
```

- Performs a scan using the specified device (or default).
- Saves scan pages to disk unless storage is disabled.
- Sends scanned images to Telegram if `notify_telegram` is true.
- Adds scanned pages to the PDF queue.

### Copy (Scan + Print)

```json
{"command": "copy", "device_id": "", "notify_telegram": true}
```

```json
{"command": "copy_color", "device_id": "", "notify_telegram": true}
```

- Performs a scan and prints each page immediately.
- Sends scanned images to Telegram if `notify_telegram` is true.
- Adds scanned pages to the PDF queue.

### PDF

```json
{"command": "pdf"}
```

- Builds a PDF from scans in the last 30 minutes.
- Sends the PDF to Telegram if configured.
- Saves the PDF to the output folder unless storage is disabled.
- Clears the queued items used for the PDF.

### Delete Last Scan

```json
{"command": "delete"}
```

- Removes the most recent scan from the PDF queue.
- Deletes the scan file from disk when available.
- Deletes the corresponding Telegram message when available.

### Resolution Override

```json
{"command": "resolution", "level": "high"}
```

```json
{"command": "resolution", "dpi": 600}
```

- Temporarily sets scan DPI for the next 30 minutes.
- Preset levels match the Telegram `/res` command.

## Configuration

- `telegram.bot_token`: Telegram bot token.
- `telegram.chat_id`: Authorized chat ID for messaging.
- `telegram.admin_ids`: Comma-separated Telegram user IDs allowed to use commands via direct chat.
- `save_to`: `media`, `share`, or `none` to control output storage.
- `subdir`: Output subdirectory under the base path.
- `resolution`: Default scan DPI when no override is active.
- `printer_address`: Optional CUPS server hostname/IP (use `host:port` if needed).
- `printer_name`: Optional CUPS printer/queue name. If empty, the first available
  printer discovered by CUPS is used.

## Notes and Limitations

- PDF generation uses Pillow; images are converted to RGB before saving.
- PNG alpha channels are flattened automatically.
- The PDF queue is not persisted across restarts.
- `/delete` requires replying to the scan message that belongs to the queue.
