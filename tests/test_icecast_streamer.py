import queue
import time

import pytest

from classes.streamer.streamers.IcecastStreamer import IcecastStreamer
from tests.conftest import FakeProcess, FakeShout, FakeStreamer


def build_relay(streamer=None, process=None, shout=None, popen_factory=None, sleeps=None):
    """Build a relay wired to fakes, without starting any threads.

    Args:
        streamer: Source streamer stand-in
        process: ffmpeg process stand-in
        shout: libshout handle stand-in
        popen_factory: Optional recording Popen replacement
        sleeps: Optional list collecting backoff sleeps

    Returns:
        tuple: (relay, streamer, process, shout)
    """
    streamer = streamer or FakeStreamer()
    process = process or FakeProcess()
    shout = shout or FakeShout()

    def popen(cmd, **kwargs):
        if popen_factory is not None:
            popen_factory.append((cmd, kwargs))
        return process

    def sleep(delay):
        if sleeps is not None:
            sleeps.append(delay)

    relay = IcecastStreamer(
        streamer,
        popen=popen,
        shout_factory=lambda: shout,
        sleep=sleep,
    )
    return relay, streamer, process, shout


def wait_for(predicate, timeout=2.0):
    """Wait for a predicate to hold, so thread tests do not rely on sleeps.

    Args:
        predicate: Callable returning True once the condition is met
        timeout: Seconds to wait before giving up

    Returns:
        bool: True if the predicate held within the timeout
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return False


def test_configures_the_mount_from_the_environment():
    relay, _, _, shout = build_relay()

    relay.start()
    relay.stop()

    assert shout.settings['host'] == 'icecast.test'
    assert shout.settings['port'] == 8000
    assert shout.settings['mount'] == '/stream'
    assert shout.settings['user'] == 'source'
    assert shout.settings['password'] == 'hackme'
    assert shout.settings['protocol'] == 'http'
    assert shout.settings['format'] == 'mp3'
    assert shout.settings['name'] == 'Test Station'
    assert shout.settings['audio_info'] == {
        'bitrate': '128',
        'samplerate': '44100',
        'channels': '2',
    }


def test_start_opens_the_mount_and_attaches_to_the_source():
    relay, streamer, _, shout = build_relay()

    relay.start()

    assert shout.opens == 1
    assert relay.is_connected is True
    assert len(streamer.clients) == 1

    relay.stop()


def test_encoder_runs_at_the_configured_icecast_bitrate():
    calls = []
    relay, _, _, _ = build_relay(popen_factory=calls)

    relay.start()
    relay.stop()

    command = calls[0][0]
    assert command[0] == 'ffmpeg'
    assert '-b:a' in command
    assert command[command.index('-b:a') + 1] == '128k'


def test_a_refused_mount_raises_and_leaves_the_source_untouched():
    shout = FakeShout(open_error=RuntimeError('401 Unauthorized'))
    relay, streamer, _, _ = build_relay(shout=shout)

    with pytest.raises(RuntimeError, match='Could not connect to Icecast'):
        relay.start()

    assert relay.is_connected is False
    assert streamer.clients == []


def test_source_audio_is_written_to_the_encoder():
    relay, streamer, process, _ = build_relay()

    relay.start()
    client_queue = streamer.clients[0]
    client_queue.put(b'pcm-payload')

    assert wait_for(lambda: b'pcm-payload' in process.stdin.written)
    # The WAV header precedes the payload, so ffmpeg knows the input format
    assert process.stdin.written.startswith(b'RIFF')

    relay.stop()


def test_encoded_output_is_sent_to_icecast_and_paced():
    process = FakeProcess(stdout_chunks=[b'mp3-one', b'mp3-two'])
    relay, _, _, shout = build_relay(process=process)

    relay.start()

    assert wait_for(lambda: shout.sent == b'mp3-onemp3-two')
    # sync() paces the sender to real time, once per chunk
    assert shout.syncs == 2

    relay.stop()


def test_a_failed_send_reconnects_and_backs_off():
    process = FakeProcess(stdout_chunks=[b'one', b'two', b'three'])
    shout = FakeShout(send_errors=1)
    sleeps = []
    relay, _, _, _ = build_relay(process=process, shout=shout, sleeps=sleeps)

    relay.start()

    # The first send fails, so the mount is reopened and the later chunks land
    assert wait_for(lambda: shout.opens >= 2)
    assert wait_for(lambda: b'two' in shout.sent)
    assert sleeps and sleeps[0] == pytest.approx(0.01)

    relay.stop()


def test_stop_releases_the_source_and_terminates_the_encoder():
    relay, streamer, process, shout = build_relay()

    relay.start()
    client_queue = streamer.clients[0]
    relay.stop()

    assert client_queue in streamer.removed
    assert process.terminated is True or process.poll() is not None
    assert shout.closes == 1
    assert relay.is_connected is False


def test_stop_is_idempotent():
    relay, _, _, shout = build_relay()

    relay.start()
    relay.stop()
    relay.stop()

    assert shout.closes == 1


def test_stats_report_the_configured_mount():
    relay, _, _, _ = build_relay()

    relay.start()
    stats = relay.getStats()
    relay.stop()

    assert stats['enabled'] is True
    assert stats['connected'] is True
    assert stats['host'] == 'icecast.test'
    assert stats['mount'] == '/stream'
    assert stats['bitrate'] == 128
    assert stats['protocol'] == 'http'


def test_the_source_thread_stops_when_the_streamer_goes_off_air():
    streamer = FakeStreamer(on_air=False)
    relay, _, _, _ = build_relay(streamer=streamer)

    relay.start()

    assert wait_for(lambda: relay.running is False)

    relay.stop()
