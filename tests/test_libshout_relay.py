from classes.streamer.LibshoutRelay import RelaySettings, probe_server


def build_settings(**overrides):
    """Build relay settings with recognisable defaults.

    Args:
        **overrides: Fields to replace

    Returns:
        RelaySettings: Settings for a fictional server
    """
    fields = dict(
        label='Testcast',
        scheme='testcast',
        host='relay.test',
        port=9000,
        mount='/mount',
        user='source',
        password='secret',
        protocol='http',
        bitrate=128,
        station_name='Test Station',
        reconnect_delay=1.0,
        reconnect_max_delay=4.0,
        test_timeout=2.0,
        config_prefix='TESTCAST',
    )
    fields.update(overrides)
    return RelaySettings(**fields)


def test_the_url_describes_the_mount():
    assert build_settings().url == 'testcast://relay.test:9000/mount'


def test_the_probe_uses_the_settings_address_and_timeout():
    attempts = []

    class FakeConnection:
        def close(self):
            attempts.append('closed')

    def connect(address, timeout):
        attempts.append((address, timeout))
        return FakeConnection()

    assert probe_server(build_settings(), connect=connect) is True
    assert attempts[0] == (('relay.test', 9000), 2.0)
    assert 'closed' in attempts


def test_the_probe_survives_a_close_that_fails():
    """A probe is informational; cleaning up must not raise."""
    class FakeConnection:
        def close(self):
            raise OSError('already gone')

    assert probe_server(build_settings(), connect=lambda a, t: FakeConnection()) is True


def test_the_probe_reports_an_unreachable_server():
    def connect(address, timeout):
        raise OSError('no route to host')

    assert probe_server(build_settings(), connect=connect) is False
