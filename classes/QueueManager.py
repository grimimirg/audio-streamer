import threading
import json
import os
from utilities.Logger import Logger
from typing import Optional

class QueueManager:
    """Manages thread-safe playlist queues and playback states with persistent storage.

    This class coordinates playlist structures, track histories, and system 
    playback states (playing, paused, scanning) across multiple concurrent 
    execution contexts. It wraps raw data modifications inside a reentrant 
    thread lock (RLock) to prevent race conditions between web request 
    threads (Flask) and background audio capture workers. State changes 
    are automatically serialized to a local JSON file for persistence.

    Attributes:
        persistence_file (str): File path for JSON state serialization.
    """
    def __init__(self, persistence_file="playlist_queue.json"):
        self.persistence_file = persistence_file
        
        # 1. The Protection Barrier
        self._lock = threading.RLock()
        
        # 2. Protected Core Attributes
        self._playlist = []
        self._playlistMetadata = {}
        self._currentTrackIndex = 0
        self._playbackStack = []
        
        # Playback/App States
        self._isPlaying = False
        self._isPaused = False
        self._isScanning = False
        self._localMusicPath = None
        
        # Load any existing saved state on startup
        self.load_queue()

    # --- ATOMIC STATE READERS & SNAPSHOTS ---
    def get_status(self) -> dict:
        """Returns a safe, frozen snapshot of the entire state machine.
        
        """
        with self._lock:
            return {
                "playlist": list(self._playlist),
                "playlistMetadata": dict(self._playlistMetadata),
                "currentTrackIndex": self._currentTrackIndex,
                "playbackStack": list(self._playbackStack),
                "isPlaying": self._isPlaying,
                "isPaused": self._isPaused,
                "isScanning": self._isScanning,
                "localMusicPath": self._localMusicPath,
                "currentTrack": self.get_current_track()
            }

    def get_current_track(self) -> Optional[str]:
        with self._lock:
            # sync with disk
            self.load_queue()
            
            if not self._playlist or self._currentTrackIndex >= len(self._playlist):
                return None
            return self._playlist[self._currentTrackIndex]

    # --- STATE MUTATORS (SETTERS) ---
    def set_playback_states(self, is_playing: Optional[bool] = None, is_paused: Optional[bool] = None):
        """Atomically updates playing/paused flags."""
        with self._lock:
            if is_playing is not None:
                self._isPlaying = is_playing
            if is_paused is not None:
                self._isPaused = is_paused
            self.save_queue()

    def set_scanning(self, is_scanning: bool):
        with self._lock:
            self._isScanning = is_scanning

    def set_local_music_path(self, path: Optional[str]):
        with self._lock:
            self._localMusicPath = path
            self.save_queue()

    # --- QUEUE & PLAYLIST CORE ACTIONS ---
    def add_track(self, file_path: str, metadata: dict):
        with self._lock:
            # sync with disk first
            self.load_queue()
            if file_path not in self._playlist:
                self._playlist.append(file_path)
            self._playlistMetadata[file_path] = metadata
            # commit back to disk
            self.save_queue()

    def clear_playlist(self):
        with self._lock:
            # sync with disk
            self.load_queue()
            self._playlist.clear()
            self._playlistMetadata.clear()
            self._currentTrackIndex = 0
            self._playbackStack.clear()
            self.save_queue()

def skip_forward(self) -> Optional[str]:
        with self._lock:
            # Sync with disk
            self.load_queue()
            if not self._playlist:
                return None
            # Evaluate current track directly from memory to prevent redundant file reads
            if self._currentTrackIndex < len(self._playlist):
                current = self._playlist[self._currentTrackIndex]
                self._playbackStack.append(current)
            # Advance index (with wrap-around loop back to 0)
            self._currentTrackIndex = (self._currentTrackIndex + 1) % len(self._playlist)
            self.save_queue()
            return self._playlist[self._currentTrackIndex]

    def skip_backward(self) -> Optional[str]:
        with self._lock:
            # Sync with disk
            self.load_queue()
            if not self._playlist:
                return None                
            # Regress index
            self._currentTrackIndex = (self._currentTrackIndex - 1) % len(self._playlist)
            # Pop last item from stack if possible
            if self._playbackStack:
                self._playbackStack.pop()
            self.save_queue()
            return self._playlist[self._currentTrackIndex]
            
    # --- PERSISTENCE LAYER ---

    def save_queue(self):
        """Serializes current queue context to disk safely."""
        try:
            state = {
                "playlist": self._playlist,
                "playlistMetadata": self._playlistMetadata,
                "currentTrackIndex": self._currentTrackIndex,
                "playbackStack": self._playbackStack,
                "isPlaying": self._isPlaying,
                "isPaused": self._isPaused,
                "localMusicPath": self._localMusicPath
            }
            with open(self.persistence_file, 'w') as f:
                json.dump(state, f, indent=4)
        except Exception as e:
            Logger.error(f"QueueManager failed to write persistence layer: {e}")

    def load_queue(self):
        """Restores queue state matrix on system startup."""
        if not os.path.exists(self.persistence_file):
            # Explicitly enforce safe empty defaults if the JSON doesn't exist yet
            self._playlist = []
            self._playlistMetadata = {}
            self._currentTrackIndex = 0
            self._playbackStack = []
            self._isPlaying = False
            self._isPaused = False
            self._localMusicPath = None
            return
        try:
            with open(self.persistence_file, 'r') as f:
                state = json.load(f)
            self._playlist = state.get("playlist", [])
            self._playlistMetadata = state.get("playlistMetadata", {})
            self._currentTrackIndex = state.get("currentTrackIndex", 0)
            self._playbackStack = state.get("playbackStack", [])
            self._isPlaying = state.get("isPlaying", False)
            self._isPaused = state.get("isPaused", False)
            self._localMusicPath = state.get("localMusicPath", None)
            print("QueueManager state successfully restored from local storage.", flush=True)
        except Exception as e:
            print(f"QueueManager crashed while restoring state disk matrix: {e}", flush=True)
