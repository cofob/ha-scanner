#!/bin/bash
# ==============================================================================
# Run the scanner application
# ==============================================================================

set -e

cd /opt/scanner

# Optional: Print libinsane/SANE diagnostics (if available)
echo "Checking scanner environment..."
if command -v sane-find-scanner &> /dev/null; then
    echo "Available SANE devices:"
    sane-find-scanner 2>/dev/null || echo "No SANE devices found or permission denied"
fi

# Start the Python application
echo "Starting Scanner Add-on service..."
python3 -m app.main