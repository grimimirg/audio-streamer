import queue
import struct
from flask import render_template, Response

from classes.streamer.streamers.LiquidMusicStreamer import LiquidMusicStreamer
from utilities.Constants import CLIENT_QUEUE_SIZE
from utilities.Logger import Logger


class StreamHandler:
    """Handles audio streaming and basic routes."""

    def __init__(self, audio_streamer, radio_station_name: str):
        """Initialize the stream handler.
        
        Args:
            audio_streamer: Instance of the audio streamer
            radio_station_name: Name of the radio station
        """
        self.audio_streamer = audio_streamer
        self.radio_station_name = radio_station_name

    def player(self):
        """Serve the main web player interface.
        
        Returns:
            str: Rendered HTML template for the audio player
        """
        return render_template('index.html', radio_station_name=self.radio_station_name)

    def stream(self):
        """Serve the audio streaming endpoint.
        
        Returns:
            Response: Flask response with audio stream data
        """

        def generate_wav_stream():
            # WAV header for 44100 Hz, 16-bit, stereo
            sample_rate = 44100
            channels = 2
            bits_per_sample = 16
            byte_rate = sample_rate * channels * bits_per_sample // 8
            block_align = channels * bits_per_sample // 8

            # WAV header with proper sizes for Firefox compatibility
            # Use a large dummy size (2GB) to indicate streaming
            dummy_size = 0xFFFFFFFF
            header = struct.pack('<4sL4s', b'RIFF', dummy_size, b'WAVE')
            header += struct.pack('<4sLHHLLHH4sL',
                                  b'fmt ', 16, 1, channels, sample_rate,
                                  byte_rate, block_align, bits_per_sample, b'data', dummy_size)

            yield header

            # Stream audio data
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
            chunk_count = 0
            while True:
                try:
                    # Use timeout to prevent indefinite blocking
                    data = client_queue.get(timeout=1.0)
                    chunk_count += 1
                    yield data
                except queue.Empty:
                    # Check if streaming is still active
                    if not self.audio_streamer.onAir:
                        Logger.info("Audio streaming stopped, closing client connection")
                        break
                    # Continue waiting for data
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
            # Ensure client is removed even on errors
            self.audio_streamer.removeClient(client_queue)
            Logger.debug("Client queue removed from audio streamer")
