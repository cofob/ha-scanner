# Libinsane Scanner Home Assistant Add-on

Scan documents using your USB or network scanner with Telegram delivery, PDF
generation, and optional print support.

## Features

- Scan with libinsane/SANE and save to `/media/<subdir>` or `/share/<subdir>` (or keep output temporary).
- Telegram bot commands for scan, device listing, PDF creation, and cleanup.
- Print attached images or PDFs via CUPS (`/print` and `/print_color`).
- Scan-and-print workflows (`/copy` and `/copy_color`).
- Home Assistant automation commands via Supervisor STDIN.
- Temporary DPI overrides via Telegram (`/res`) or STDIN commands.

## Installation

1. In Home Assistant, go to **Settings → Add-ons → Add-on Store**.
2. Open the menu (top-right) and choose **Repositories**.
3. Add the repository URL:
   - `https://github.com/cofob/ha-scanner`
4. Find **Libinsane Scanner** in the list, click **Install**, then **Start**.
5. Configure options (Telegram token/chat id, output folder, resolution, printer).

## Configuration notes

- `telegram.bot_token` and `telegram.chat_id` enable Telegram delivery and commands.
- `telegram.admin_ids` allows direct chat access for comma-separated Telegram user IDs.
- `save_to` controls the base folder (`media`, `share`, or `none`) for output files.
- `subdir` is the output subdirectory.
- `resolution` sets the default scan DPI unless overridden.
- `printer_address` sets the CUPS server hostname/IP (use `host:port` if needed).
- `printer_name` is optional; if empty, the first available CUPS printer is used.

## Usage

See `DOCS.md` for the full command list, STDIN payloads, and examples.
