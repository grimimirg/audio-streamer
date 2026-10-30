#!/bin/bash

set -euo pipefail

cd "$(dirname "$0")"

VENV_DIR="venv"

# Install system dependencies that pip cannot provide:
#   python headers + portaudio -> building PyAudio
#   ffmpeg                     -> bitrate conversion
#   libmagic                   -> upload validation in Liquid Music mode
#   libshout headers           -> building python-shout for Icecast streaming
echo "Installing system dependencies..."

if command -v apt >/dev/null 2>&1; then
    sudo apt update
    sudo apt install -y python3-dev python3-venv portaudio19-dev ffmpeg libmagic1 \
        libshout3-dev pkg-config
elif command -v pacman >/dev/null 2>&1; then
    sudo pacman -S --needed --noconfirm python portaudio ffmpeg file libshout pkgconf
else
    echo "Error: no supported package manager found (apt, pacman)." >&2
    echo "Install the prerequisites listed in the README manually, then run:" >&2
    echo "  python3 -m venv venv && ./venv/bin/pip install -r requirements.txt" >&2
    exit 1
fi

# Install the Python requirements into a virtual environment. A global install
# is refused outright by Arch and by Debian 12+ / Ubuntu 23.04+ (PEP 668).
if [ -d "$VENV_DIR" ]; then
    echo "Reusing existing virtual environment in $VENV_DIR/..."
else
    echo "Creating virtual environment in $VENV_DIR/..."
    python3 -m venv "$VENV_DIR"
fi

echo "Installing Python requirements..."
"$VENV_DIR/bin/pip" install -r requirements.txt

# The application refuses to start without .env
if [ ! -f .env ]; then
    cp .env.example .env
    echo "Created .env from .env.example - edit it with your settings before starting."
fi

echo "Installation complete! Start the station with ./startup.sh"
