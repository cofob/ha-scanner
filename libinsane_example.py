#!/usr/bin/env python3

import argparse
import sys
from datetime import datetime
from pathlib import Path

import gi

gi.require_version("Libinsane", "1.0")
from gi.repository import Libinsane
from PIL import Image


def list_devices(api):
    """Lists all available scanner devices."""
    print("Looking for scanner devices...")
    try:
        devices = api.list_devices(Libinsane.DeviceLocations.ANY)
        if not devices:
            print("No scanner devices found.")
            return
        print(f"Found {len(devices)} device(s):")
        for i, dev in enumerate(devices):
            print(
                f"  [{i}]: ID='{dev.get_dev_id()}', Name='{dev.get_name()}', Type='{dev.get_type()}'"
            )
    except Exception as e:
        print(f"An error occurred while listing devices: {e}", file=sys.stderr)


def scan_document(api, device_id, output_path, img_format):
    """Scans a document from the specified device and saves it to a file."""
    try:
        if device_id:
            device = api.get_device(device_id)
        else:
            devices = api.list_devices(Libinsane.DeviceLocations.ANY)
            if not devices:
                print("No scanner devices found.", file=sys.stderr)
                return
            device = devices[0]
            print(
                f"No device specified, using the first available device: {device.get_name()}"
            )

        print(f"Using device: {device.get_name()}")

        # Get the first available scan source (e.g., flatbed)
        sources = device.get_children()
        if not sources:
            print("No scan sources found for this device.", file=sys.stderr)
            return
        source = sources[0]
        print(f"Using source: {source.get_name()}")

        session = source.scan_start()
        print("Scanning...")

        if session.end_of_feed():
            print("No document found in the scanner.", file=sys.stderr)
            return

        page_num = 0
        while not session.end_of_feed():
            scan_params = session.get_scan_parameters()
            img_data = b""
            while True:
                try:
                    chunk = session.read_bytes(128 * 1024)
                    if not chunk:
                        break
                    img_data += chunk.get_data()
                except Exception:
                    break  # End of page

            if not img_data:
                continue

            width = scan_params.get_width()
            height = int(len(img_data) / (width * 3))  # Assuming 24-bit RGB

            if scan_params.get_format() == Libinsane.ImgFormat.RAW_RGB_24:
                image = Image.frombytes("RGB", (width, height), img_data)
            else:
                # Handle other formats if necessary, for now, we assume RAW RGB
                print(
                    f"Unsupported image format: {scan_params.get_format()}",
                    file=sys.stderr,
                )
                continue

            # Determine the output path
            if output_path == "-":
                # Write to stdout
                image.save(sys.stdout.buffer, format=img_format.upper())
            else:
                # Generate a filename if not fully specified
                if "{" in output_path:
                    output_file = Path(
                        output_path.format(
                            dateandtime=datetime.now().strftime("%Y-%m-%d_%H-%M-%S"),
                            page=page_num,
                            format_suffix=img_format,
                        )
                    )
                else:
                    output_file = Path(output_path)

                output_file.parent.mkdir(parents=True, exist_ok=True)
                image.save(output_file, format=img_format.upper())
                print(f"Saved page {page_num} to '{output_file}'")

            page_num += 1

    except Exception as e:
        print(f"An error occurred during scanning: {e}", file=sys.stderr)
    finally:
        if "session" in locals() and session:
            session.cancel()


def main():
    """Main function to parse arguments and execute the script."""
    parser = argparse.ArgumentParser(
        description="A Python script to scan documents using libinsane."
    )
    parser.add_argument(
        "-l", "--list", action="store_true", help="Lists available scanner devices."
    )
    parser.add_argument(
        "-s", "--scan", action="store_true", help="Scans a page from a printer."
    )
    parser.add_argument(
        "-p",
        "--printer",
        dest="device_id",
        help="The ID of the printer to use for scanning (defaults to the first available).",
    )
    parser.add_argument(
        "-o",
        "--output",
        default="scan_{dateandtime}.{format_suffix}",
        help="The output file path. Use '-' for stdout. Default: scan_{dateandtime}.{format_suffix}",
    )
    parser.add_argument(
        "-f",
        "--format",
        choices=["png", "jpeg"],
        default="png",
        help="The output image format (png or jpeg). Default: png",
    )

    args = parser.parse_args()

    try:
        api = Libinsane.Api.new_safebet()
    except Exception as e:
        print(f"Failed to initialize libinsane API: {e}", file=sys.stderr)
        sys.exit(1)

    if args.list:
        list_devices(api)
    elif args.scan:
        scan_document(api, args.device_id, args.output, args.format)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
