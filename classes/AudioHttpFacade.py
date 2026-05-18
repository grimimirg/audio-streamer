import os
import queue
import yaml
from flask import Flask, render_template, Response, jsonify, send_from_directory
from flask_socketio import SocketIO, emit
from dotenv import load_dotenv

from utilities.Constants import CLIENT_QUEUE_SIZE
from utilities.Logger import Logger


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
        # Load environment variables from .env file
        root_dir = os.path.dirname(os.path.dirname(__file__))
        env_file = os.path.join(root_dir, '.env')
        load_dotenv(env_file)

        # Get the project root directory (parent of classes folder)
        template_dir = os.path.join(root_dir, 'templates')
        static_dir = os.path.join(root_dir, 'static')

        self.app = Flask(__name__,
                         template_folder=template_dir,
                         static_folder=static_dir)
        self.app.config['SECRET_KEY'] = 'audio-streamer-secret-key'
        self.socketio = SocketIO(self.app, cors_allowed_origins="*")
        self.audioStreamer = audioStreamer
        self.locales_dir = os.path.join(root_dir, 'locales')
        self.radio_station_name = os.getenv('RADIO_STATION_NAME', 'My Radio Station')
        self._add_routes()
        self._add_socketio_events()

    def run(self, host: str, port: int, debug: bool):
        """Start the Flask HTTP server.
        
        Args:
            host: Host address to bind to
            port: Port number to listen on
            debug: Enable Flask debug mode
        """
        Logger.info(f"Server listening on http://{host}:{port}")
        self.socketio.run(self.app, host=host, port=port, debug=debug, allow_unsafe_werkzeug=True)

    # -- PRIVATES --

    def _add_routes(self):
        """Configure Flask URL routes for the application."""
        self.app.add_url_rule('/', 'player', self._player)
        self.app.add_url_rule('/stream', 'stream', self._stream)
        self.app.add_url_rule('/stats', 'stats', self._stats)
        self.app.add_url_rule('/dashboard', 'dashboard', self._dashboard)
        self.app.add_url_rule('/locales/<lang>', 'locales', self._get_locale)

    def _add_socketio_events(self):
        """Configure SocketIO event handlers for real-time updates."""
        @self.socketio.on('connect')
        def handle_connect():
            Logger.info('WebSocket client connected')
            # Send initial stats on connection
            emit('stats', self.audioStreamer.getStats())

        @self.socketio.on('disconnect')
        def handle_disconnect():
            Logger.info('WebSocket client disconnected')

        @self.socketio.on('request_stats')
        def handle_request_stats():
            emit('stats', self.audioStreamer.getStats())

    def _generateAudioStream(self):
        """Generate audio stream data for HTTP response.

        Creates a client queue, registers it with the audio streamer,
        and yields audio chunks as they become available.

        Yields:
            bytes: Raw audio data chunks
        """
        clientQueue = queue.Queue(maxsize=CLIENT_QUEUE_SIZE)
        self.audioStreamer.addClient(clientQueue)
        Logger.info("New audio stream client connected")

        try:
            chunkCount = 0
            while True:
                try:
                    # Use timeout to prevent indefinite blocking
                    data = clientQueue.get(timeout=1.0)
                    chunkCount += 1
                    # For debug purposes
                    # Logger.info(f"Yielding chunk {chunkCount}: {len(data)} bytes")
                    yield data
                except queue.Empty:
                    # Check if streaming is still active
                    if not self.audioStreamer.onAir:
                        Logger.info("Audio streaming stopped, closing client connection")
                        break
                    # Continue waiting for data
                    Logger.warning(f"Queue empty, waiting... (stream active: {self.audioStreamer.onAir})")
                    continue
                except Exception as e:
                    Logger.error(f"Error while getting data from queue: {type(e).__name__}: {str(e)}")
                    break

        except GeneratorExit:
            Logger.info("Client disconnected from audio stream")
        except Exception as e:
            Logger.error(f"Unexpected error in audio stream generator: {type(e).__name__}: {str(e)}")
        finally:
            # Ensure client is removed even on errors
            self.audioStreamer.removeClient(clientQueue)
            Logger.debug("Client queue removed from audio streamer")

    def _player(self):
        """Serve the main web player interface.
        
        Returns:
            str: Rendered HTML template for the audio player
        """
        return render_template('index.html', radio_station_name=self.radio_station_name)

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

    def _dashboard(self):
        """Serve the dashboard interface.
        
        Returns:
            str: Rendered HTML template for the dashboard
        """
        return render_template('dashboard.html', radio_station_name=self.radio_station_name)

    def _get_locale(self, lang):
        """Serve translation files as JSON.
        
        Args:
            lang: Language code (it, en, de)
            
        Returns:
            dict: Translation data as JSON
        """
        try:
            locale_file = os.path.join(self.locales_dir, f'{lang}.yaml')
            if not os.path.exists(locale_file):
                return jsonify({'error': 'Language not found'}), 404

            with open(locale_file, 'r', encoding='utf-8') as f:
                translations = yaml.safe_load(f)

            return jsonify(translations)
        except Exception as e:
            Logger.error(f"Error loading locale {lang}: {e}")
            return jsonify({'error': 'Failed to load translations'}), 500
