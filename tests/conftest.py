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
