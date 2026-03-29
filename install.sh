#!/bin/bash

# Install system dependencies for PyAudio
echo "Installing system dependencies..."
sudo apt update
sudo apt install -y python3-dev portaudio19-dev

# Install Python requirements
echo "Installing Python requirements..."
pip install -r requirements.txt

echo "Installation complete!"
