"""STDIN server for Home Assistant addon communication."""

import json
import logging
import sys
import threading
import uuid
from typing import Dict, Any

from .config import AppConfig, ScanOverrides
from .scanner import list_devices, scan_document, ScannerError
from .telegram import send_to_telegram


logger = logging.getLogger(__name__)


def handle_list_devices_command() -> Dict[str, Any]:
    """Handle list_devices command."""
    try:
        devices = list_devices()
        return {
            "success": True,
            "devices": [device.to_dict() for device in devices]
        }
    except ScannerError as e:
        logger.error(f"Failed to list devices: {e}")
        return {"success": False, "error": str(e)}


def handle_scan_command(config: AppConfig, overrides: Dict[str, Any]) -> Dict[str, Any]:
    """Handle scan command."""
    request_id = str(uuid.uuid4())[:8]
    
    try:
        # Convert overrides to ScanOverrides model
        scan_overrides = ScanOverrides(**overrides) if overrides else None
        
        logger.info(f"[{request_id}] STDIN scan command with overrides: {overrides}")
        
        # Perform scan
        saved_files = scan_document(config, scan_overrides)
        saved_paths = [str(path) for path in saved_files]
        
        logger.info(f"[{request_id}] Saved {len(saved_files)} files: {saved_paths}")
        
        # Handle Telegram delivery
        telegram_result = None
        should_send_telegram = (
            overrides.get('send_to_telegram') if 'send_to_telegram' in overrides
            else config.telegram.enabled
        )
        
        if should_send_telegram:
            if not config.telegram.bot_token or not config.telegram.chat_id:
                logger.warning(f"[{request_id}] Telegram enabled but missing credentials")
                telegram_result = {"sent": False, "error": "Missing Telegram credentials"}
            else:
                caption = overrides.get('caption') or config.telegram.caption
                telegram_result = send_to_telegram(
                    saved_files,
                    config.telegram.bot_token,
                    config.telegram.chat_id,
                    caption,
                    config.telegram.use_album
                )
                logger.info(f"[{request_id}] Telegram result: {telegram_result}")
        
        result = {
            "success": True,
            "request_id": request_id,
            "saved": saved_paths,
        }
        
        if telegram_result:
            result["telegram"] = telegram_result
        
        return result
        
    except ScannerError as e:
        logger.error(f"[{request_id}] Scanner error: {e}")
        return {"success": False, "error": str(e), "request_id": request_id}
    except Exception as e:
        logger.error(f"[{request_id}] Unexpected error: {e}")
        return {"success": False, "error": f"Unexpected error: {e}", "request_id": request_id}


def process_stdin_command(config: AppConfig, command_data: Dict[str, Any]) -> Dict[str, Any]:
    """Process a single command from STDIN."""
    command = command_data.get("command")
    
    if command == "list_devices":
        return handle_list_devices_command()
    elif command == "scan":
        overrides = command_data.get("overrides", {})
        return handle_scan_command(config, overrides)
    else:
        return {"success": False, "error": f"Unknown command: {command}"}


def stdin_server_loop(config: AppConfig):
    """Main loop for processing STDIN commands."""
    logger.info("STDIN server started, listening for commands...")
    
    try:
        while True:
            try:
                line = sys.stdin.readline()
                if not line:
                    # EOF reached
                    logger.info("STDIN EOF reached, stopping server")
                    break
                
                line = line.strip()
                if not line:
                    continue
                
                # Parse JSON command
                try:
                    command_data = json.loads(line)
                except json.JSONDecodeError as e:
                    logger.error(f"Invalid JSON in STDIN: {e}")
                    result = {"success": False, "error": f"Invalid JSON: {e}"}
                    print(json.dumps(result), flush=True)
                    continue
                
                # Process command
                result = process_stdin_command(config, command_data)
                
                # Send result to STDOUT
                print(json.dumps(result), flush=True)
                
            except KeyboardInterrupt:
                logger.info("STDIN server interrupted")
                break
            except Exception as e:
                logger.error(f"Unexpected error in STDIN server: {e}")
                result = {"success": False, "error": f"Server error: {e}"}
                print(json.dumps(result), flush=True)
                
    except Exception as e:
        logger.error(f"Fatal error in STDIN server: {e}")


def start_stdin_server(config: AppConfig) -> threading.Thread:
    """Start STDIN server in a background thread."""
    thread = threading.Thread(
        target=stdin_server_loop,
        args=(config,),
        daemon=True,
        name="StdinServer"
    )
    thread.start()
    logger.info("STDIN server thread started")
    return thread