import queue
import threading
import time
import os
import subprocess
from typing import List, Optional, Dict
from pathlib import Path
from mutagen import File
from mutagen.id3 import ID3NoHeaderError

from utilities.Constants import CHANNELS, RATE, CHUNK
from utilities.Logger import Logger


class LiquidMusicStreamer:
    """Audio streaming engine for file-based music playback.
    
    Handles manual song upload and local path playback with playlist management.
    """

    def __init__(self):
        """Initialize the musica liquida streaming system.
        
        Sets up playlist management, playback state, client management,
        and creates the upload directory for music files.
        
        Attributes:
            playbackProcess: Subprocess handle for ffmpeg playback
            onAir: Boolean flag indicating if streaming is active
            listeningClients: List of client queues for audio distribution
            _lock: Thread-safe lock for playlist and client management
            startTime: Application start time (set by ApplicationController)
            playlist: List of file paths in playback order
            currentTrackIndex: Index of currently playing track
            isPlaying: Boolean flag indicating if playback is active
            isPaused: Boolean flag indicating if playback is paused
            localMusicPath: Path to local music directory
            playbackStack: History of played tracks
            uploadDir: Directory path for uploaded music files
        """
        self.playbackProcess = None
        self.onAir = False
        self.listeningClients = []
        self._lock = threading.RLock()
        self.startTime = None  # Set by ApplicationController
        
        # Playlist management
        self.playlist = []  # List of file paths in order
        self.playlistMetadata = {}  # Dictionary mapping file paths to metadata
        self.currentTrackIndex = 0
        self.isPlaying = False
        self.isPaused = False
        self.localMusicPath = None
        
        # Playback stack queue
        self.playbackStack = []  # History of played tracks
        
        # Upload directory
        self.uploadDir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'uploads', 'music')
        os.makedirs(self.uploadDir, exist_ok=True)

    def listAvailableDevices(self):
        """List available music sources for musica liquida.
        
        Displays the two available music sources:
        1. Manual upload via dashboard
        2. Local directory path specification
        
        Note: This is a placeholder method for consistency with other streamers.
              Musica liquida doesn't use audio devices but file-based playback.
        """
        print("=== Available music sources ===")
        print("1. Upload songs manually via dashboard")
        print("2. Specify local directory path")
        print("=" * 10)

    def _extract_metadata(self, file_path: str) -> Dict[str, str]:
        """Extract metadata from an audio file.
        
        Args:
            file_path: Path to the audio file
            
        Returns:
            Dictionary containing metadata (title, artist, album, year)
        """
        metadata = {
            'title': '',
            'artist': '',
            'album': '',
            'year': ''
        }
        
        try:
            audio_file = File(file_path)
            if audio_file is None:
                return metadata
            
            # Try to extract common metadata fields
            if hasattr(audio_file, 'tags'):
                tags = audio_file.tags
                if tags:
                    metadata['title'] = tags.get('TIT2', [''])[0] if 'TIT2' in tags else tags.get('title', [''])[0]
                    metadata['artist'] = tags.get('TPE1', [''])[0] if 'TPE1' in tags else tags.get('artist', [''])[0]
                    metadata['album'] = tags.get('TALB', [''])[0] if 'TALB' in tags else tags.get('album', [''])[0]
                    metadata['year'] = tags.get('TDRC', [''])[0] if 'TDRC' in tags else tags.get('date', [''])[0]
            elif hasattr(audio_file, 'info'):
                info = audio_file.info
                if hasattr(info, 'title'):
                    metadata['title'] = info.title if info.title else ''
                if hasattr(info, 'artist'):
                    metadata['artist'] = info.artist if info.artist else ''
                if hasattr(info, 'album'):
                    metadata['album'] = info.album if info.album else ''
                if hasattr(info, 'date'):
                    metadata['year'] = str(info.date[0]) if info.date else ''
            
            Logger.info(f"Extracted metadata for {os.path.basename(file_path)}: {metadata}")
            
        except (ID3NoHeaderError, Exception) as e:
            Logger.warning(f"Could not extract metadata for {file_path}: {e}")
        
        return metadata

    def addTrackToPlaylist(self, filePath: str):
        """Add a track to the playlist with metadata extraction.
        
        Adds the specified audio file to the end of the playlist.
        Extracts metadata from the file and stores it for later use.
        The track will be played in the order it was added.
        
        Args:
            filePath: Absolute path to the audio file to add
        """
        with self._lock:
            self.playlist.append(filePath)
            # Extract and store metadata
            metadata = self._extract_metadata(filePath)
            self.playlistMetadata[filePath] = metadata
            Logger.info(f"Added track to playlist: {filePath}")

    def setLocalMusicPath(self, path: str):
        """Set the local music directory path and load all audio files with metadata.
        
        Scans the specified directory for audio files (mp3, wav, flac, ogg, m4a)
        and loads them into the playlist in alphabetical order.
        Extracts metadata from each file.
        
        Args:
            path: Absolute path to the local directory containing music files
        
        Note:
            This replaces the current playlist with files from the local directory.
            Only files with supported audio extensions are loaded.
        """
        with self._lock:
            self.localMusicPath = path
            if os.path.exists(path) and os.path.isdir(path):
                # Load all audio files from the directory
                audio_extensions = ['.mp3', '.wav', '.flac', '.ogg', '.m4a']
                files = []
                for file in os.listdir(path):
                    if any(file.lower().endswith(ext) for ext in audio_extensions):
                        files.append(os.path.join(path, file))
                
                # Sort files to maintain order
                files.sort()
                self.playlist = files
                self.playlistMetadata = {}  # Clear old metadata
                
                # Extract metadata for each file
                for file_path in files:
                    metadata = self._extract_metadata(file_path)
                    self.playlistMetadata[file_path] = metadata
                
                Logger.info(f"Loaded {len(files)} tracks from local path: {path}")
            else:
                Logger.error(f"Invalid local path: {path}")

    def startAudioStream(self, listeningDeviceIndexes: Optional[List[int]] = None):
        """Start audio streaming from the playlist.
        
        Begins playback of the current track in the playlist.
        This method is called when the user presses the play button.
        Streaming does not start automatically on application startup.
        
        Args:
            listeningDeviceIndexes: Not used for file-based streaming (kept for interface compatibility)
        
        Note:
            If the playlist is empty, streaming will not start.
            If the current track index is beyond the playlist length, it wraps to the first track.
        """
        if self.onAir and not self.isPaused:
            Logger.info("Stream already onAir")
            return

        if not self.playlist:
            Logger.warning("Playlist is empty, cannot start streaming")
            return

        # Start from current track index
        if self.currentTrackIndex >= len(self.playlist):
            self.currentTrackIndex = 0

        self._playCurrentTrack()

    def stopAudioStream(self):
        """Stop audio streaming and clean up resources.
        
        Stops the current playback, terminates the ffmpeg process,
        and resets all playback state flags. This is called when
        the user presses the stop button.
        
        Note:
            The current track index is not reset, allowing playback to
            resume from the same position if desired.
        """
        self.onAir = False
        self.isPlaying = False
        self.isPaused = False

        if self.playbackProcess:
            try:
                self.playbackProcess.terminate()
                self.playbackProcess.wait(timeout=5)
                Logger.info("Playback process terminated")
            except Exception as e:
                Logger.error(f"Error terminating playback: {e}")
                self.playbackProcess.kill()
            self.playbackProcess = None

        Logger.info("Audio streaming stopped")

    def pausePlayback(self):
        """Pause the current playback.
        
        Pauses the currently playing track by terminating the ffmpeg process.
        The track can be resumed from the same position using resumePlayback().
        
        Note:
            Only affects playback if it's currently playing and not already paused.
        """
        if self.isPlaying and not self.isPaused:
            self.isPaused = True
            if self.playbackProcess:
                try:
                    self.playbackProcess.terminate()
                    self.playbackProcess.wait(timeout=5)
                except Exception as e:
                    Logger.error(f"Error pausing playback: {e}")
            Logger.info("Playback paused")

    def resumePlayback(self):
        """Resume paused playback.
        
        Resumes playback of the currently paused track from where it left off.
        
        Note:
            Only works if playback is currently paused and the playlist is not empty.
        """
        if self.isPaused and self.playlist:
            self.isPaused = False
            self._playCurrentTrack()
            Logger.info("Playback resumed")

    def skipForward(self):
        """Skip to the next track in the playlist.
        
        Moves to the next track in the playlist, wrapping around to the
        first track if at the end. The current track is added to the playback
        stack before skipping. If playback is active, the new track starts immediately.
        """
        with self._lock:
            if self.playlist:
                # Add current track to stack if it was playing
                if self.currentTrackIndex < len(self.playlist):
                    self.playbackStack.append(self.playlist[self.currentTrackIndex])
                
                self.currentTrackIndex = (self.currentTrackIndex + 1) % len(self.playlist)
                Logger.info(f"Skipped to track {self.currentTrackIndex + 1}/{len(self.playlist)}")
                
                if self.isPlaying or self.onAir:
                    self._playCurrentTrack()

    def skipBackward(self):
        """Skip to the previous track in the playlist.
        
        Moves to the previous track in the playlist, wrapping around to the
        last track if at the beginning. If playback is active, the new track
        starts immediately.
        
        Note:
            Unlike skipForward, this does not add tracks to the playback stack.
        """
        with self._lock:
            if self.playlist:
                self.currentTrackIndex = (self.currentTrackIndex - 1) % len(self.playlist)
                Logger.info(f"Skipped back to track {self.currentTrackIndex + 1}/{len(self.playlist)}")
                
                if self.isPlaying or self.onAir:
                    self._playCurrentTrack()

    def addClient(self, clientQueue: queue.Queue):
        """Add a client queue for audio distribution.
        
        Registers a new client to receive audio data chunks.
        The client will receive all audio data from the currently playing track.
        
        Args:
            clientQueue: Thread-safe queue for sending audio chunks to this client
        """
        Logger.info("Client connected")
        with self._lock:
            self.listeningClients.append(clientQueue)
            Logger.info(f"New connected client. Number of connected clients: {len(self.listeningClients)}")

    def removeClient(self, clientQueue: queue.Queue):
        """Remove a client queue from distribution list.
        
        Unregisters a client from receiving audio data.
        
        Args:
            clientQueue: The queue to remove from active clients
        """
        with self._lock:
            if clientQueue in self.listeningClients:
                self.listeningClients.remove(clientQueue)
                Logger.info(f"Client disconnected. Number of connected clients: {len(self.listeningClients)}")

    def getStats(self):
        """Get current streaming statistics.
        
        Returns a dictionary containing the current state of the streamer,
        including playback status, listener count, and track information.
        
        Returns:
            dict: Dictionary containing the following keys:
                - on_air (bool): Whether streaming is active
                - is_playing (bool): Whether playback is active
                - is_paused (bool): Whether playback is paused
                - listeners (int): Number of connected clients
                - sample_rate (int): Audio sample rate in Hz
                - channels (int): Number of audio channels
                - uptime_seconds (int): Uptime in seconds
                - uptime_formatted (str): Human-readable uptime string
                - start_time (float): Application start timestamp
                - current_track (str): Filename of current track
                - playlist_length (int): Number of tracks in playlist
                - current_track_index (int): Index of current track
                - playback_stack_length (int): Number of tracks in playback stack
                - local_music_path (str): Path to local music directory
        """
        with self._lock:
            # Calculate uptime
            uptime_seconds = 0
            if self.startTime:
                uptime_seconds = int(time.time() - self.startTime)

            current_track = ""
            current_metadata = {}
            if self.playlist and self.currentTrackIndex < len(self.playlist):
                current_file = self.playlist[self.currentTrackIndex]
                current_track = os.path.basename(current_file)
                current_metadata = self.playlistMetadata.get(current_file, {})

            return {
                'on_air': self.onAir,
                'is_playing': self.isPlaying,
                'is_paused': self.isPaused,
                'listeners': len(self.listeningClients),
                'sample_rate': RATE,
                'channels': CHANNELS,
                'uptime_seconds': uptime_seconds,
                'uptime_formatted': self._formatUptime(uptime_seconds),
                'start_time': self.startTime,
                'current_track': current_track,
                'track_title': current_metadata.get('title', ''),
                'artist': current_metadata.get('artist', ''),
                'album_name': current_metadata.get('album', ''),
                'track_year': current_metadata.get('year', ''),
                'playlist_length': len(self.playlist),
                'current_track_index': self.currentTrackIndex,
                'playback_stack_length': len(self.playbackStack),
                'local_music_path': self.localMusicPath
            }

    def _formatUptime(self, seconds):
        """Format uptime seconds into human-readable string.
        
        Args:
            seconds: Uptime in seconds
            
        Returns:
            str: Formatted uptime string (e.g., "1h 23m 45s", "45s", "5m 30s")
        """
        if seconds < 60:
            return f"{seconds}s"
        elif seconds < 3600:
            minutes = seconds // 60
            secs = seconds % 60
            return f"{minutes}m {secs}s"
        else:
            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            secs = seconds % 60
            return f"{hours}h {minutes}m {secs}s"

    def _playCurrentTrack(self):
        """Play the current track from the playlist.
        
        Starts ffmpeg to convert the current audio file to raw PCM format
        and begins streaming to connected clients. The track is added to
        the playback stack when playback starts.
        
        Note:
            This is a private method called by startAudioStream, skipForward,
            and resumePlayback. It uses ffmpeg for audio conversion.
        """
        if not self.playlist or self.currentTrackIndex >= len(self.playlist):
            Logger.warning("No track to play")
            return

        current_file = self.playlist[self.currentTrackIndex]
        Logger.info(f"Playing track: {current_file}")

        try:
            # Use ffmpeg to convert audio to raw PCM and stream it
            cmd = [
                'ffmpeg',
                '-i', current_file,
                '-f', 's16le',
                '-acodec', 'pcm_s16le',
                '-ar', str(RATE),
                '-ac', str(CHANNELS),
                '-loglevel', 'error',
                '-'
            ]

            self.playbackProcess = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=0
            )

            self.onAir = True
            self.isPlaying = True
            self.isPaused = False
            
            # Start the audio capture thread
            threading.Thread(target=self._captureAudioFromProcess, daemon=True).start()
            
            # Add to playback stack
            self.playbackStack.append(current_file)
            
            Logger.info("Audio streaming started for current track")

        except Exception as e:
            Logger.error(f"Failed to start playback: {e}")
            self.onAir = False
            self.isPlaying = False

    def _captureAudioFromProcess(self):
        """Read audio data from ffmpeg process and distribute to clients.
        
        This method runs in a daemon thread and continuously reads audio
        chunks from ffmpeg's stdout, distributing them to all connected
        clients. When a track ends, it automatically advances to the next
        track in the playlist.
        
        Note:
            This is a private method called by _playCurrentTrack.
            Handles process termination and queue overflow gracefully.
        """
        Logger.info("Audio capture thread started - reading from ffmpeg")

        try:
            while self.onAir and self.isPlaying and self.playbackProcess:
                # Read audio chunk from ffmpeg
                data = self.playbackProcess.stdout.read(CHUNK * 2)  # 2 bytes per sample for 16-bit

                if not data:
                    # Check if process ended
                    if self.playbackProcess.poll() is not None:
                        Logger.info("ffmpeg process ended, moving to next track")
                        # Auto-advance to next track
                        if self.onAir:
                            self.skipForward()
                        break
                    else:
                        # Process still running but no data, wait a bit
                        time.sleep(0.01)
                        continue

                # Distribute to clients
                with self._lock:
                    clientsCopy = self.listeningClients.copy()

                for client in clientsCopy:
                    try:
                        client.put_nowait(data)
                    except queue.Full:
                        Logger.warning("Client queue full, dropping audio chunk")

        except Exception as e:
            Logger.error(f"Error in audio capture thread: {e}")
            import traceback
            Logger.error(f"Full traceback: {traceback.format_exc()}")
        finally:
            if not self.isPaused:
                self.onAir = False
            Logger.info("Audio capture thread ended")
