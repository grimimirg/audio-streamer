import logging
import os
import queue

from flask import Flask, render_template, Response

from utilities.Constants import CLIENT_QUEUE_SIZE


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
        # Get the project root directory (parent of classes folder)
        template_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'templates')
        self.app = Flask(__name__, template_folder=template_dir)
        self.audioStreamer = audioStreamer
        self._add_routes()

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
        clientQueue = queue.Queue(maxsize=CLIENT_QUEUE_SIZE)
        self.audioStreamer.addClient(clientQueue)
        logging.info("New audio stream client connected")

        try:
            chunkCount = 0
            while True:
                try:
                    # Use timeout to prevent indefinite blocking
                    data = clientQueue.get(timeout=1.0)
                    chunkCount += 1
                    logging.info(f"Yielding chunk {chunkCount}: {len(data)} bytes")
                    yield data
                except queue.Empty:
                    # Check if streaming is still active
                    if not self.audioStreamer.onAir:
                        logging.info("Audio streaming stopped, closing client connection")
                        break
                    # Continue waiting for data
                    logging.warning(f"Queue empty, waiting... (stream active: {self.audioStreamer.onAir})")
                    continue
                except Exception as e:
                    logging.error(f"Error while getting data from queue: {type(e).__name__}: {str(e)}")
                    break

        except GeneratorExit:
            logging.info("Client disconnected from audio stream")
        except Exception as e:
            logging.error(f"Unexpected error in audio stream generator: {type(e).__name__}: {str(e)}")
        finally:
            # Ensure client is removed even on errors
            self.audioStreamer.removeClient(clientQueue)
            logging.debug("Client queue removed from audio streamer")

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
        # Generate WAV header for streaming
        import struct
        
        def generate_wav_stream():
            # WAV header for 44100 Hz, 16-bit, stereo
            sample_rate = 44100
            channels = 2
            bits_per_sample = 16
            byte_rate = sample_rate * channels * bits_per_sample // 8
            block_align = channels * bits_per_sample // 8
            
            # Simple WAV header
            header = struct.pack('<4sL4s', b'RIFF', 0, b'WAVE')
            header += struct.pack('<4sLHHLLHH4sL', 
                                b'fmt ', 16, 1, channels, sample_rate, 
                                byte_rate, block_align, bits_per_sample, b'data', 0)
            
            yield header
            
            # Stream audio data
            for chunk in self._generateAudioStream():
                yield chunk
        
        return Response(
            generate_wav_stream(),
            mimetype='audio/wav',
            headers={
                'Cache-Control': 'no-cache',
                'Connection': 'keep-alive',
                'Access-Control-Allow-Origin': '*'
            }
        )

    def _stats(self):
        """Serve streaming statistics endpoint.
        
        Returns:
            dict: Current streaming statistics as JSON
        """
        return self.audioStreamer.getStats()
