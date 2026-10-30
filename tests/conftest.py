import os
import queue

# Pin the configuration before any module imports utilities.Constants, so tests
# never depend on a developer's local .env. python-dotenv does not override
# variables that are already set, so these win either way.
os.environ.setdefault('AUDIO_CHUNK', '512')
os.environ.setdefault('AUDIO_CHANNELS', '2')
os.environ.setdefault('AUDIO_RATE', '44100')
os.environ.setdefault('AUDIO_STREAMER_HOST', '127.0.0.1')
os.environ.setdefault('AUDIO_STREAMER_PORT', '4986')
os.environ.setdefault('AUDIO_STREAMER_DEBUG', 'False')
os.environ.setdefault('AUDIO_STREAMER_MAX_CLIENTS', '10')
os.environ.setdefault('AUDIO_STREAM_BITRATES', '128,192,320')
os.environ.setdefault('AUDIO_STREAMER_QUEUE_SIZE', '100')
os.environ.setdefault('FFMPEG_OUTPUT_QUEUE_SIZE', '50')
os.environ.setdefault('FFMPEG_QUEUE_TIMEOUT', '0.01')
os.environ.setdefault('FFMPEG_THREADS', '0')
os.environ.setdefault('CPU_WARNING_THRESHOLD', '80')
os.environ.setdefault('CPU_MONITOR_INTERVAL', '5.0')
os.environ.setdefault('ICECAST_ENABLED', 'False')
os.environ.setdefault('ICECAST_HOST', 'icecast.test')
os.environ.setdefault('ICECAST_PORT', '8000')
os.environ.setdefault('ICECAST_MOUNT', '/stream')
os.environ.setdefault('ICECAST_USER', 'source')
os.environ.setdefault('ICECAST_PASSWORD', 'hackme')
os.environ.setdefault('ICECAST_BITRATE', '128')
os.environ.setdefault('ICECAST_PROTOCOL', 'http')
os.environ.setdefault('ICECAST_RECONNECT_DELAY', '0.01')
os.environ.setdefault('ICECAST_RECONNECT_MAX_DELAY', '0.04')
os.environ.setdefault('RADIO_STATION_NAME', 'Test Station')
os.environ.setdefault('SHOUTCAST_ENABLED', 'False')
os.environ.setdefault('SHOUTCAST_HOST', 'shoutcast.test')
os.environ.setdefault('SHOUTCAST_PORT', '8100')
os.environ.setdefault('SHOUTCAST_MOUNT', '/live')
os.environ.setdefault('SHOUTCAST_USER', 'source')
os.environ.setdefault('SHOUTCAST_PASSWORD', 'sc-secret')
os.environ.setdefault('SHOUTCAST_BITRATE', '192')
os.environ.setdefault('SHOUTCAST_RECONNECT_DELAY', '0.01')
os.environ.setdefault('SHOUTCAST_RECONNECT_MAX_DELAY', '0.04')
os.environ.setdefault('SHOUTCAST_TEST_TIMEOUT', '5.0')

import pytest  # noqa: E402  (must follow the environment setup above)


class FakeStreamer:
    """Minimal stand-in for an audio streamer, exposing the client queue contract."""

    def __init__(self, on_air=True):
        self.onAir = on_air
        self.clients = []
        self.removed = []

    def addClient(self, client_queue):
        self.clients.append(client_queue)

    def removeClient(self, client_queue):
        self.removed.append(client_queue)
        if client_queue in self.clients:
            self.clients.remove(client_queue)

    def getStats(self):
        return {
            'on_air': self.onAir,
            'listeners': len(self.clients),
            'sample_rate': 44100,
            'channels': 2,
            'uptime_seconds': 0,
            'uptime_formatted': '0s',
            'start_time': None,
        }


class FakePipe:
    """Writable pipe recording everything written to it."""

    def __init__(self):
        self.written = b''
        self.closed = False
        self.flushed = 0

    def write(self, data):
        if self.closed:
            raise ValueError('I/O operation on closed file')
        self.written += data

    def flush(self):
        self.flushed += 1

    def close(self):
        self.closed = True


class FakeReadPipe:
    """Readable pipe serving a fixed list of chunks, then EOF."""

    def __init__(self, chunks=None, lines=None):
        self._chunks = list(chunks or [])
        self._lines = list(lines or [])
        self.closed = False

    def read(self, _size=None):
        return self._chunks.pop(0) if self._chunks else b''

    def readline(self):
        return self._lines.pop(0) if self._lines else b''

    def close(self):
        self.closed = True


class FakeProcess:
    """Stand-in for an ffmpeg subprocess."""

    def __init__(self, stdout_chunks=None, stderr_lines=None, return_code=0):
        self.stdin = FakePipe()
        self.stdout = FakeReadPipe(chunks=stdout_chunks)
        self.stderr = FakeReadPipe(lines=stderr_lines)
        self.terminated = False
        self.killed = False
        self.waited = False
        self._return_code = return_code

    def poll(self):
        return self._return_code

    def terminate(self):
        self.terminated = True

    def kill(self):
        self.killed = True

    def wait(self, timeout=None):
        self.waited = True
        return self._return_code


class FakeShout:
    """Stand-in for a libshout handle, recording configuration and traffic.

    Mirrors python-shout's interface: settings are plain attributes, and
    open/send/sync/close raise on failure.
    """

    def __init__(self, open_error=None, send_errors=0, connected_code=0,
                 metadata_error=None):
        """Initialize the handle.

        Args:
            open_error: Exception to raise from open(), or None to succeed
            send_errors: Number of initial send() calls that should fail
            connected_code: What get_connected() reports; 0 means connected,
                            as libshout's SHOUTERR_SUCCESS does
            metadata_error: Exception to raise from set_metadata(), or None
        """
        self.open_error = open_error
        self.send_errors = send_errors
        self.connected_code = connected_code
        self.metadata_error = metadata_error
        self.sent = b''
        self.metadata = []
        self.opens = 0
        self.closes = 0
        self.syncs = 0
        self.settings = {}

    def __setattr__(self, name, value):
        # Record the libshout settings without shadowing our own attributes
        if name not in ('open_error', 'send_errors', 'connected_code', 'metadata_error',
                        'sent', 'metadata', 'opens', 'closes', 'syncs', 'settings'):
            self.settings[name] = value
        object.__setattr__(self, name, value)

    def open(self):
        self.opens += 1
        if self.open_error:
            raise self.open_error

    def send(self, chunk):
        if self.send_errors > 0:
            self.send_errors -= 1
            raise RuntimeError('send failed')
        self.sent += chunk

    def sync(self):
        self.syncs += 1

    def get_connected(self):
        return self.connected_code

    def set_metadata(self, metadata):
        if self.metadata_error:
            raise self.metadata_error
        self.metadata.append(metadata)

    def close(self):
        self.closes += 1


@pytest.fixture
def fake_shout():
    """A libshout handle stand-in that connects successfully."""
    return FakeShout()


@pytest.fixture
def fake_streamer():
    """An audio streamer stand-in that is on air."""
    return FakeStreamer()


@pytest.fixture
def fake_process():
    """An ffmpeg process stand-in with no output."""
    return FakeProcess()


@pytest.fixture
def popen_factory():
    """Build a Popen replacement returning a given process and recording its calls."""

    def factory(process):
        calls = []

        def popen(cmd, **kwargs):
            calls.append((cmd, kwargs))
            return process

        popen.calls = calls
        return popen

    return factory


def drain(output_queue):
    """Collect everything currently queued, stopping at the stop sentinel.

    Args:
        output_queue: Queue to drain

    Returns:
        list: Chunks read before the sentinel or the queue running dry
    """
    chunks = []
    while True:
        try:
            item = output_queue.get_nowait()
        except queue.Empty:
            return chunks
        if item is None:
            return chunks
        chunks.append(item)
