#!/usr/bin/env python3

import argparse
import sys
from pathlib import Path

from app.config import AppConfig
from app.scanner import list_devices, scan_document, ScannerError
from app.filename import format_filename, ensure_unique_filename


def cli_list_devices():
    """CLI command to list available scanner devices."""
    try:
        devices = list_devices()
        if not devices:
            print("No scanner devices found.")
            return
        print(f"Found {len(devices)} device(s):")
        for i, device in enumerate(devices):
            print(f"  [{i}]: ID='{device.id}', Name='{device.name}'")
            if device.vendor or device.model:
                print(f"       Vendor='{device.vendor}', Model='{device.model}'")
    except ScannerError as e:
        print(f"An error occurred while listing devices: {e}", file=sys.stderr)
        sys.exit(1)


def cli_scan_document(device_id, output_path, img_format):
    """CLI command to scan a document."""
    try:
        # Create a basic config for CLI usage
        config = AppConfig(
            device_id=device_id or "",
            output_format=img_format,
            filename_pattern=output_path,
            save_to="media" if output_path != "-" else "media",  # Doesn't matter for CLI
            subdir="."  # Current directory for CLI
        )
        
        if output_path == "-":
            print("Stdout output not supported in CLI mode. Use a file path.", file=sys.stderr)
            sys.exit(1)
        
        # Override output directory to current directory for CLI
        config.subdir = "."
        
        saved_files = scan_document(config)
        print(f"Successfully scanned {len(saved_files)} page(s):")
        for file_path in saved_files:
            print(f"  {file_path}")
            
    except ScannerError as e:
        print(f"An error occurred during scanning: {e}", file=sys.stderr)
        sys.exit(1)


def main():
    """Main function to parse arguments and execute the script."""
    parser = argparse.ArgumentParser(description="A Python script to scan documents using libinsane.")
    parser.add_argument("-l", "--list", action="store_true", help="Lists available scanner devices.")
    parser.add_argument("-s", "--scan", action="store_true", help="Scans a page from a printer.")
    parser.add_argument("-p", "--printer", dest="device_id", help="The ID of the printer to use for scanning (defaults to the first available).")
    parser.add_argument("-o", "--output", default="scan_{dateandtime}.{format_suffix}", help="The output file path. Use '-' for stdout. Default: scan_{dateandtime}.{format_suffix}")
    parser.add_argument("-f", "--format", choices=['png', 'jpeg'], default='png', help="The output image format (png or jpeg). Default: png")

    args = parser.parse_args()

    if args.list:
        cli_list_devices()
    elif args.scan:
        cli_scan_document(args.device_id, args.output, args.format)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
