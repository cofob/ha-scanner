#!/bin/bash
# ==============================================================================
# STDIN bridge for hassio.addon_stdin
# ==============================================================================

set -e

cd /opt/scanner

echo "Starting Scanner Add-on STDIN bridge..."
exec python3 -u /opt/scanner/app/stdin_bridge.py
