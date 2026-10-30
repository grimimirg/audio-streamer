import pytest

from classes.streamer.streamers.ShoutcastStreamer import ShoutcastStreamer, shoutcast_settings
from tests.conftest import FakeProcess, FakeShout, FakeStreamer


def build_relay(streamer=None, process=None, shout=None, popen_calls=None, sleeps=None):
    """Build a Shoutcast relay wired to fakes, without starting any threads.

    Args:
        streamer: Source streamer stand-in
        process: ffmpeg process stand-in
        shout: libshout handle stand-in
        popen_calls: Optional list recording Popen calls
        sleeps: Optional list collecting backoff sleeps

    Returns:
        tuple: (relay, streamer, process, shout)
    """
    streamer = streamer or FakeStreamer()
    process = process or FakeProcess()
    shout = shout or FakeShout()

    def popen(cmd, **kwargs):
        if popen_calls is not None:
            popen_calls.append((cmd, kwargs))
        return process

    def sleep(delay):
        if sleeps is not None:
            sleeps.append(delay)

    relay = ShoutcastStreamer(streamer, popen=popen, shout_factory=lambda: shout, sleep=sleep)
    return relay, streamer, process, shout


def test_the_relay_speaks_the_icy_protocol():
    """libshout has no Shoutcast v2 support, so v1/ICY is what we can offer."""
    relay, _, _, shout = build_relay()

    relay.start()
    relay.stop()

    assert shout.settings['protocol'] == 'icy'
    assert shout.settings['format'] == 'mp3'


def test_the_mount_is_configured_from_the_environment():
    relay, _, _, shout = build_relay()

    relay.start()
    relay.stop()

    assert shout.settings['host'] == 'shoutcast.test'
    assert shout.settings['port'] == 8100
    assert shout.settings['mount'] == '/live'
    assert shout.settings['password'] == 'sc-secret'
    assert shout.settings['name'] == 'Test Station'


def test_the_settings_carry_the_shoutcast_prefix():
    """Error messages must point at the right environment variables."""
    settings = shoutcast_settings()

    assert settings.config_prefix == 'SHOUTCAST'
    assert settings.label == 'Shoutcast'
    assert settings.url == 'shoutcast://shoutcast.test:8100/live'


def test_stats_report_the_configured_mount():
    relay, _, _, _ = build_relay()

    relay.start()
    stats = relay.getStats()
    relay.stop()

    assert stats['enabled'] is True
    assert stats['connected'] is True
    assert stats['mount'] == '/live'
    assert stats['bitrate'] == 192
    assert stats['protocol'] == 'icy'


def test_the_encoder_runs_at_the_shoutcast_bitrate():
    calls = []
    relay, _, _, _ = build_relay(popen_calls=calls)

    relay.start()
    relay.stop()

    command = calls[0][0]
    assert command[command.index('-b:a') + 1] == '192k'


# -- Metadata --

def test_metadata_is_published_when_connected():
    relay, _, _, shout = build_relay()

    relay.start()
    sent = relay.update_metadata('Portishead - Roads')
    relay.stop()

    assert sent is True
    assert shout.metadata == [{'song': 'Portishead - Roads'}]


def test_metadata_is_not_published_before_the_relay_starts():
    """set_metadata on an unconnected libshout handle segfaults the process."""
    relay, _, _, shout = build_relay()

    assert relay.update_metadata('Portishead - Roads') is False
    assert shout.metadata == []


def test_metadata_is_not_published_when_libshout_reports_no_connection():
    """The handle may look present while libshout has already dropped the link."""
    shout = FakeShout(connected_code=-8)
    relay, _, _, _ = build_relay(shout=shout)

    relay.start()
    sent = relay.update_metadata('Portishead - Roads')
    relay.stop()

    assert sent is False
    assert shout.metadata == []


def test_metadata_is_not_published_after_stopping():
    relay, _, _, shout = build_relay()

    relay.start()
    relay.stop()

    assert relay.update_metadata('Portishead - Roads') is False


def test_an_empty_title_is_not_published():
    relay, _, _, shout = build_relay()

    relay.start()
    assert relay.update_metadata('') is False
    relay.stop()

    assert shout.metadata == []


def test_a_failing_metadata_update_does_not_raise():
    """Metadata is cosmetic; it must never disturb the audio."""
    shout = FakeShout(metadata_error=RuntimeError('rejected'))
    relay, _, _, _ = build_relay(shout=shout)

    relay.start()
    sent = relay.update_metadata('Portishead - Roads')
    relay.stop()

    assert sent is False


# -- Connection probe --

def test_the_probe_targets_the_shoutcast_server():
    attempts = []

    class FakeConnection:
        def close(self):
            pass

    def connect(address, timeout):
        attempts.append((address, timeout))
        return FakeConnection()

    assert ShoutcastStreamer.test_connection(connect=connect) is True
    assert attempts[0] == (('shoutcast.test', 8100), 5.0)


def test_the_probe_reports_a_refused_server():
    def connect(address, timeout):
        raise ConnectionRefusedError('refused')

    assert ShoutcastStreamer.test_connection(connect=connect) is False
