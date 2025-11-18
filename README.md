# Audio Streamer

Stream audio from a source

## Description

Audio Streamer is a Python application that captures audio from your physical audio sources and streams it over HTTP. Anyone can listen to the stream through a web browser.

Perfect for creating a personal internet radio station, or broadcasting live music sessions.

## Installation

### Prerequisites

*   Python 3.7 or higher
*   An audio input device (USB audio interface, line-in, etc.)
*   Your audio source connected to the computer

### Install Dependencies

`pip install -r requirements.txt`

**Note for Windows users:** Installing PyAudio might require Microsoft Visual C++ 14.0 or greater. Alternatively, download a pre-compiled wheel from [here](https://www.lfd.uci.edu/~gohlke/pythonlibs/#pyaudio).

## Usage

1 **Connect your audio source**

Connect your turntable, cassette deck, or amplifier to your computer's audio input (line-in, USB audio interface, etc.)

2 **Start the server**

`python app.py`

3 **Select your audio device**

The application will list all available audio input devices. Enter the number corresponding to your audio source, or press ENTER to use the default device.

4 **Open the player**

Open your web browser and navigate to:

`http://localhost:4986`

5 **Start listening**

Click the Play button in the web interface to start streaming. Share the URL with friends to let them listen too!

## Remote Access

To allow people outside your local network to listen:

*   Configure port forwarding on your router (forward port 4986)
*   Share your public IP address with listeners

## Stopping the Server

Press `Ctrl+C` in the terminal to gracefully stop the streaming server.

## Tips

*   Adjust your amplifier/source volume to avoid distortion
*   Test the audio levels before sharing with listeners
*   The stream URL is: `http://your-address:4986/stream`
*   Check listener count at: `http://your-address:4986/stats`

## Technical Details

*   **Sample Rate:** 44.1 kHz (CD quality)
*   **Channels:** 2 (Stereo)
*   **Format:** WAV (uncompressed)
*   **Port:** 4986 (HTTP)
