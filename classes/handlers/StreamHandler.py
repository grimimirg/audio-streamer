import queue
from flask import render_template, Response

from classes.streamer.BitrateEncoderPool import BitrateEncoderPool
from classes.streamer.streamers.LiquidMusicStreamer import LiquidMusicStreamer
from utilities.AudioFormat import build_wav_header
from utilities.Constants import CHANNELS, CLIENT_QUEUE_SIZE, FFMPEG_QUEUE_TIMEOUT, RATE, STREAM_BITRATES
from utilities.FfmpegCommand import build_mp3_command
from utilities.Logger import Logger


class StreamHandler:
    """Handles audio streaming and basic routes."""

    def __init__(self, audio_streamer, radio_station_name: str, encoder_pool=None):
        """Initialize the stream handler.

        Args:
            audio_streamer: Instance of the audio streamer
            radio_station_name: Name of the radio station
            encoder_pool: Shared bitrate encoder pool, injectable for testing
        """
        self.audio_streamer = audio_streamer
        self.radio_station_name = radio_station_name
        self.encoder_pool = encoder_pool or BitrateEncoderPool(audio_streamer, self._build_ffmpeg_command)

    def player(self):
        """Serve the main web player interface.

        Returns:
            str: Rendered HTML template for the audio player
        """
        return render_template('index.html',
                               radio_station_name=self.radio_station_name,
                               stream_bitrates=STREAM_BITRATES)

    def stream(self, bitrate: int = None):
        """Serve the audio streaming endpoint.

        Args:
            bitrate: Optional bitrate in kbps for re-encoding (e.g., 128, 192, 320).
                    If None, streams original WAV without re-encoding.

        Returns:
            Response: Flask response with audio stream data
        """
        if bitrate is None:
            return self._stream_wav()
        else:
            return self._stream_mp3(bitrate)

    def _stream_wav(self):
        """Stream audio as WAV without re-encoding.

        Returns:
            Response: Flask response with WAV audio stream
        """
        def generate_wav_stream():
            yield self._generate_wav_header()
            for chunk in self._generate_audio_stream():
                yield chunk

        return Response(
            generate_wav_stream(),
            mimetype='audio/wav',
            headers={
                'Cache-Control': 'no-cache, no-store',
                'Connection': 'keep-alive',
                'Access-Control-Allow-Origin': '*',
                'Accept-Ranges': 'none'
            }
        )

    def _stream_mp3(self, bitrate: int):
        """Stream audio as MP3 at the specified bitrate.

        Listeners on the same bitrate share a single ffmpeg encoder from the pool,
        so the audio is encoded once regardless of how many are connected.

        Args:
            bitrate: Bitrate in kbps for re-encoding (e.g., 128, 192, 320)

        Returns:
            Response: Flask response with MP3 audio stream
        """
        def generate_mp3_stream():
            subscription = None
            try:
                subscription = self.encoder_pool.subscribe(bitrate)
                Logger.info(f"New MP3 stream client connected at {bitrate}kbps")
                yield from self._consume_subscription(subscription)
            except GeneratorExit:
                Logger.info("Client disconnected from MP3 stream")
            except Exception as e:
                Logger.error(f"Error in MP3 stream generator: {type(e).__name__}: {str(e)}")
            finally:
                self.encoder_pool.unsubscribe(subscription)

        return Response(
            generate_mp3_stream(),
            mimetype='audio/mpeg',
            headers={
                'Cache-Control': 'no-cache, no-store',
                'Connection': 'keep-alive',
                'Access-Control-Allow-Origin': '*',
                'Accept-Ranges': 'none'
            }
        )

    def stats(self):
        """Serve streaming statistics endpoint.

        Returns:
            dict: Current streaming statistics as JSON
        """
        return self.audio_streamer.getStats()

    def dashboard(self):
        """Serve the dashboard interface.

        Returns:
            str: Rendered HTML template for the dashboard
        """
        # Check if the streamer is LiquidMusicStreamer
        if isinstance(self.audio_streamer, LiquidMusicStreamer):
            return render_template('dashboard_liquid.html', radio_station_name=self.radio_station_name)
        return render_template('dashboard.html', radio_station_name=self.radio_station_name)

    def dashboard_liquid(self):
        """Serve the liquid music dashboard interface.

        Returns:
            str: Rendered HTML template for the liquid music dashboard
        """
        return render_template('dashboard_liquid.html', radio_station_name=self.radio_station_name)

    def streamer_type(self):
        """Get the current streamer type.

        Returns:
            dict: JSON response with the streamer type
        """
        streamer_type = 'standard'
        if isinstance(self.audio_streamer, LiquidMusicStreamer):
            streamer_type = 'liquid'

        return {'streamer_type': streamer_type}

    def shutdown(self):
        """Stop every shared encoder owned by this handler."""
        self.encoder_pool.shutdown()

    def _generate_wav_header(self):
        """Generate WAV header for streaming.

        Returns:
            bytes: WAV header bytes
        """
        return build_wav_header(RATE, CHANNELS)

    def _build_ffmpeg_command(self, bitrate: int):
        """Build ffmpeg command for MP3 encoding.

        Args:
            bitrate: Bitrate in kbps for re-encoding

        Returns:
            list: FFmpeg command as list of arguments
        """
        return build_mp3_command(bitrate)

    def _consume_subscription(self, subscription):
        """Yield encoded chunks from a subscription until its encoder stops.

        Args:
            subscription: The listener's subscription handle

        Yields:
            bytes: Encoded MP3 chunks
        """
        while True:
            try:
                chunk = subscription.queue.get(timeout=FFMPEG_QUEUE_TIMEOUT)
            except queue.Empty:
                if not subscription.encoder.running:
                    Logger.info("Encoder stopped, closing MP3 client connection")
                    break
                continue

            if chunk is None:  # Sentinel value: the encoder has stopped
                break

            yield chunk

    def _generate_audio_stream(self):
        """Generate audio stream data for HTTP response.

        Creates a client queue, registers it with the audio streamer,
        and yields audio chunks as they become available.

        Yields:
            bytes: Raw audio data chunks
        """
        client_queue = queue.Queue(maxsize=CLIENT_QUEUE_SIZE)
        self.audio_streamer.addClient(client_queue)
        Logger.info("New audio stream client connected")

        try:
            while True:
                try:
                    data = client_queue.get(timeout=1.0)
                    yield data
                except queue.Empty:
                    if not self.audio_streamer.onAir:
                        Logger.info("Audio streaming stopped, closing client connection")
                        break
                    Logger.warning(f"Queue empty, waiting... (stream active: {self.audio_streamer.onAir})")
                    continue
                except Exception as e:
                    Logger.error(f"Error while getting data from queue: {type(e).__name__}: {str(e)}")
                    break

        except GeneratorExit:
            Logger.info("Client disconnected from audio stream")
        except Exception as e:
            Logger.error(f"Unexpected error in audio stream generator: {type(e).__name__}: {str(e)}")
        finally:
            self.audio_streamer.removeClient(client_queue)
            Logger.debug("Client queue removed from audio streamer")
