import os
import queue
import yaml
import uuid
import shutil
from flask import Flask, render_template, Response, jsonify, send_from_directory, request
from flask_socketio import SocketIO, emit
from dotenv import load_dotenv
from werkzeug.utils import secure_filename

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
        upload_dir = os.path.join(root_dir, 'uploads', 'covers')

        # Create upload directory if it doesn't exist
        os.makedirs(upload_dir, exist_ok=True)

        self.app = Flask(__name__,
                         template_folder=template_dir,
                         static_folder=static_dir)
        self.app.config['SECRET_KEY'] = 'audio-streamer-secret-key'
        self.app.config['UPLOAD_FOLDER'] = upload_dir
        self.app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
        self.socketio = SocketIO(self.app, cors_allowed_origins="*")
        self.audioStreamer = audioStreamer
        self.locales_dir = os.path.join(root_dir, 'locales')
        self.radio_station_name = os.getenv('RADIO_STATION_NAME', 'My Radio Station')
        self.track_info = {'artist': '', 'track_title': '', 'album_name': '', 'track_year': '', 'album_cover': ''}
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
        self.app.add_url_rule('/upload_cover', 'upload_cover', self._upload_cover, methods=['POST'])
        self.app.add_url_rule('/uploads/covers/<filename>', 'uploaded_cover', self._uploaded_cover)

    def _add_socketio_events(self):
        """Configure SocketIO event handlers for real-time updates."""
        @self.socketio.on('connect')
        def handle_connect():
            Logger.info('WebSocket client connected')
            # Send initial stats on connection
            emit('stats', self._get_stats_with_track_info())

        @self.socketio.on('disconnect')
        def handle_disconnect():
            Logger.info('WebSocket client disconnected')

        @self.socketio.on('request_stats')
        def handle_request_stats():
            emit('stats', self._get_stats_with_track_info())

        @self.socketio.on('update_track_info')
        def handle_update_track_info(data):
            """Handle track info updates from dashboard."""
            self.track_info['artist'] = data.get('artist', '')
            self.track_info['track_title'] = data.get('track_title', '')
            self.track_info['album_name'] = data.get('album_name', '')
            self.track_info['track_year'] = data.get('track_year', '')
            self.track_info['album_cover'] = data.get('album_cover', '')
            Logger.info(f"Track info updated: {self.track_info}")
            # Broadcast updated stats to all WebSocket clients
            self.socketio.emit('stats', self._get_stats_with_track_info())

    def _get_stats_with_track_info(self):
        """Get audio stats combined with track info."""
        stats = self.audioStreamer.getStats()
        stats['artist'] = self.track_info['artist']
        stats['track_title'] = self.track_info['track_title']
        stats['album_name'] = self.track_info['album_name']
        stats['track_year'] = self.track_info['track_year']
        stats['album_cover'] = self.track_info['album_cover']
        return stats

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
        # Broadcast updated stats to all WebSocket clients
        self.socketio.emit('stats', self._get_stats_with_track_info())

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
            # Broadcast updated stats to all WebSocket clients
            self.socketio.emit('stats', self._get_stats_with_track_info())

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
        return self._get_stats_with_track_info()

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

    def _upload_cover(self):
        """Handle album cover image upload.
        
        Returns:
            dict: JSON response with the URL of the uploaded image
        """
        try:
            if 'cover' not in request.files:
                return jsonify({'error': 'No file provided'}), 400

            file = request.files['cover']

            if file.filename == '':
                return jsonify({'error': 'No file selected'}), 400

            if file:
                # Clear existing files in upload folder
                upload_folder = self.app.config['UPLOAD_FOLDER']
                if os.path.exists(upload_folder):
                    for filename in os.listdir(upload_folder):
                        file_path = os.path.join(upload_folder, filename)
                        try:
                            if os.path.isfile(file_path):
                                os.unlink(file_path)
                        except Exception as e:
                            Logger.error(f"Error deleting file {file_path}: {e}")

                # Generate unique filename
                filename = secure_filename(file.filename)
                unique_filename = f"{uuid.uuid4().hex}_{filename}"
                filepath = os.path.join(self.app.config['UPLOAD_FOLDER'], unique_filename)

                # Save file
                file.save(filepath)

                # Return URL
                url = f"/uploads/covers/{unique_filename}"
                Logger.info(f"Cover image uploaded: {url}")
                return jsonify({'url': url})

        except Exception as e:
            Logger.error(f"Error uploading cover: {e}")
            return jsonify({'error': 'Failed to upload file'}), 500

    def _uploaded_cover(self, filename):
        """Serve uploaded cover images.
        
        Args:
            filename: Name of the file to serve
            
        Returns:
            File: The requested image file
        """
        try:
            return send_from_directory(self.app.config['UPLOAD_FOLDER'], filename)
        except Exception as e:
            Logger.error(f"Error serving cover {filename}: {e}")
            return jsonify({'error': 'File not found'}), 404
