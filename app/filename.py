"""Filename templating and sanitization for scanner outputs."""

import re
from datetime import datetime
from pathlib import Path
from typing import Dict, Any


def sanitize_filename(filename: str) -> str:
    """Sanitize filename to prevent path traversal and illegal characters."""
    # Remove path separators and illegal characters
    filename = re.sub(r'[<>:"|?*\\\/]', '_', filename)
    # Remove control characters
    filename = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', filename)
    # Remove dots at the end and spaces
    filename = filename.rstrip('. ')
    # Ensure it's not empty
    if not filename:
        filename = 'scan'
    return filename


def format_filename(
    pattern: str,
    page: int,
    output_format: str,
    device_id: str = "",
    **kwargs
) -> str:
    """Format filename using template pattern."""
    now = datetime.now()
    
    template_vars = {
        'date': now.strftime('%Y-%m-%d'),
        'time': now.strftime('%H-%M-%S'),
        'datetime': now.strftime('%Y-%m-%d_%H-%M-%S'),
        'timestamp': str(int(now.timestamp())),
        'page': str(page),
        'device_id': sanitize_filename(device_id.split(':')[-1] if device_id else 'unknown'),
        'format': output_format,
        **kwargs
    }
    
    try:
        formatted = pattern.format(**template_vars)
        return sanitize_filename(formatted)
    except (KeyError, ValueError) as e:
        # Fallback to safe default if template fails
        return f"scan_{template_vars['datetime']}_{page}.{output_format}"


def ensure_unique_filename(base_path: Path, filename: str) -> Path:
    """Ensure filename is unique by appending counter if needed."""
    file_path = base_path / filename
    
    if not file_path.exists():
        return file_path
    
    # Extract name and extension
    stem = file_path.stem
    suffix = file_path.suffix
    
    counter = 1
    while True:
        new_filename = f"{stem}-{counter}{suffix}"
        new_path = base_path / new_filename
        if not new_path.exists():
            return new_path
        counter += 1