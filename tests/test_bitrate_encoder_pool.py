import queue

import pytest

from classes.streamer.BitrateEncoderPool import BitrateEncoder, BitrateEncoderPool
from tests.conftest import FakeProcess, FakeStreamer, drain


def build_command(bitrate):
    """Build a recognisable command for a bitrate."""
    return ['ffmpeg', '-b:a', f'{bitrate}k']


class StubEncoder:
    """Encoder stand-in that records lifecycle calls without starting threads."""

    instances = []

    def __init__(self, bitrate, audio_streamer, ffmpeg_cmd):
        self.bitrate = bitrate
        self.audio_streamer = audio_streamer
        self.ffmpeg_cmd = ffmpeg_cmd
        self.running = False
        self.starts = 0
        self.stops = 0
        self.subscriptions = []
        StubEncoder.instances.append(self)

    def start(self):
        self.starts += 1
        self.running = True

    def stop(self):
        self.stops += 1
        self.running = False

    def subscribe(self):
        from classes.streamer.BitrateEncoderPool import Subscription
        subscription = Subscription(self.bitrate, self, queue.Queue())
        self.subscriptions.append(subscription)
        return subscription

    def unsubscribe(self, subscription):
        if subscription in self.subscriptions:
            self.subscriptions.remove(subscription)
        return len(self.subscriptions)


@pytest.fixture
def pool(fake_streamer):
    """A pool backed by StubEncoder."""
    StubEncoder.instances = []
    return BitrateEncoderPool(fake_streamer, build_command, encoder_factory=StubEncoder)


# -- Pool reference counting --

def test_second_listener_on_same_bitrate_reuses_the_encoder(pool):
    first = pool.subscribe(192)
    second = pool.subscribe(192)

    assert len(StubEncoder.instances) == 1
    assert first.encoder is second.encoder
    assert StubEncoder.instances[0].starts == 1


def test_different_bitrates_get_their_own_encoder(pool):
    pool.subscribe(128)
    pool.subscribe(320)

    assert len(StubEncoder.instances) == 2
    assert pool.active_encoders == 2
    assert [e.bitrate for e in StubEncoder.instances] == [128, 320]
    assert StubEncoder.instances[0].ffmpeg_cmd == build_command(128)


def test_encoder_stops_only_when_its_last_listener_leaves(pool):
    first = pool.subscribe(192)
    second = pool.subscribe(192)
    encoder = first.encoder

    pool.unsubscribe(first)
    assert encoder.stops == 0
    assert pool.active_encoders == 1

    pool.unsubscribe(second)
    assert encoder.stops == 1
    assert pool.active_encoders == 0


def test_resubscribing_after_teardown_starts_a_fresh_encoder(pool):
    first = pool.subscribe(192)
    pool.unsubscribe(first)

    second = pool.subscribe(192)

    assert len(StubEncoder.instances) == 2
    assert second.encoder is not first.encoder
    assert second.encoder.running is True


def test_unsubscribe_does_not_evict_a_replacement_encoder(pool):
    """A late unsubscribe must not tear down the encoder that replaced its own."""
    stale = pool.subscribe(192)
    stale_encoder = stale.encoder
    stale_encoder.running = False  # Simulate the encoder dying

    live = pool.subscribe(192)  # Pool starts a replacement
    assert live.encoder is not stale_encoder

    pool.unsubscribe(stale)

    assert pool.active_encoders == 1
    assert live.encoder.stops == 0


def test_unsubscribe_tolerates_no_subscription(pool):
    pool.unsubscribe(None)  # Happens when subscribe() itself failed

    assert pool.active_encoders == 0


def test_shutdown_stops_every_encoder(pool):
    pool.subscribe(128)
    pool.subscribe(320)

    pool.shutdown()

    assert pool.active_encoders == 0
    assert all(encoder.stops == 1 for encoder in StubEncoder.instances)


def test_subscribe_propagates_missing_ffmpeg(fake_streamer):
    def exploding_popen(*_args, **_kwargs):
        raise FileNotFoundError('ffmpeg')

    pool = BitrateEncoderPool(
        fake_streamer,
        build_command,
        encoder_factory=lambda bitrate, streamer, cmd: BitrateEncoder(
            bitrate, streamer, cmd, popen=exploding_popen
        )
    )

    with pytest.raises(RuntimeError, match='ffmpeg is required'):
        pool.subscribe(192)


# -- Encoder fan-out --

def build_encoder(streamer=None, process=None, popen_calls=None):
    """Build an encoder wired to a fake process, without starting it."""
    streamer = streamer or FakeStreamer()
    process = process or FakeProcess()

    def popen(cmd, **kwargs):
        if popen_calls is not None:
            popen_calls.append((cmd, kwargs))
        return process

    encoder = BitrateEncoder(192, streamer, build_command(192), popen=popen)
    encoder.process = process
    encoder.running = True
    return encoder, process


def test_broadcast_delivers_the_chunk_to_every_listener():
    encoder, _ = build_encoder()
    first = encoder.subscribe()
    second = encoder.subscribe()

    encoder._broadcast(b'mp3data')

    assert drain(first.queue) == [b'mp3data']
    assert drain(second.queue) == [b'mp3data']


def test_full_listener_queue_drops_only_that_listener(mocker):
    warning = mocker.patch('classes.streamer.BitrateEncoderPool.Logger.warning')
    encoder, _ = build_encoder()
    slow = encoder.subscribe()
    fast = encoder.subscribe()
    slow.queue = queue.Queue(maxsize=1)
    slow.queue.put(b'already-queued')

    encoder._broadcast(b'new-chunk')

    assert drain(fast.queue) == [b'new-chunk']
    assert drain(slow.queue) == [b'already-queued']
    warning.assert_called_once()


def test_unsubscribed_listener_receives_nothing_further():
    encoder, _ = build_encoder()
    leaving = encoder.subscribe()
    staying = encoder.subscribe()

    remaining = encoder.unsubscribe(leaving)
    encoder._broadcast(b'after-leaving')

    assert remaining == 1
    assert drain(leaving.queue) == []
    assert drain(staying.queue) == [b'after-leaving']


def test_unsubscribe_is_idempotent():
    encoder, _ = build_encoder()
    subscription = encoder.subscribe()

    assert encoder.unsubscribe(subscription) == 0
    assert encoder.unsubscribe(subscription) == 0


def test_subscriber_count_tracks_listeners():
    encoder, _ = build_encoder()

    assert encoder.subscriber_count == 0
    first = encoder.subscribe()
    assert encoder.subscriber_count == 1
    encoder.unsubscribe(first)
    assert encoder.subscriber_count == 0


def test_closing_subscribers_sends_the_stop_sentinel():
    encoder, _ = build_encoder()
    subscription = encoder.subscribe()

    encoder._close_subscribers()

    assert subscription.queue.get_nowait() is None


# -- Encoder lifecycle --

def test_start_registers_one_source_client_and_writes_the_wav_header():
    streamer = FakeStreamer(on_air=False)  # Lets the source thread exit immediately
    process = FakeProcess()
    popen_calls = []
    encoder, _ = build_encoder(streamer, process, popen_calls)
    encoder.running = False
    encoder.process = None

    encoder.start()
    encoder.stop()

    assert popen_calls[0][0] == build_command(192)
    assert len(streamer.removed) == 1  # The single source client, released on stop
    assert process.stdin.written.startswith(b'RIFF')


def test_stop_releases_the_source_client_and_terminates_ffmpeg():
    streamer = FakeStreamer(on_air=False)
    process = FakeProcess(return_code=None)
    encoder, _ = build_encoder(streamer, process)
    encoder._threads = []

    encoder.stop()

    assert encoder.running is False
    assert streamer.removed == [encoder._source_queue]
    assert process.terminated is True
    assert process.stdin.closed is True


def test_stop_is_idempotent():
    streamer = FakeStreamer(on_air=False)
    encoder, process = build_encoder(streamer)
    encoder._threads = []

    encoder.stop()
    encoder.stop()

    assert len(streamer.removed) == 1


def test_stop_closes_out_remaining_listeners():
    streamer = FakeStreamer(on_air=False)
    encoder, _ = build_encoder(streamer)
    encoder._threads = []
    subscription = encoder.subscribe()

    encoder.stop()

    assert subscription.queue.get_nowait() is None


def test_missing_ffmpeg_raises_runtime_error():
    def exploding_popen(*_args, **_kwargs):
        raise FileNotFoundError('ffmpeg')

    encoder = BitrateEncoder(192, FakeStreamer(), build_command(192), popen=exploding_popen)

    with pytest.raises(RuntimeError, match='ffmpeg is required'):
        encoder.start()


def test_output_pump_fans_out_until_eof_then_closes_listeners():
    streamer = FakeStreamer(on_air=False)
    process = FakeProcess(stdout_chunks=[b'one', b'two'])
    encoder, _ = build_encoder(streamer, process)
    subscription = encoder.subscribe()

    encoder._pump_output()

    assert drain(subscription.queue) == [b'one', b'two']
    assert encoder.running is False


def test_source_pump_stops_when_the_streamer_goes_off_air():
    streamer = FakeStreamer(on_air=False)
    encoder, process = build_encoder(streamer)

    encoder._pump_source()

    assert encoder.running is False
    assert process.stdin.closed is True


def test_source_pump_forwards_audio_chunks_to_ffmpeg():
    streamer = FakeStreamer(on_air=False)
    encoder, process = build_encoder(streamer)
    encoder._source_queue.put(b'pcm-chunk')
    encoder._source_queue.put(None)  # Stop sentinel

    encoder._pump_source()

    assert process.stdin.written.endswith(b'pcm-chunk')


def test_broken_pipe_while_writing_stops_the_encoder(mocker):
    streamer = FakeStreamer()
    encoder, process = build_encoder(streamer)
    mocker.patch.object(process.stdin, 'write', side_effect=BrokenPipeError)

    encoder._pump_source()

    assert encoder.running is False


def test_stderr_monitor_logs_errors_and_warnings(mocker):
    error = mocker.patch('classes.streamer.BitrateEncoderPool.Logger.error')
    warning = mocker.patch('classes.streamer.BitrateEncoderPool.Logger.warning')
    process = FakeProcess(stderr_lines=[
        b'Error while decoding stream\n',
        b'warning: something odd\n',
        b'\n',
        b'frame= 123 fps=30\n',
    ])
    encoder, _ = build_encoder(process=process)

    encoder._monitor_errors()

    assert error.call_count == 1
    assert warning.call_count == 1


def test_replacing_a_dead_encoder_stops_it_first(pool):
    """A self-terminated encoder must be stopped, or its source client leaks."""
    first = pool.subscribe(192)
    dead = first.encoder
    dead.running = False  # The encoder wound itself down

    second = pool.subscribe(192)

    assert dead.stops == 1
    assert second.encoder is not dead
    assert pool.active_encoders == 1
