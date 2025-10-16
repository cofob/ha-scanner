"""Main application entry point for the scanner addon."""

import logging
import signal
import sys
from pathlib import Path

import uvicorn
from pythonjsonlogger import jsonlogger

from .config import load_config
from .api import create_app, set_app_config
from .stdin_server import start_stdin_server


def setup_logging():
    """Setup JSON logging for Home Assistant."""
    # Create JSON formatter
    formatter = jsonlogger.JsonFormatter(
        '%(asctime)s %(name)s %(levelname)s %(message)s'
    )
    
    # Setup root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    
    # Clear existing handlers
    root_logger.handlers.clear()
    
    # Add console handler with JSON formatting
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    root_logger.addHandler(handler)
    
    # Set specific log levels
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)


def setup_signal_handlers():
    """Setup graceful shutdown handlers."""
    def signal_handler(signum, frame):
        logging.info(f"Received signal {signum}, shutting down gracefully...")
        sys.exit(0)
    
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)


def main():
    """Main application entry point."""
    setup_logging()
    setup_signal_handlers()
    
    logger = logging.getLogger(__name__)
    logger.info("Starting Scanner Add-on...")
    
    try:
        # Load configuration
        config = load_config()
        logger.info(f"Loaded configuration: save_to={config.save_to}, "
                   f"output_format={config.output_format}, "
                   f"telegram_enabled={config.telegram.enabled}")
        
        # Ensure output directory exists
        config.output_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Output directory: {config.output_dir}")
        
        # Create FastAPI app and inject config
        app = create_app()
        set_app_config(config)
        
        # Start STDIN server for Home Assistant communication
        stdin_thread = start_stdin_server(config)
        
        # Log startup info
        logger.info(f"HTTP API will be available at http://0.0.0.0:{config.port}")
        logger.info("STDIN server ready for Home Assistant commands")
        
        # Start HTTP server
        uvicorn.run(
            app,
            host="0.0.0.0",
            port=config.port,
            log_config=None,  # Use our custom logging
            access_log=False  # Disable access logs to reduce noise
        )
        
    except Exception as e:
        logger.error(f"Failed to start application: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()