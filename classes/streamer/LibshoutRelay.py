import queue
import socket
import subprocess
import threading
import time

from utilities.AudioFormat import build_wav_header
from utilities.Constants import CHANNELS, CLIENT_QUEUE_SIZE, FFMPEG_QUEUE_TIMEOUT, RATE
from utilities.FfmpegCommand import build_mp3_command
from utilities.Logger import Logger

# shout_get_connected() returns this when the handle is connected; anything else
# means it is not. Calling set_metadata() on an unconnected handle segfaults the
# process, so every metadata push must check this first.
SHOUT_CONNECTED = 0


class RelaySettings:
    """Where one relay publishes, and how it identifies itself."""

    def __init__(self, label, scheme, host, port, mount, user, password, protocol, bitrate,
                 station_name, reconnect_delay, reconnect_max_delay, test_timeout,
                 config_prefix):
        """Initialize the settings.

        Args:
            label: Human-readable name used in log messages, e.g. "Icecast"
            scheme: URL scheme used in log messages, e.g. "icecast"
            host: Server hostname or address
            port: Server port
            mount: Mount point, including the leading slash
            user: Source user
            password: Source password
            protocol: libshout protocol name (http, icy, xaudiocast)
            bitrate: Bitrate in kbps for the relayed stream
            station_name: Station name published as the stream's name
            reconnect_delay: Seconds before the first reconnection attempt
            reconnect_max_delay: Longest wait between reconnection attempts
            test_timeout: Timeout for the startup reachability check
            config_prefix: Environment variable prefix, used in error messages
        """
        self.label = label
        self.scheme = scheme
        self.host = host
        self.port = port
        self.mount = mount
        self.user = user
        self.password = password
        self.protocol = protocol
        self.bitrate = bitrate
        self.station_name = station_name
        self.reconnect_delay = reconnect_delay
        self.reconnect_max_delay = reconnect_max_delay
        self.test_timeout = test_timeout
        self.config_prefix = config_prefix

    @property
    def url(self) -> str:
        """The mount's address, for log messages."""
        return f"{self.scheme}://{self.host}:{self.port}{self.mount}"


def default_shout_factory():
    """Build a libshout handle.

    The import is deferred so a station that never relays can run without
    libshout installed: nothing imports python-shout until a relay is started.

    Returns:
        shout.Shout: A fresh libshout handle

    Raises:
        RuntimeError: If python-shout or libshout is unavailable
    """
    try:
        import shout
    except ImportError as e:
        Logger.error(
            "python-shout is not available. Install libshout and its development "
            "headers, then reinstall the requirements, to relay the stream."
        )
        raise RuntimeError("python-shout is required for relaying") from e

    return shout.Shout()


def probe_server(settings: RelaySettings, connect=socket.create_connection) -> bool:
    """Check that a relay's server is reachable.

    This answers "is the server there?" only. Whether the credentials and mount
    point are accepted is decided when the mount is opened, because opening a
    second connection as a dry run would collide with the relay's own mount.

    Args:
        settings: The relay's settings
        connect: Connection factory, injectable for testing

    Returns:
        bool: True if the server accepted a TCP connection
    """
    try:
        connection = connect((settings.host, settings.port), settings.test_timeout)
    except (OSError, socket.timeout) as e:
        Logger.warning(
            f"{settings.label} server at {settings.host}:{settings.port} is not reachable: {e}. "
            f"Check {settings.config_prefix}_HOST and {settings.config_prefix}_PORT, "
            "and that the server is running."
        )
        return False

    try:
        connection.close()
    except OSError:
        pass

    Logger.info(f"{settings.label} server reachable at {settings.host}:{settings.port}")
    return True


class LibshoutRelay:
    """Relays the live audio to a streaming server as a source client.

    Unlike the capturing streamers this is a sink, not a source, and must never
    be registered in AudioStreamerFactory: it does not capture audio. It attaches
    to whichever streamer is capturing - the same seam BitrateEncoder uses,
    `addClient` on a queue - encodes that PCM to MP3 with ffmpeg, and pushes the
    result to a mount point via libshout.

    The protocol is libshout's business. This class owns the plumbing: the ffmpeg
    process, the pump threads, and reconnecting when the server drops the
    connection. Subclasses supply only where to publish, via RelaySettings.
    """

    def __init__(self, audio_streamer, settings: RelaySettings, popen=subprocess.Popen,
                 shout_factory=default_shout_factory, sleep=time.sleep):
        """Initialize the relay.

        Args:
            audio_streamer: The capturing streamer to read source audio from
            settings: Where to publish and how to identify the stream
            popen: Process factory, injectable for testing
            shout_factory: Callable returning a libshout handle, injectable for testing
            sleep: Sleep function used for reconnect backoff, injectable for testing
        """
        self.audio_streamer = audio_streamer
        self.settings = settings
        self.popen = popen
        self.shout_factory = shout_factory
        self.sleep = sleep

        self.process = None
        self.shout = None
        self.running = False
        self.connected = False

        self._stopped = False
        self._lock = threading.Lock()
        self._source_queue = queue.Queue(maxsize=CLIENT_QUEUE_SIZE)
        self._threads = []

    def start(self):
        """Connect to the server, start encoding, and begin relaying audio.

        Raises:
            RuntimeError: If ffmpeg or python-shout is unavailable, or the mount
                          point cannot be opened
        """
        self.shout = self._open_connection()
        self.process = self._start_process()
        self.running = True
        self._stopped = False
        self.audio_streamer.addClient(self._source_queue)

        label = self.settings.label.lower()
        self._threads = [
            threading.Thread(target=self._pump_source, name=f'{label}-source', daemon=True),
            threading.Thread(target=self._pump_output, name=f'{label}-output', daemon=True),
            threading.Thread(target=self._monitor_errors, name=f'{label}-stderr', daemon=True),
        ]
        for thread in self._threads:
            thread.start()

        Logger.info(f"Relaying to {self.settings.url} at {self.settings.bitrate}kbps")

    def stop(self):
        """Stop relaying, release the source client and close the mount point.

        Safe to call more than once, and callable after the relay has already
        wound itself down.
        """
        with self._lock:
            if self._stopped:
                return
            self._stopped = True

        self.running = False

        try:
            self.audio_streamer.removeClient(self._source_queue)
        except Exception as e:
            Logger.error(f"Error removing {self.settings.label} source client: {e}")

        # Unblock the source thread if it is waiting on an empty queue
        try:
            self._source_queue.put_nowait(None)
        except queue.Full:
            pass

        for thread in self._threads:
            if thread.is_alive():
                thread.join(timeout=1.0)
        self._threads = []

        if self.process:
            self._cleanup_process(self.process)
            self.process = None

        self._close_connection()
        Logger.info(f"Stopped {self.settings.label} relay")

    def update_metadata(self, title: str) -> bool:
        """Publish the currently playing title to the server.

        Args:
            title: The "now playing" string to publish

        Returns:
            bool: True if the update was sent
        """
        if not title:
            return False

        handle = self.shout
        # set_metadata() on an unconnected handle segfaults the interpreter, so
        # the live connection is checked rather than assumed. A reconnect in
        # progress must never be able to take the application down.
        if handle is None or not self.connected:
            return False

        try:
            if handle.get_connected() != SHOUT_CONNECTED:
                return False
            handle.set_metadata({'song': title})
        except Exception as e:
            # Metadata is cosmetic; losing it must not disturb the audio
            Logger.warning(f"Could not update {self.settings.label} metadata: {e}")
            return False

        Logger.info(f"{self.settings.label} metadata updated: {title}")
        return True

    @property
    def is_connected(self) -> bool:
        """Whether the mount point is currently open."""
        return self.connected

    def getStats(self) -> dict:
        """Get the relay's current state.

        Returns:
            dict: Connection state and mount details
        """
        return {
            'enabled': True,
            'connected': self.connected,
            'host': self.settings.host,
            'port': self.settings.port,
            'mount': self.settings.mount,
            'bitrate': self.settings.bitrate,
            'protocol': self.settings.protocol,
        }

    # -- PRIVATES --

    def _open_connection(self):
        """Open the mount point.

        Returns:
            The connected libshout handle

        Raises:
            RuntimeError: If the mount point cannot be opened
        """
        handle = self.shout_factory()
        self._configure(handle)

        try:
            handle.open()
        except Exception as e:
            prefix = self.settings.config_prefix
            Logger.error(
                f"Could not open {self.settings.url}: {e}. "
                f"Check that the server is running and that {prefix}_USER, "
                f"{prefix}_PASSWORD and {prefix}_MOUNT are correct."
            )
            raise RuntimeError(f"Could not connect to {self.settings.label}: {e}") from e

        self.connected = True
        Logger.info(f"Connected to {self.settings.label} mount {self.settings.mount}")
        return handle

    def _configure(self, handle):
        """Apply the connection and metadata settings to a handle.

        Args:
            handle: The libshout handle to configure
        """
        settings = self.settings
        handle.host = settings.host
        handle.port = settings.port
        handle.user = settings.user
        handle.password = settings.password
        handle.mount = settings.mount
        handle.protocol = settings.protocol
        handle.format = 'mp3'
        handle.name = settings.station_name
        handle.audio_info = {
            'bitrate': str(settings.bitrate),
            'samplerate': str(RATE),
            'channels': str(CHANNELS),
        }

    def _close_connection(self):
        """Close the mount point, ignoring a connection that is already gone."""
        self.connected = False
        if not self.shout:
            return
        try:
            self.shout.close()
        except Exception as e:
            Logger.error(f"Error closing {self.settings.label} connection: {e}")
        self.shout = None

    def _start_process(self):
        """Start the ffmpeg process encoding the relay's MP3 stream.

        Returns:
            The ffmpeg process

        Raises:
            RuntimeError: If ffmpeg is not found
        """
        try:
            return self.popen(
                build_mp3_command(self.settings.bitrate),
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
        except FileNotFoundError:
            Logger.error(f"ffmpeg not found. Please install ffmpeg to relay to {self.settings.label}.")
            raise RuntimeError(f"ffmpeg is required for {self.settings.label} streaming")

    def _pump_source(self):
        """Feed source audio into ffmpeg's stdin until the stream ends."""
        try:
            self.process.stdin.write(build_wav_header(RATE, CHANNELS))
            self.process.stdin.flush()

            while self.running:
                try:
                    chunk = self._source_queue.get(timeout=FFMPEG_QUEUE_TIMEOUT)
                except queue.Empty:
                    if not self.audio_streamer.onAir:
                        Logger.info(
                            f"Audio streaming stopped, closing {self.settings.label} relay encoder"
                        )
                        break
                    continue

                if chunk is None:
                    break

                self.process.stdin.write(chunk)
                self.process.stdin.flush()
        except BrokenPipeError:
            Logger.error(f"ffmpeg broken pipe on the {self.settings.label} relay")
        except (IOError, ValueError) as e:
            Logger.error(f"Error writing to ffmpeg ({self.settings.label} relay): {e}")
        except Exception as e:
            Logger.error(
                f"Unexpected error in {self.settings.label} source thread: "
                f"{type(e).__name__}: {str(e)}"
            )
        finally:
            self.running = False
            self._close_stdin()

    def _pump_output(self):
        """Send encoded output to the server, reconnecting if it drops us."""
        delay = self.settings.reconnect_delay
        try:
            while self.running:
                chunk = self.process.stdout.read(8192)
                if not chunk:
                    break

                if self._send(chunk):
                    delay = self.settings.reconnect_delay
                    continue

                # The send failed: drop the connection and try to get it back,
                # backing off so a server that stays down is not hammered.
                self._close_connection()
                if not self.running:
                    break

                Logger.warning(
                    f"{self.settings.label} connection lost, reconnecting in {delay:.0f}s"
                )
                self.sleep(delay)
                delay = min(delay * 2, self.settings.reconnect_max_delay)

                if not self._reconnect():
                    continue

                # The chunk that failed is deliberately dropped: it is now older
                # than the backoff, and a listener is better served by live audio.
        except Exception as e:
            Logger.error(f"Error relaying to {self.settings.label}: {e}")
        finally:
            self.running = False

    def _send(self, chunk: bytes) -> bool:
        """Send one encoded chunk to the server.

        Args:
            chunk: Encoded MP3 chunk

        Returns:
            bool: True if the chunk was accepted, False if the connection failed
        """
        if not self.shout:
            return False
        try:
            self.shout.send(chunk)
            # libshout paces the sender to real time; without this the relay
            # would race ahead of the stream and the server would drop it.
            self.shout.sync()
            return True
        except Exception as e:
            Logger.error(f"Error sending audio to {self.settings.label}: {e}")
            return False

    def _reconnect(self) -> bool:
        """Try to reopen the mount point.

        Returns:
            bool: True once reconnected, False if the attempt failed
        """
        try:
            self.shout = self._open_connection()
            return True
        except RuntimeError:
            return False

    def _close_stdin(self):
        """Close ffmpeg's stdin to signal end of input."""
        try:
            if self.process and self.process.stdin and not self.process.stdin.closed:
                self.process.stdin.close()
        except Exception as e:
            Logger.error(f"Error closing ffmpeg stdin: {e}")

    def _monitor_errors(self):
        """Monitor ffmpeg stderr and log anything it reports."""
        try:
            while True:
                error_line = self.process.stderr.readline()
                if not error_line:
                    break
                error_line = error_line.decode('utf-8', errors='ignore').strip()
                if not error_line:
                    continue
                if 'error' in error_line.lower() or 'fatal' in error_line.lower():
                    Logger.error(f"FFmpeg error ({self.settings.label} relay): {error_line}")
                elif 'warning' in error_line.lower():
                    Logger.warning(f"FFmpeg warning ({self.settings.label} relay): {error_line}")
        except Exception as e:
            Logger.error(f"Error in ffmpeg error monitor thread: {e}")

    def _cleanup_process(self, process):
        """Clean up ffmpeg process resources.

        Args:
            process: The ffmpeg subprocess to cleanup
        """
        try:
            self._close_stdin()
            if process.stdout and not process.stdout.closed:
                process.stdout.close()
            if process.stderr and not process.stderr.closed:
                process.stderr.close()
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    Logger.warning("ffmpeg process did not terminate, killing it")
                    process.kill()
                    process.wait()
        except Exception as e:
            Logger.error(f"Error cleaning up ffmpeg process: {e}")
