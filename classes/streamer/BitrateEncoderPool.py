import queue
import subprocess
import threading

from utilities.AudioFormat import build_wav_header
from utilities.Constants import CHANNELS, CLIENT_QUEUE_SIZE, FFMPEG_OUTPUT_QUEUE_SIZE, FFMPEG_QUEUE_TIMEOUT, RATE
from utilities.Logger import Logger


class Subscription:
    """A single listener attached to a shared bitrate encoder."""

    def __init__(self, bitrate: int, encoder, output_queue: queue.Queue):
        """Initialize the subscription.

        Args:
            bitrate: Bitrate in kbps this subscription is listening at
            encoder: The BitrateEncoder feeding this subscription
            output_queue: Queue encoded chunks are delivered on
        """
        self.bitrate = bitrate
        self.encoder = encoder
        self.queue = output_queue


class BitrateEncoder:
    """A single ffmpeg encoder shared by every listener of one bitrate.

    Reads the source audio once, encodes it once, and fans the encoded output out
    to all subscribed listeners. Without this, each listener would run its own
    ffmpeg process and the source would be read once per listener.
    """

    def __init__(self, bitrate: int, audio_streamer, ffmpeg_cmd, popen=subprocess.Popen):
        """Initialize the encoder.

        Args:
            bitrate: Bitrate in kbps to encode at
            audio_streamer: Instance of the audio streamer to read source audio from
            ffmpeg_cmd: FFmpeg command as list of arguments
            popen: Process factory, injectable for testing
        """
        self.bitrate = bitrate
        self.audio_streamer = audio_streamer
        self.ffmpeg_cmd = ffmpeg_cmd
        self.popen = popen
        self.process = None
        self.running = False

        self._stopped = False
        self._lock = threading.Lock()
        self._subscribers = []
        self._source_queue = queue.Queue(maxsize=CLIENT_QUEUE_SIZE)
        self._threads = []

    def start(self):
        """Start the ffmpeg process and its worker threads.

        Raises:
            RuntimeError: If ffmpeg is not installed
        """
        self.process = self._start_process()
        self.running = True
        self._stopped = False
        self.audio_streamer.addClient(self._source_queue)

        self._threads = [
            threading.Thread(target=self._pump_source, name=f'encoder-{self.bitrate}-source', daemon=True),
            threading.Thread(target=self._pump_output, name=f'encoder-{self.bitrate}-output', daemon=True),
            threading.Thread(target=self._monitor_errors, name=f'encoder-{self.bitrate}-stderr', daemon=True),
        ]
        for thread in self._threads:
            thread.start()

        Logger.info(f"Started shared encoder for {self.bitrate}kbps")

    def stop(self):
        """Stop the encoder, release the source client and close out all subscribers.

        Safe to call more than once, and callable after the encoder has already
        wound itself down - the worker threads clear `running` on their own, but
        only this method releases the source client queue.
        """
        with self._lock:
            if self._stopped:
                return
            self._stopped = True

        self.running = False

        try:
            self.audio_streamer.removeClient(self._source_queue)
        except Exception as e:
            Logger.error(f"Error removing encoder source client: {e}")

        # Unblock the source thread if it is waiting on an empty queue
        try:
            self._source_queue.put_nowait(None)
        except queue.Full:
            pass

        for thread in self._threads:
            if thread.is_alive():
                thread.join(timeout=1.0)
        self._threads = []

        if self.process:
            self._cleanup_process(self.process)
            self.process = None

        self._close_subscribers()
        Logger.info(f"Stopped shared encoder for {self.bitrate}kbps")

    def subscribe(self) -> Subscription:
        """Attach a new listener to this encoder.

        Returns:
            Subscription: The listener's subscription handle
        """
        subscription = Subscription(self.bitrate, self, queue.Queue(maxsize=FFMPEG_OUTPUT_QUEUE_SIZE))
        with self._lock:
            self._subscribers.append(subscription)
            count = len(self._subscribers)
        Logger.info(f"Listener subscribed to {self.bitrate}kbps encoder ({count} total)")
        return subscription

    def unsubscribe(self, subscription: Subscription) -> int:
        """Detach a listener from this encoder.

        Args:
            subscription: The subscription to remove

        Returns:
            int: Number of listeners still subscribed
        """
        with self._lock:
            if subscription in self._subscribers:
                self._subscribers.remove(subscription)
            count = len(self._subscribers)
        Logger.info(f"Listener unsubscribed from {self.bitrate}kbps encoder ({count} remaining)")
        return count

    @property
    def subscriber_count(self) -> int:
        """Number of listeners currently subscribed."""
        with self._lock:
            return len(self._subscribers)

    # -- PRIVATES --

    def _start_process(self):
        """Start the ffmpeg process for this encoder.

        Returns:
            The ffmpeg process

        Raises:
            RuntimeError: If ffmpeg is not found
        """
        try:
            return self.popen(
                self.ffmpeg_cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
        except FileNotFoundError:
            Logger.error("ffmpeg not found. Please install ffmpeg to use bitrate-based streaming.")
            raise RuntimeError("ffmpeg is required for bitrate-based streaming")

    def _pump_source(self):
        """Feed source audio into ffmpeg's stdin until the stream ends."""
        try:
            self.process.stdin.write(build_wav_header(RATE, CHANNELS))
            self.process.stdin.flush()

            while self.running:
                try:
                    chunk = self._source_queue.get(timeout=FFMPEG_QUEUE_TIMEOUT)
                except queue.Empty:
                    if not self.audio_streamer.onAir:
                        Logger.info(f"Audio streaming stopped, closing {self.bitrate}kbps encoder")
                        break
                    continue

                if chunk is None:
                    break

                self.process.stdin.write(chunk)
                self.process.stdin.flush()
        except BrokenPipeError:
            Logger.error(f"ffmpeg broken pipe on {self.bitrate}kbps encoder")
        except (IOError, ValueError) as e:
            Logger.error(f"Error writing to ffmpeg ({self.bitrate}kbps): {e}")
        except Exception as e:
            Logger.error(f"Unexpected error in encoder source thread: {type(e).__name__}: {str(e)}")
        finally:
            self.running = False
            self._close_stdin()
            self._close_subscribers()

    def _pump_output(self):
        """Read encoded output from ffmpeg and fan it out to every subscriber."""
        try:
            while True:
                chunk = self.process.stdout.read(8192)
                if not chunk:
                    break
                self._broadcast(chunk)
        except Exception as e:
            Logger.error(f"Error reading from ffmpeg ({self.bitrate}kbps): {e}")
        finally:
            self.running = False
            self._close_subscribers()

    def _broadcast(self, chunk: bytes):
        """Deliver an encoded chunk to every subscriber.

        A listener too slow to keep up loses its own chunks rather than blocking
        the encoder or the other listeners.

        Args:
            chunk: Encoded MP3 chunk
        """
        with self._lock:
            subscribers = list(self._subscribers)

        for subscription in subscribers:
            try:
                subscription.queue.put_nowait(chunk)
            except queue.Full:
                Logger.warning(f"Output queue full for a {self.bitrate}kbps listener, dropping encoded chunk")

    def _close_subscribers(self):
        """Send the stop sentinel to every subscriber so their responses end."""
        with self._lock:
            subscribers = list(self._subscribers)

        for subscription in subscribers:
            try:
                subscription.queue.put_nowait(None)
            except queue.Full:
                pass

    def _close_stdin(self):
        """Close ffmpeg's stdin to signal end of input."""
        try:
            if self.process and self.process.stdin and not self.process.stdin.closed:
                self.process.stdin.close()
        except Exception as e:
            Logger.error(f"Error closing ffmpeg stdin: {e}")

    def _monitor_errors(self):
        """Monitor ffmpeg stderr and log anything it reports."""
        try:
            while True:
                error_line = self.process.stderr.readline()
                if not error_line:
                    break
                error_line = error_line.decode('utf-8', errors='ignore').strip()
                if not error_line:
                    continue
                if 'error' in error_line.lower() or 'fatal' in error_line.lower():
                    Logger.error(f"FFmpeg error ({self.bitrate}kbps): {error_line}")
                elif 'warning' in error_line.lower():
                    Logger.warning(f"FFmpeg warning ({self.bitrate}kbps): {error_line}")
        except Exception as e:
            Logger.error(f"Error in ffmpeg error monitor thread: {e}")

    def _cleanup_process(self, process):
        """Clean up ffmpeg process resources.

        Args:
            process: The ffmpeg subprocess to cleanup
        """
        try:
            self._close_stdin()
            if process.stdout and not process.stdout.closed:
                process.stdout.close()
            if process.stderr and not process.stderr.closed:
                process.stderr.close()
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    Logger.warning("ffmpeg process did not terminate, killing it")
                    process.kill()
                    process.wait()
        except Exception as e:
            Logger.error(f"Error cleaning up ffmpeg process: {e}")


class BitrateEncoderPool:
    """Owns one shared encoder per active bitrate, reference counted by listener.

    An encoder is started when its first listener arrives and stopped when its
    last listener leaves, so CPU cost scales with the number of *bitrates in use*
    rather than with the number of listeners.
    """

    def __init__(self, audio_streamer, command_builder, encoder_factory=BitrateEncoder):
        """Initialize the pool.

        Args:
            audio_streamer: Instance of the audio streamer to read source audio from
            command_builder: Callable taking a bitrate and returning an ffmpeg command
            encoder_factory: Factory for encoder instances, injectable for testing
        """
        self.audio_streamer = audio_streamer
        self.command_builder = command_builder
        self.encoder_factory = encoder_factory
        self._encoders = {}
        self._lock = threading.Lock()

    def subscribe(self, bitrate: int) -> Subscription:
        """Attach a listener to the encoder for a bitrate, starting it if needed.

        Args:
            bitrate: Bitrate in kbps

        Returns:
            Subscription: The listener's subscription handle

        Raises:
            RuntimeError: If ffmpeg is not installed
        """
        stale = None
        with self._lock:
            encoder = self._encoders.get(bitrate)
            if encoder is None or not encoder.running:
                # A previous encoder may have wound itself down (source went off
                # air); release its resources before replacing it.
                stale = encoder
                encoder = self.encoder_factory(bitrate, self.audio_streamer, self.command_builder(bitrate))
                encoder.start()
                self._encoders[bitrate] = encoder
            subscription = encoder.subscribe()

        if stale is not None:
            stale.stop()

        return subscription

    def unsubscribe(self, subscription: Subscription):
        """Detach a listener, stopping its encoder once no listeners remain.

        Args:
            subscription: The subscription to remove
        """
        if subscription is None:
            return

        encoder = subscription.encoder
        with self._lock:
            remaining = encoder.unsubscribe(subscription)
            if remaining > 0:
                return
            # Only drop the encoder if it is still the one registered for this
            # bitrate; a replacement may already have been started.
            if self._encoders.get(subscription.bitrate) is encoder:
                del self._encoders[subscription.bitrate]

        encoder.stop()

    def shutdown(self):
        """Stop every active encoder."""
        with self._lock:
            encoders = list(self._encoders.values())
            self._encoders.clear()

        for encoder in encoders:
            encoder.stop()

    @property
    def active_encoders(self) -> int:
        """Number of encoders currently running."""
        with self._lock:
            return len(self._encoders)
