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
    ICECAST_BITRATE,
    ICECAST_HOST,
    ICECAST_MOUNT,
    ICECAST_PASSWORD,
    ICECAST_PORT,
    ICECAST_PROTOCOL,
    ICECAST_RECONNECT_DELAY,
    ICECAST_RECONNECT_MAX_DELAY,
    ICECAST_TEST_TIMEOUT,
    ICECAST_USER,
    RADIO_STATION_NAME,
)


def icecast_settings() -> RelaySettings:
    """Build the relay settings for the configured Icecast server.

    Returns:
        RelaySettings: Where this station publishes to Icecast
    """
    return RelaySettings(
        label='Icecast',
        scheme='icecast',
        host=ICECAST_HOST,
        port=ICECAST_PORT,
        mount=ICECAST_MOUNT,
        user=ICECAST_USER,
        password=ICECAST_PASSWORD,
        protocol=ICECAST_PROTOCOL,
        bitrate=ICECAST_BITRATE,
        station_name=RADIO_STATION_NAME,
        reconnect_delay=ICECAST_RECONNECT_DELAY,
        reconnect_max_delay=ICECAST_RECONNECT_MAX_DELAY,
        test_timeout=ICECAST_TEST_TIMEOUT,
        config_prefix='ICECAST',
    )


class IcecastStreamer(LibshoutRelay):
    """Relays the live audio to an Icecast server as a source client.

    See LibshoutRelay for how the relay attaches to the capturing streamer; this
    subclass only supplies the Icecast configuration.
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
            icecast_settings(),
            popen=popen,
            shout_factory=shout_factory,
            sleep=sleep,
        )

    @staticmethod
    def test_connection(connect=socket.create_connection) -> bool:
        """Check that the configured Icecast server is reachable.

        Args:
            connect: Connection factory, injectable for testing

        Returns:
            bool: True if the server accepted a TCP connection
        """
        return probe_server(icecast_settings(), connect=connect)
