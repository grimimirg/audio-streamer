import os
import uuid
import magic
from flask import jsonify, request
from werkzeug.utils import secure_filename
from mutagen import File
from mutagen.id3 import ID3NoHeaderError

from utilities.Logger import Logger
from classes.streamer.streamers.LiquidMusicStreamer import LiquidMusicStreamer


class LiquidMusicHandler:
    """Handles Liquid Music specific endpoints and functionality."""

    def __init__(self, audio_streamer, socketio):
        """Initialize the Liquid Music handler.
        
        Args:
            audio_streamer: Instance of the audio streamer
            socketio: SocketIO instance for real-time updates
        """
        self.audio_streamer = audio_streamer
        self.socketio = socketio
        self.upload_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'uploads', 'music')
        os.makedirs(self.upload_dir, exist_ok=True)
        
        # Allowed MIME types for audio files
        self.allowed_mime_types = {
            'audio/mpeg',
            'audio/mp3',
            'audio/wav',
            'audio/wave',
            'audio/x-wav',
            'audio/flac',
            'audio/x-flac',
            'audio/ogg',
            'audio/x-ogg',
            'audio/x-m4a',
            'audio/mp4',
            'audio/x-m4p'
        }
        
        # Maximum file size (50 MB)
        self.max_file_size = 50 * 1024 * 1024

    def clear_upload_folder(self):
        """Clear all uploaded audio files from the upload folder."""
        if os.path.exists(self.upload_dir):
            for filename in os.listdir(self.upload_dir):
                file_path = os.path.join(self.upload_dir, filename)
                try:
                    if os.path.isfile(file_path):
                        os.unlink(file_path)
                        Logger.info(f"Deleted old uploaded track: {file_path}")
                except Exception as e:
                    Logger.error(f"Error deleting file {file_path}: {e}")
            Logger.info("Upload folder for tracks cleared at application startup")

    def _validate_audio_file(self, file, filepath):
        """Validate that the uploaded file is a genuine audio file.
        
        Performs low-level validation using magic bytes and mutagen to ensure
        the file is actually an audio file and doesn't contain malicious content.
        
        Args:
            file: The uploaded file object
            filepath: Path where the file has been saved
            
        Returns:
            tuple: (is_valid, error_message)
        """
        # Check file size
        file.seek(0, os.SEEK_END)
        file_size = file.tell()
        file.seek(0)
        
        if file_size > self.max_file_size:
            return False, f'File too large. Maximum size is {self.max_file_size / (1024*1024)} MB'
        
        if file_size == 0:
            return False, 'File is empty'
        
        # Check MIME type using magic bytes
        try:
            mime = magic.from_file(filepath, mime=True)
            if mime not in self.allowed_mime_types:
                Logger.warning(f"Invalid MIME type: {mime}")
                return False, f'Invalid file type. Detected: {mime}'
        except Exception as e:
            Logger.error(f"Error detecting MIME type: {e}")
            return False, 'Could not determine file type'
        
        # Validate using mutagen to ensure it's a valid audio file
        try:
            audio_file = File(filepath)
            if audio_file is None:
                return False, 'Invalid audio file format'
            
            # Check if the file has audio properties
            if hasattr(audio_file, 'info'):
                info = audio_file.info
                if not hasattr(info, 'length') or info.length <= 0:
                    return False, 'Invalid audio file: no valid duration'
        except (ID3NoHeaderError, Exception) as e:
            Logger.error(f"Error validating audio file: {e}")
            return False, 'File is not a valid audio file'
        
        # Check for suspicious content (basic check for executable patterns)
        try:
            with open(filepath, 'rb') as f:
                header = f.read(1024)
                # Check for MZ header (Windows executable)
                if header[:2] == b'MZ':
                    return False, 'File appears to be an executable, not an audio file'
                # Check for ELF header (Linux executable)
                if header[:4] == b'\x7fELF':
                    return False, 'File appears to be an executable, not an audio file'
                # Check for script shebangs
                if header.startswith(b'#!/') or header.startswith(b'#!/'):
                    return False, 'File appears to be a script, not an audio file'
        except Exception as e:
            Logger.error(f"Error checking for suspicious content: {e}")
            return False, 'Could not verify file content'
        
        return True, None

    def upload_track(self):
        """Handle audio file upload for liquid music with security validation."""
        try:
            if 'track' not in request.files:
                return jsonify({'error': 'No file provided'}), 400

            file = request.files['track']

            if file.filename == '':
                return jsonify({'error': 'No file selected'}), 400

            # Check if it's an audio file (extension check as first filter)
            allowed_extensions = {'.mp3', '.wav', '.flac', '.ogg', '.m4a'}
            file_ext = os.path.splitext(file.filename)[1].lower()
            if file_ext not in allowed_extensions:
                return jsonify({'error': 'Invalid file type. Allowed: mp3, wav, flac, ogg, m4a'}), 400

            if file:
                # Generate unique filename
                filename = secure_filename(file.filename)
                unique_filename = f"{uuid.uuid4().hex}_{filename}"
                
                filepath = os.path.join(self.upload_dir, unique_filename)

                # Save file temporarily for validation
                file.save(filepath)

                # Perform security validation
                is_valid, error_message = self._validate_audio_file(file, filepath)
                if not is_valid:
                    # Delete the invalid file
                    if os.path.exists(filepath):
                        os.remove(filepath)
                    Logger.warning(f"File validation failed: {error_message}")
                    return jsonify({'error': error_message}), 400

                # Add to playlist
                if hasattr(self.audio_streamer, 'addTrackToPlaylist'):
                    self.audio_streamer.addTrackToPlaylist(filepath)
                    Logger.info(f"Track uploaded and added to playlist: {filepath}")
                    
                    # Broadcast updated stats
                    self._broadcast_stats()
                    
                    return jsonify({'success': True, 'filename': filename, 'path': filepath})
                else:
                    # Delete the file if streamer doesn't support playlist
                    if os.path.exists(filepath):
                        os.remove(filepath)
                    return jsonify({'error': 'Audio streamer does not support playlist'}), 400

        except Exception as e:
            Logger.error(f"Error uploading track: {e}")
            return jsonify({'error': 'Failed to upload file'}), 500

    def play(self):
        """Start playback for liquid music."""
        try:
            if hasattr(self.audio_streamer, 'startAudioStream'):
                self.audio_streamer.startAudioStream()
                self._broadcast_stats()
                return jsonify({'success': True})
            else:
                return jsonify({'error': 'Audio streamer does not support playback control'}), 400
        except Exception as e:
            Logger.error(f"Error starting playback: {e}")
            return jsonify({'error': 'Failed to start playback'}), 500

    def stop(self):
        """Stop playback for liquid music."""
        try:
            if hasattr(self.audio_streamer, 'stopAudioStream'):
                self.audio_streamer.stopAudioStream()
                self._broadcast_stats()
                return jsonify({'success': True})
            else:
                return jsonify({'error': 'Audio streamer does not support playback control'}), 400
        except Exception as e:
            Logger.error(f"Error stopping playback: {e}")
            return jsonify({'error': 'Failed to stop playback'}), 500

    def pause(self):
        """Pause playback for liquid music."""
        try:
            if hasattr(self.audio_streamer, 'pausePlayback'):
                self.audio_streamer.pausePlayback()
                self._broadcast_stats()
                return jsonify({'success': True})
            else:
                return jsonify({'error': 'Audio streamer does not support playback control'}), 400
        except Exception as e:
            Logger.error(f"Error pausing playback: {e}")
            return jsonify({'error': 'Failed to pause playback'}), 500

    def resume(self):
        """Resume paused playback for liquid music."""
        try:
            if hasattr(self.audio_streamer, 'resumePlayback'):
                self.audio_streamer.resumePlayback()
                self._broadcast_stats()
                return jsonify({'success': True})
            else:
                return jsonify({'error': 'Audio streamer does not support playback control'}), 400
        except Exception as e:
            Logger.error(f"Error resuming playback: {e}")
            return jsonify({'error': 'Failed to resume playback'}), 500

    def skip_forward(self):
        """Skip to next track for liquid music."""
        try:
            if hasattr(self.audio_streamer, 'skipForward'):
                self.audio_streamer.skipForward()
                self._broadcast_stats()
                return jsonify({'success': True})
            else:
                return jsonify({'error': 'Audio streamer does not support playback control'}), 400
        except Exception as e:
            Logger.error(f"Error skipping forward: {e}")
            return jsonify({'error': 'Failed to skip forward'}), 500

    def skip_backward(self):
        """Skip to previous track for liquid music."""
        try:
            if hasattr(self.audio_streamer, 'skipBackward'):
                self.audio_streamer.skipBackward()
                self._broadcast_stats()
                return jsonify({'success': True})
            else:
                return jsonify({'error': 'Audio streamer does not support playback control'}), 400
        except Exception as e:
            Logger.error(f"Error skipping backward: {e}")
            return jsonify({'error': 'Failed to skip backward'}), 500

    def set_local_path(self):
        """Set local music directory path for liquid music."""
        try:
            data = request.get_json()
            path = data.get('path', '')
            
            if not path:
                return jsonify({'error': 'No path provided'}), 400
            
            if hasattr(self.audio_streamer, 'setLocalMusicPath'):
                self.audio_streamer.setLocalMusicPath(path)
                self._broadcast_stats()
                return jsonify({'success': True})
            else:
                return jsonify({'error': 'Audio streamer does not support local path'}), 400
        except Exception as e:
            Logger.error(f"Error setting local path: {e}")
            return jsonify({'error': 'Failed to set local path'}), 500

    def get_playlist(self):
        """Get current playlist for liquid music with metadata."""
        try:
            if hasattr(self.audio_streamer, 'playlist'):
                playlist = []
                for i, track_path in enumerate(self.audio_streamer.playlist):
                    metadata = self.audio_streamer.playlistMetadata.get(track_path, {})
                    playlist.append({
                        'index': i,
                        'filename': os.path.basename(track_path),
                        'path': track_path,
                        'title': metadata.get('title', ''),
                        'artist': metadata.get('artist', ''),
                        'album': metadata.get('album', ''),
                        'year': metadata.get('year', '')
                    })
                return jsonify({'playlist': playlist, 'current_index': self.audio_streamer.currentTrackIndex})
            else:
                return jsonify({'error': 'Audio streamer does not support playlist'}), 400
        except Exception as e:
            Logger.error(f"Error getting playlist: {e}")
            return jsonify({'error': 'Failed to get playlist'}), 500

    def get_stack(self):
        """Get playback stack for liquid music."""
        try:
            if hasattr(self.audio_streamer, 'playbackStack'):
                stack = []
                for track_path in self.audio_streamer.playbackStack:
                    stack.append({
                        'filename': os.path.basename(track_path),
                        'path': track_path
                    })
                return jsonify({'stack': stack})
            else:
                return jsonify({'error': 'Audio streamer does not support playback stack'}), 400
        except Exception as e:
            Logger.error(f"Error getting playback stack: {e}")
            return jsonify({'error': 'Failed to get playback stack'}), 500

    def remove_track(self):
        """Remove a track from the playlist."""
        try:
            data = request.get_json()
            index = data.get('index', -1)
            
            if index < 0:
                return jsonify({'error': 'Invalid index'}), 400
            
            if hasattr(self.audio_streamer, 'playlist'):
                if 0 <= index < len(self.audio_streamer.playlist):
                    removed_track = self.audio_streamer.playlist.pop(index)
                    # Adjust current index if needed
                    if self.audio_streamer.currentTrackIndex >= len(self.audio_streamer.playlist):
                        self.audio_streamer.currentTrackIndex = max(0, len(self.audio_streamer.playlist) - 1)
                    elif self.audio_streamer.currentTrackIndex > index:
                        self.audio_streamer.currentTrackIndex -= 1
                    
                    Logger.info(f"Removed track from playlist: {removed_track}")
                    self._broadcast_stats()
                    return jsonify({'success': True})
                else:
                    return jsonify({'error': 'Index out of range'}), 400
            else:
                return jsonify({'error': 'Audio streamer does not support playlist'}), 400
        except Exception as e:
            Logger.error(f"Error removing track: {e}")
            return jsonify({'error': 'Failed to remove track'}), 500

    def _broadcast_stats(self):
        """Broadcast updated stats to all WebSocket clients."""
        if hasattr(self.audio_streamer, 'getStats'):
            stats = self.audio_streamer.getStats()
            # Add track info if available
            if hasattr(self.audio_streamer, 'track_info'):
                stats['artist'] = self.audio_streamer.track_info.get('artist', '')
                stats['track_title'] = self.audio_streamer.track_info.get('track_title', '')
                stats['album_name'] = self.audio_streamer.track_info.get('album_name', '')
                stats['track_year'] = self.audio_streamer.track_info.get('track_year', '')
                stats['album_cover'] = self.audio_streamer.track_info.get('album_cover', '')
            self.socketio.emit('stats', stats)
