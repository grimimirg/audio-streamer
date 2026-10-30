import socket
import subprocess
import time

from classes.streamer.LibshoutRelay import (
    LibshoutRelay,
    RelaySettings,
    default_shout_factory,
    probe_server,
)
from utilities.Constants import (
    RADIO_STATION_NAME,
    SHOUTCAST_BITRATE,
    SHOUTCAST_HOST,
    SHOUTCAST_MOUNT,
    SHOUTCAST_PASSWORD,
    SHOUTCAST_PORT,
    SHOUTCAST_RECONNECT_DELAY,
    SHOUTCAST_RECONNECT_MAX_DELAY,
    SHOUTCAST_TEST_TIMEOUT,
    SHOUTCAST_USER,
)

# libshout 2.4 implements the ICY source protocol, which is Shoutcast v1. The
# v2 protocol (Ultravox) is not among libshout's four protocols - HTTP,
# XAUDIOCAST, ICY and ROARAUDIO - so it cannot be spoken through this library.
# DNAS 2 servers still accept v1 sources on their legacy source port.
SHOUTCAST_PROTOCOL = 'icy'


def shoutcast_settings() -> RelaySettings:
    """Build the relay settings for the configured Shoutcast server.

    Returns:
        RelaySettings: Where this station publishes to Shoutcast
    """
    return RelaySettings(
        label='Shoutcast',
        scheme='shoutcast',
        host=SHOUTCAST_HOST,
        port=SHOUTCAST_PORT,
        mount=SHOUTCAST_MOUNT,
        user=SHOUTCAST_USER,
        password=SHOUTCAST_PASSWORD,
        protocol=SHOUTCAST_PROTOCOL,
        bitrate=SHOUTCAST_BITRATE,
        station_name=RADIO_STATION_NAME,
        reconnect_delay=SHOUTCAST_RECONNECT_DELAY,
        reconnect_max_delay=SHOUTCAST_RECONNECT_MAX_DELAY,
        test_timeout=SHOUTCAST_TEST_TIMEOUT,
        config_prefix='SHOUTCAST',
    )


class ShoutcastStreamer(LibshoutRelay):
    """Relays the live audio to a Shoutcast server as a source client.

    Speaks the ICY source protocol (Shoutcast v1), which DNAS 2 also accepts on
    its legacy source port. See LibshoutRelay for how the relay attaches to the
    capturing streamer; this subclass only supplies the Shoutcast configuration.
    """

    def __init__(self, audio_streamer, popen=subprocess.Popen,
                 shout_factory=default_shout_factory, sleep=time.sleep):
        """Initialize the relay.

        Args:
            audio_streamer: The capturing streamer to read source audio from
            popen: Process factory, injectable for testing
            shout_factory: Callable returning a libshout handle, injectable for testing
            sleep: Sleep function used for reconnect backoff, injectable for testing
        """
        super().__init__(
            audio_streamer,
            shoutcast_settings(),
            popen=popen,
            shout_factory=shout_factory,
            sleep=sleep,
        )

    @staticmethod
    def test_connection(connect=socket.create_connection) -> bool:
        """Check that the configured Shoutcast server is reachable.

        Args:
            connect: Connection factory, injectable for testing

        Returns:
            bool: True if the server accepted a TCP connection
        """
        return probe_server(shoutcast_settings(), connect=connect)
