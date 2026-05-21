import os
from functools import wraps
from dotenv import load_dotenv
from flask import Flask, Response, jsonify, request, send_from_directory
from flask_socketio import SocketIO, emit

from classes.handlers.AuthHandler import AuthHandler
from classes.handlers.CoverUploadHandler import CoverUploadHandler
from classes.handlers.LiquidMusicHandler import LiquidMusicHandler
from classes.handlers.LocalizationHandler import LocalizationHandler
from classes.handlers.StreamHandler import StreamHandler
from utilities.Logger import Logger


class AudioHttpFacade:
    """HTTP interface for audio streaming using Flask.
    
    Provides web interface and streaming endpoints for audio distribution.
    Handles client connections and audio data delivery with proper error handling.
    """

    def __init__(self, audioStreamer, input_method=None):
        """Initialize the HTTP facade with audio streaming backend.
        
        Args:
            audioStreamer: Instance of AudioStreamer for audio capture
            input_method: The input method selected (microphone, interface, or liquid_music)
        """
        # Load environment variables from .env file
        root_dir = os.path.dirname(os.path.dirname(__file__))
        env_file = os.path.join(root_dir, '.env')
        load_dotenv(env_file)

        # Get the project root directory (parent of classes folder)
        template_dir = os.path.join(root_dir, 'html-client', 'templates')
        static_dir = os.path.join(root_dir, 'html-client', 'static')
        self.js_dir = os.path.join(root_dir, 'html-client', 'src')
        upload_dir = os.path.join(root_dir, 'uploads', 'covers')
        locales_dir = os.path.join(root_dir, 'locales')

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
        self.input_method = input_method
        self.radio_station_name = os.getenv('RADIO_STATION_NAME', 'My Radio Station')
        self.dashboard_username = os.getenv('DASHBOARD_USERNAME', 'admin')
        self.dashboard_password = os.getenv('DASHBOARD_PASSWORD', 'admin123')
        self.track_info = {'artist': '', 'track_title': '', 'album_name': '', 'track_year': '', 'album_cover': ''}

        # Initialize handlers
        self.auth_handler = AuthHandler(self.dashboard_username, self.dashboard_password)
        self.cover_handler = CoverUploadHandler(upload_dir)
        self.localization_handler = LocalizationHandler(locales_dir)
        self.stream_handler = StreamHandler(audioStreamer, self.radio_station_name)
        self.liquid_music_handler = LiquidMusicHandler(audioStreamer, self.socketio)

        # Register callback for listener count changes
        if hasattr(audioStreamer, 'set_listener_callback'):
            audioStreamer.set_listener_callback(self._notify_listener_change)

        # Clear upload folders and setup
        self.cover_handler.clear_upload_folder()
        self.liquid_music_handler.clear_upload_folder()
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

    def _requires_auth(self, f):
        """Decorator to require HTTP Basic Authentication for a route.

        Args:
            f: The function to decorate

        Returns:
            The decorated function
        """
        return self.auth_handler.requires_auth(f)

    def _requires_liquid_mode(self, f):
        """Decorator to require Liquid Music mode for dashboard access.

        Args:
            f: The function to decorate

        Returns:
            The decorated function
        """

        @wraps(f)
        def decorated_function(*args, **kwargs):
            if self.input_method != 'liquid_music':
                return jsonify({
                    'error': 'Access denied',
                    'message': 'The Liquid Music Dashboard is only available when the application is started in Liquid Music mode (option 3). '
                               'To use this dashboard, please restart the application and select option 3 (Liquid Music) when prompted for the audio input method.'
                }), 403
            return f(*args, **kwargs)

        return decorated_function

    def _requires_streaming_mode(self, f):
        """Decorator to require streaming mode (microphone or interface) for dashboard access.

        Args:
            f: The function to decorate

        Returns:
            The decorated function
        """

        @wraps(f)
        def decorated_function(*args, **kwargs):
            if self.input_method == 'liquid_music':
                return jsonify({
                    'error': 'Access denied',
                    'message': 'The regular Dashboard is only available when the application is started in streaming mode (option 1 or 2). '
                               'To use this dashboard, please restart the application and select option 1 (Microphone) or option 2 (Audio Interface) when prompted for the audio input method.'
                }), 403
            return f(*args, **kwargs)

        return decorated_function

    def _add_routes(self):
        """Configure Flask URL routes for the application."""
        # Standard routes
        self.app.add_url_rule('/', 'player', self.stream_handler.player)
        self.app.add_url_rule('/stream', 'stream', self.stream_handler.stream)
        self.app.add_url_rule('/stats', 'stats', self._stats)
        self.app.add_url_rule('/dashboard', 'dashboard',
                              self._requires_auth(self._requires_streaming_mode(self.stream_handler.dashboard)))
        self.app.add_url_rule('/dashboard_liquid', 'dashboard_liquid',
                              self._requires_auth(self._requires_liquid_mode(self.stream_handler.dashboard_liquid)))
        self.app.add_url_rule('/locales/<lang>', 'locales', self.localization_handler.get_locale)
        self.app.add_url_rule('/upload_cover', 'upload_cover', self._requires_auth(self._upload_cover),
                              methods=['POST'])
        self.app.add_url_rule('/uploads/covers/<filename>', 'uploaded_cover', self.cover_handler.serve_cover)
        self.app.add_url_rule('/streamer_type', 'streamer_type', self._streamer_type)

        # Liquid Music routes
        self.app.add_url_rule('/liquid/upload_track', 'upload_track',
                              self._requires_auth(self.liquid_music_handler.upload_track), methods=['POST'])
        self.app.add_url_rule('/liquid/play', 'play', self._requires_auth(self.liquid_music_handler.play),
                              methods=['POST'])
        self.app.add_url_rule('/liquid/stop', 'stop', self._requires_auth(self.liquid_music_handler.stop),
                              methods=['POST'])
        self.app.add_url_rule('/liquid/pause', 'pause', self._requires_auth(self.liquid_music_handler.pause),
                              methods=['POST'])
        self.app.add_url_rule('/liquid/resume', 'resume', self._requires_auth(self.liquid_music_handler.resume),
                              methods=['POST'])
        self.app.add_url_rule('/liquid/skip_forward', 'skip_forward',
                              self._requires_auth(self.liquid_music_handler.skip_forward), methods=['POST'])
        self.app.add_url_rule('/liquid/skip_backward', 'skip_backward',
                              self._requires_auth(self.liquid_music_handler.skip_backward), methods=['POST'])
        self.app.add_url_rule('/liquid/set_local_path', 'set_local_path',
                              self._requires_auth(self.liquid_music_handler.set_local_path), methods=['POST'])
        self.app.add_url_rule('/liquid/stop_scan', 'stop_scan',
                              self._requires_auth(self.liquid_music_handler.stop_scan), methods=['POST'])
        self.app.add_url_rule('/liquid/list_directories', 'list_directories',
                              self._requires_auth(self.liquid_music_handler.list_directories), methods=['POST'])
        self.app.add_url_rule('/liquid/playlist', 'playlist',
                              self._requires_auth(self.liquid_music_handler.get_playlist))
        self.app.add_url_rule('/liquid/stack', 'stack', self._requires_auth(self.liquid_music_handler.get_stack))
        self.app.add_url_rule('/liquid/remove_track', 'remove_track',
                              self._requires_auth(self.liquid_music_handler.remove_track), methods=['POST'])

        # Serve JavaScript files from html-client/src
        self.app.add_url_rule('/js/<path:filename>', 'serve_js', self._serve_js)

    def _add_socketio_events(self):
        """Configure SocketIO event handlers for real-time updates."""

        @self.socketio.on('connect')
        def handle_connect(data=None):
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
        stats = self.stream_handler.stats()
        stats['artist'] = self.track_info['artist']
        stats['track_title'] = self.track_info['track_title']
        stats['album_name'] = self.track_info['album_name']
        stats['track_year'] = self.track_info['track_year']
        stats['album_cover'] = self.track_info['album_cover']
        return stats

    def _upload_cover(self):
        """Handle album cover image upload."""
        if 'cover' not in request.files:
            return {'error': 'No file provided'}, 400
        return self.cover_handler.upload_cover(request.files['cover'])

    def _stats(self):
        """Serve streaming statistics endpoint."""
        return self._get_stats_with_track_info()

    def _streamer_type(self):
        """Get the current streamer type."""
        return jsonify(self.stream_handler.streamer_type())

    def _serve_js(self, filename):
        """Serve JavaScript files from html-client/src directory."""
        return send_from_directory(self.js_dir, filename)

    def _notify_listener_change(self):
        """Notify all WebSocket clients when listener count changes."""
        self.socketio.emit('stats', self._get_stats_with_track_info())
