# Libinsane Scanner Add-on Docs

This add-on provides Telegram and Home Assistant automation support for scanning documents with libinsane, delivering images, and generating PDFs.

## Core Features

- Scan documents with libinsane and save them to disk.
- Telegram bot commands for scanning, device listing, PDF creation, and cleanup.
- Home Assistant automation support via STDIN commands.
- Outputs saved to `/media/<subdir>` or `/share/<subdir>` based on config.

## Output and Storage

- Output directory is determined by:
  - `save_to: media` -> `/media/<subdir>`
  - `save_to: share` -> `/share/<subdir>`
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
- `/pdf`
  - Combines queued scans from the last 30 minutes into a single PDF.
  - Sends the PDF to the chat and saves it to the output folder.
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
- Saves scan pages to disk.
- Sends scanned images to Telegram if `notify_telegram` is true.
- Adds scanned pages to the PDF queue.

### PDF

```json
{"command": "pdf"}
```

- Builds a PDF from scans in the last 30 minutes.
- Sends the PDF to Telegram if configured.
- Saves the PDF to the output folder.
- Clears the queued items used for the PDF.

## Configuration

- `telegram.bot_token`: Telegram bot token.
- `telegram.chat_id`: Authorized chat ID for messaging.
- `save_to`: `media` or `share` to control output base.
- `subdir`: Output subdirectory under the base path.

## Notes and Limitations

- PDF generation uses Pillow; images are converted to RGB before saving.
- PNG alpha channels are flattened automatically.
- The PDF queue is not persisted across restarts.
- `/delete` requires replying to the scan message that belongs to the queue.
