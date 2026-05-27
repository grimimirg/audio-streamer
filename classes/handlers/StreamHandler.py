import queue
import struct
import subprocess
import threading
from flask import render_template, Response

from classes.streamer.streamers.LiquidMusicStreamer import LiquidMusicStreamer
from utilities.Constants import CLIENT_QUEUE_SIZE, FFMPEG_OUTPUT_QUEUE_SIZE, FFMPEG_QUEUE_TIMEOUT
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
        """Stream audio as MP3 with ffmpeg re-encoding at specified bitrate.
        
        Args:
            bitrate: Bitrate in kbps for re-encoding (e.g., 128, 192, 320)
        
        Returns:
            Response: Flask response with MP3 audio stream
        """
        ffmpeg_cmd = self._build_ffmpeg_command(bitrate)

        def generate_mp3_stream():
            process = None
            output_queue = None
            reader_thread = None
            error_monitor_thread = None
            try:
                process = self._start_ffmpeg_process(ffmpeg_cmd)
                output_queue = queue.Queue(maxsize=FFMPEG_OUTPUT_QUEUE_SIZE)
                reader_thread = threading.Thread(
                    target=self._read_ffmpeg_output,
                    args=(process, output_queue),
                    daemon=False
                )
                error_monitor_thread = threading.Thread(
                    target=self._monitor_ffmpeg_errors,
                    args=(process,),
                    daemon=True
                )
                reader_thread.start()
                error_monitor_thread.start()
                yield from self._stream_through_ffmpeg(process, output_queue)
            except GeneratorExit:
                Logger.info("Client disconnected from MP3 stream")
            except Exception as e:
                Logger.error(f"Error in MP3 stream generator: {type(e).__name__}: {str(e)}")
            finally:
                # Signal reader thread to stop first
                if output_queue:
                    output_queue.put(None)
                # Wait for reader thread to finish
                if reader_thread and reader_thread.is_alive():
                    reader_thread.join(timeout=1.0)
                # Then cleanup process
                if process:
                    self._cleanup_ffmpeg_process(process)

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

    def _generate_wav_header(self):
        """Generate WAV header for streaming.
        
        Returns:
            bytes: WAV header bytes
        """
        sample_rate = 44100
        channels = 2
        bits_per_sample = 16
        byte_rate = sample_rate * channels * bits_per_sample // 8
        block_align = channels * bits_per_sample // 8
        dummy_size = 0xFFFFFFFF

        header = struct.pack('<4sL4s', b'RIFF', dummy_size, b'WAVE')
        header += struct.pack('<4sLHHLLHH4sL',
                              b'fmt ', 16, 1, channels, sample_rate,
                              byte_rate, block_align, bits_per_sample, b'data', dummy_size)
        return header

    def _build_ffmpeg_command(self, bitrate: int):
        """Build ffmpeg command for MP3 encoding.
        
        Args:
            bitrate: Bitrate in kbps for re-encoding
        
        Returns:
            list: FFmpeg command as list of arguments
        """
        return [
            'ffmpeg',
            '-i', 'pipe:0',
            '-f', 'mp3',
            '-codec:a', 'libmp3lame',
            '-b:a', f'{bitrate}k',
            '-ar', '44100',
            '-ac', '2',
            '-bufsize', '64k',
            '-'
        ]

    def _start_ffmpeg_process(self, ffmpeg_cmd):
        """Start ffmpeg process for encoding.
        
        Args:
            ffmpeg_cmd: List of ffmpeg command arguments
        
        Returns:
            subprocess.Popen: The ffmpeg process
        
        Raises:
            RuntimeError: If ffmpeg is not found
        """
        try:
            return subprocess.Popen(
                ffmpeg_cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
        except FileNotFoundError:
            Logger.error("ffmpeg not found. Please install ffmpeg to use bitrate-based streaming.")
            raise RuntimeError("ffmpeg is required for bitrate-based streaming")

    def _stream_through_ffmpeg(self, process, output_queue):
        """Stream audio data through ffmpeg process.
        
        Args:
            process: The ffmpeg subprocess
            output_queue: Queue to read encoded data from
        
        Yields:
            bytes: Encoded MP3 chunks
        """
        # Write WAV header first
        process.stdin.write(self._generate_wav_header())
        
        try:
            for chunk in self._generate_audio_stream():
                try:
                    process.stdin.write(chunk)
                    process.stdin.flush()
                    # Drain all available encoded data from queue
                    while True:
                        try:
                            encoded_chunk = output_queue.get(timeout=FFMPEG_QUEUE_TIMEOUT)
                            if encoded_chunk is None:  # Sentinel value to stop
                                return
                            yield encoded_chunk
                        except queue.Empty:
                            # No more data available, continue writing
                            break
                except BrokenPipeError:
                    Logger.error("ffmpeg process broken pipe")
                    break
                except IOError as e:
                    Logger.error(f"Error writing to ffmpeg: {e}")
                    break
        except GeneratorExit:
            # Client disconnected, drain queue without yielding
            while True:
                try:
                    encoded_chunk = output_queue.get(timeout=FFMPEG_QUEUE_TIMEOUT)
                    if encoded_chunk is None:
                        break
                except queue.Empty:
                    break
            raise  # Re-raise GeneratorExit to properly close the generator

    def _read_ffmpeg_output(self, process, output_queue):
        """Read ffmpeg output in a separate thread to avoid blocking.
        
        Args:
            process: The ffmpeg subprocess
            output_queue: Queue to put encoded data into
        """
        try:
            while True:
                try:
                    chunk = process.stdout.read(8192)
                    if not chunk:
                        # EOF reached
                        break
                    # Use put_nowait to avoid blocking if queue is full
                    try:
                        output_queue.put_nowait(chunk)
                    except queue.Full:
                        # Drop chunk if queue is full to prevent blocking
                        Logger.warning("Output queue full, dropping encoded chunk")
                except Exception as e:
                    Logger.error(f"Error reading from ffmpeg: {e}")
                    break
        except Exception as e:
            Logger.error(f"Error in ffmpeg reader thread: {e}")
        finally:
            # Signal that reading is complete
            try:
                output_queue.put_nowait(None)
            except queue.Full:
                pass  # Queue might be full, thread will exit anyway

    def _monitor_ffmpeg_errors(self, process):
        """Monitor ffmpeg stderr for errors in a separate thread.
        
        Args:
            process: The ffmpeg subprocess
        """
        try:
            while True:
                try:
                    error_line = process.stderr.readline()
                    if not error_line:
                        # EOF reached
                        break
                    error_line = error_line.decode('utf-8', errors='ignore').strip()
                    if error_line:
                        # Filter out common non-error messages
                        if 'error' in error_line.lower() or 'fatal' in error_line.lower():
                            Logger.error(f"FFmpeg error: {error_line}")
                        elif 'warning' in error_line.lower():
                            Logger.warning(f"FFmpeg warning: {error_line}")
                except Exception as e:
                    Logger.error(f"Error reading ffmpeg stderr: {e}")
                    break
        except Exception as e:
            Logger.error(f"Error in ffmpeg error monitor thread: {e}")

    def _cleanup_ffmpeg_process(self, process):
        """Clean up ffmpeg process resources.
        
        Args:
            process: The ffmpeg subprocess to cleanup
        """
        try:
            # Close stdin first to signal EOF to ffmpeg
            if process.stdin and not process.stdin.closed:
                process.stdin.close()
            # Close stdout and stderr
            if process.stdout and not process.stdout.closed:
                process.stdout.close()
            if process.stderr and not process.stderr.closed:
                process.stderr.close()
            # Terminate the process
            if process.poll() is None:  # Process is still running
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    Logger.warning("ffmpeg process did not terminate, killing it")
                    process.kill()
                    process.wait()
        except Exception as e:
            Logger.error(f"Error cleaning up ffmpeg process: {e}")

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
