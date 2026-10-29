import queue

import pytest

from classes.handlers import StreamHandler as stream_handler_module
from classes.handlers.StreamHandler import StreamHandler
from classes.streamer.BitrateEncoderPool import Subscription


class FakeEncoder:
    """Encoder stand-in reporting whether it is still running."""

    def __init__(self, running=True):
        self.running = running


class FakePool:
    """Encoder pool stand-in recording subscribe/unsubscribe traffic."""

    def __init__(self, chunks=None, running=True):
        self.subscribed = []
        self.unsubscribed = []
        self.shutdowns = 0
        self._chunks = list(chunks or [])
        self._running = running
        self.active_encoders = 0

    def subscribe(self, bitrate):
        output_queue = queue.Queue()
        for chunk in self._chunks:
            output_queue.put(chunk)
        output_queue.put(None)  # Stop sentinel
        subscription = Subscription(bitrate, FakeEncoder(self._running), output_queue)
        self.subscribed.append(bitrate)
        return subscription

    def unsubscribe(self, subscription):
        self.unsubscribed.append(subscription)

    def shutdown(self):
        self.shutdowns += 1


@pytest.fixture
def handler(fake_streamer):
    """A stream handler wired to a fake encoder pool."""
    return StreamHandler(fake_streamer, 'Test Radio', encoder_pool=FakePool())


# -- Routing --

def test_stream_without_bitrate_serves_wav(handler):
    response = handler.stream()

    assert response.mimetype == 'audio/wav'
    assert handler.encoder_pool.subscribed == []


def test_stream_with_bitrate_serves_mp3_from_the_pool(fake_streamer):
    pool = FakePool(chunks=[b'one', b'two'])
    handler = StreamHandler(fake_streamer, 'Test Radio', encoder_pool=pool)

    response = handler.stream(192)
    body = b''.join(response.response)

    assert response.mimetype == 'audio/mpeg'
    assert body == b'onetwo'
    assert pool.subscribed == [192]


def test_mp3_stream_unsubscribes_when_the_listener_leaves(fake_streamer):
    pool = FakePool(chunks=[b'one'])
    handler = StreamHandler(fake_streamer, 'Test Radio', encoder_pool=pool)

    generator = handler.stream(192).response
    next(iter(generator))
    generator.close()

    assert len(pool.unsubscribed) == 1


def test_mp3_stream_unsubscribes_when_subscribe_fails(fake_streamer, mocker):
    pool = FakePool()
    mocker.patch.object(pool, 'subscribe', side_effect=RuntimeError('ffmpeg is required'))
    handler = StreamHandler(fake_streamer, 'Test Radio', encoder_pool=pool)

    body = b''.join(handler.stream(192).response)

    assert body == b''
    assert pool.unsubscribed == [None]


def test_mp3_stream_response_headers_disable_caching(handler):
    response = handler.stream(192)

    assert response.headers['Cache-Control'] == 'no-cache, no-store'
    assert response.headers['Accept-Ranges'] == 'none'


def test_shutdown_shuts_down_the_pool(handler):
    handler.shutdown()

    assert handler.encoder_pool.shutdowns == 1


# -- Subscription consumption --

def test_consume_stops_at_the_sentinel(handler):
    output_queue = queue.Queue()
    output_queue.put(b'chunk')
    output_queue.put(None)
    subscription = Subscription(192, FakeEncoder(), output_queue)

    assert list(handler._consume_subscription(subscription)) == [b'chunk']


def test_consume_stops_when_the_encoder_is_no_longer_running(handler):
    subscription = Subscription(192, FakeEncoder(running=False), queue.Queue())

    assert list(handler._consume_subscription(subscription)) == []


# -- FFmpeg command --

def test_command_carries_the_requested_bitrate(handler):
    command = handler._build_ffmpeg_command(192)

    assert command[0] == 'ffmpeg'
    assert command[command.index('-b:a') + 1] == '192k'
    assert command[-1] == '-'


def test_command_omits_resampling_when_the_source_already_matches(handler):
    command = handler._build_ffmpeg_command(128)

    assert '-ar' not in command
    assert '-ac' not in command


def test_command_resamples_when_the_source_differs(handler, monkeypatch):
    monkeypatch.setattr(stream_handler_module, 'RATE', 48000)
    monkeypatch.setattr(stream_handler_module, 'CHANNELS', 1)

    command = handler._build_ffmpeg_command(128)

    assert command[command.index('-ar') + 1] == '44100'
    assert command[command.index('-ac') + 1] == '2'


def test_command_omits_thread_limit_when_unset(handler):
    command = handler._build_ffmpeg_command(128)

    assert '-threads' not in command


def test_command_applies_the_configured_thread_limit(handler, monkeypatch):
    monkeypatch.setattr(stream_handler_module, 'FFMPEG_THREADS', 2)

    command = handler._build_ffmpeg_command(128)

    assert command[command.index('-threads') + 1] == '2'


# -- WAV header --

def test_wav_header_is_unchanged(handler):
    header = handler._generate_wav_header()

    assert header.startswith(b'RIFF')
    assert header[8:12] == b'WAVE'
    assert len(header) == 44
    assert header == (
        b'RIFF\xff\xff\xff\xffWAVEfmt \x10\x00\x00\x00\x01\x00\x02\x00'
        b'\x44\xac\x00\x00\x10\xb1\x02\x00\x04\x00\x10\x00data\xff\xff\xff\xff'
    )
