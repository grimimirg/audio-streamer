import queue
import logging
import time
from flask import Flask, render_template, Response


class AudioHttpFacade:
    """HTTP interface for audio streaming using Flask.
    
    Provides web interface and streaming endpoints for audio distribution.
    Handles client connections and audio data delivery with proper error handling.
    """
    
    def __init__(self, audioStreamer):
        """Initialize the HTTP facade with audio streaming backend.
        
        Args:
            audioStreamer: Instance of AudioStreamer for audio capture
        """
        self.app = Flask(__name__)
        self.audioStreamer = audioStreamer
        self._add_routes()
        logging.basicConfig(level=logging.INFO)

    def run(self, host: str, port: int, debug: bool):
        """Start the Flask HTTP server.
        
        Args:
            host: Host address to bind to
            port: Port number to listen on
            debug: Enable Flask debug mode
        """
        logging.info(f"Server listening on http://{host}:{port}")
        self.app.run(host=host, port=port, debug=debug, threaded=True)

    # -- PRIVATES --

    def _add_routes(self):
        """Configure Flask URL routes for the application."""
        self.app.add_url_rule('/', 'player', self._player)
        self.app.add_url_rule('/stream', 'stream', self._stream)
        self.app.add_url_rule('/stats', 'stats', self._stats)

    def _generateAudioStream(self):
        """Generate audio stream data for HTTP response.
        
        Creates a client queue, registers it with the audio streamer,
        and yields audio chunks as they become available.
        
        Yields:
            bytes: Raw audio data chunks
        """
        clientQueue = queue.Queue(maxsize=100)
        self.audioStreamer.addClient(clientQueue)
        logging.info("New audio stream client connected")

        try:
            while True:
                try:
                    # Use timeout to prevent indefinite blocking
                    data = clientQueue.get(timeout=1.0)
                    yield data
                except queue.Empty:
                    # Check if streaming is still active
                    if not self.audioStreamer.onAir:
                        logging.info("Audio streaming stopped, closing client connection")
                        break
                    # Continue waiting for data
                    continue
                    
        except GeneratorExit:
            logging.info("Client disconnected from audio stream")
        finally:
            # Ensure client is removed even on errors
            self.audioStreamer.removeClient(clientQueue)

    def _player(self):
        """Serve the main web player interface.
        
        Returns:
            str: Rendered HTML template for the audio player
        """
        return render_template('index.html')

    def _stream(self):
        """Serve the audio streaming endpoint.
        
        Returns:
            Response: Flask response with audio stream data
        """
        return Response(
            self._generateAudioStream(),
            mimetype='audio/raw'  # Correct mimetype for raw PCM data
        )

    def _stats(self):
        """Serve streaming statistics endpoint.
        
        Returns:
            dict: Current streaming statistics as JSON
        """
        return self.audioStreamer.getStats()
