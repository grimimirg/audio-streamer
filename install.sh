#!/bin/bash

set -euo pipefail

# Install system dependencies that pip cannot provide:
#   python headers + portaudio -> building PyAudio
#   ffmpeg                     -> bitrate conversion
#   libmagic                   -> upload validation in Liquid Music mode
echo "Installing system dependencies..."

if command -v apt >/dev/null 2>&1; then
    sudo apt update
    sudo apt install -y python3-dev portaudio19-dev ffmpeg libmagic1
elif command -v pacman >/dev/null 2>&1; then
    sudo pacman -S --needed --noconfirm python portaudio ffmpeg file
else
    echo "Error: no supported package manager found (apt, pacman)." >&2
    echo "Install the prerequisites listed in the README manually, then run:" >&2
    echo "  pip install -r requirements.txt" >&2
    exit 1
fi

# Install Python requirements
echo "Installing Python requirements..."
pip install -r requirements.txt

echo "Installation complete!"
