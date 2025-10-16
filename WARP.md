# WARP.md

This file provides guidance to WARP (warp.dev) when working with code in this repository.

## Common Commands

### Environment Setup
- `uv sync` - Install dependencies and create virtual environment
- `uv run python main.py` - Run the scanner application

### Running the Application
- `uv run python main.py --list` - List available scanner devices
- `uv run python main.py --scan` - Scan document using first available scanner
- `uv run python main.py --scan --printer DEVICE_ID --output filename.png` - Scan with specific device and output
- `uv run python main.py --scan --output scan_{dateandtime}.{format_suffix} --format jpeg` - Use templated output filename

### Development
- `python main.py` - Direct execution (requires activated environment)
- `uv run python -c "import gi; gi.require_version('Libinsane', '1.0'); print('Dependencies OK')"` - Test libinsane setup

## Architecture

This is a single-file CLI application (`main.py`) that provides scanner functionality through the libinsane library via PyGObject bindings. The application has two primary operations:

1. **Device Discovery** (`--list`): Lists available scanner devices using `api.list_devices()`
2. **Document Scanning** (`--scan`): Captures document images and saves them in PNG or JPEG format

### Key Components
- **libinsane Integration**: Uses `gi.repository.Libinsane` for scanner hardware access
- **Image Processing**: PIL/Pillow for image format conversion and saving
- **CLI Interface**: argparse-based command-line parsing
- **Output Templating**: Supports filename templates with `{dateandtime}`, `{page}`, and `{format_suffix}` placeholders

### Code Flow
- Scanner session management in `scan_document()` handles multi-page scanning
- Raw RGB24 image data is converted to PIL Image objects
- Error handling includes device availability checks and scan parameter validation

## Project-Specific Notes

### Dependencies
- Requires Python ≥ 3.13
- Uses uv for dependency management (see `uv.lock`)
- Core dependencies: PIL/Pillow, PyGObject (for libinsane bindings)

### System Requirements
- libinsane must be available on the system for scanner hardware access
- Scanner devices need proper permissions/drivers installed
- Image format support limited to PNG and JPEG output

### File Structure
- `main.py`: Complete application logic
- `pyproject.toml`: Project configuration and dependencies
- `uv.lock`: Locked dependency versions
- No test suite currently present

### Output Handling
- Supports stdout output with `--output -`
- Template variables in output paths are dynamically replaced
- Multi-page scanning increments page counter automatically