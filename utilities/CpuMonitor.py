import threading
import time

from utilities.Logger import Logger

try:
    import psutil
except ImportError:  # pragma: no cover - exercised via the injected sampler
    psutil = None

# How long to stay quiet after logging a CPU warning, as a multiple of the
# sampling interval, so a sustained overload does not flood the log
WARNING_BACKOFF_FACTOR = 6


def build_process_tree_sampler():
    """Build a sampler reporting CPU usage of this process and its children.

    The ffmpeg encoders run as child processes, so their cost only shows up when
    the whole tree is measured. System-wide load average would also include
    unrelated processes, which is why it is not used here.

    Returns:
        callable: Returns total CPU percent across the process tree,
                  or None if psutil is unavailable
    """
    if psutil is None:
        return None

    process = psutil.Process()
    # Prime the counters; the first psutil call always reports 0.0
    process.cpu_percent(None)

    def sample():
        total = process.cpu_percent(None)
        for child in process.children(recursive=True):
            try:
                total += child.cpu_percent(None)
            except psutil.Error:
                continue  # Child exited between listing and sampling
        return total

    return sample


class CpuMonitor:
    """Samples CPU usage of the streamer and its encoders, and warns when it is high."""

    def __init__(self, threshold: float, interval: float, encoder_counter=None,
                 sampler=None, clock=time.monotonic):
        """Initialize the monitor.

        Args:
            threshold: CPU percent above which a warning is logged
            interval: Seconds between samples
            encoder_counter: Callable returning the number of active encoders
            sampler: Callable returning current CPU percent, injectable for testing
            clock: Monotonic clock, injectable for testing
        """
        self.threshold = threshold
        self.interval = interval
        self.encoder_counter = encoder_counter or (lambda: 0)
        self.sampler = sampler if sampler is not None else build_process_tree_sampler()
        self.clock = clock

        self.cpu_percent = None
        self.cpu_warning = False
        self._last_warning_at = None
        self._stop_event = threading.Event()
        self._thread = None

    @property
    def enabled(self) -> bool:
        """Whether CPU usage can actually be measured."""
        return self.sampler is not None

    def start(self):
        """Start sampling in a background thread."""
        if not self.enabled:
            Logger.warning("psutil not installed, CPU monitoring disabled")
            return
        if self._thread is not None:
            return

        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, name='cpu-monitor', daemon=True)
        self._thread.start()
        Logger.info(f"CPU monitoring started (threshold {self.threshold}%, every {self.interval}s)")

    def stop(self):
        """Stop sampling."""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=self.interval + 1.0)
            self._thread = None

    def sample(self):
        """Take a single CPU sample and warn if it exceeds the threshold.

        Returns:
            float or None: The sampled CPU percent, or None if disabled
        """
        if not self.enabled:
            return None

        try:
            self.cpu_percent = self.sampler()
        except Exception as e:
            Logger.error(f"Error sampling CPU usage: {e}")
            return self.cpu_percent

        self.cpu_warning = self.cpu_percent > self.threshold
        if self.cpu_warning and self._should_log_warning():
            Logger.warning(
                f"High CPU usage: {self.cpu_percent:.1f}% "
                f"(threshold {self.threshold}%, {self.encoder_counter()} active encoders)"
            )
            self._last_warning_at = self.clock()

        return self.cpu_percent

    def get_stats(self) -> dict:
        """Get the current CPU statistics.

        Returns:
            dict: CPU usage, active encoder count and warning flag
        """
        return {
            'cpu_percent': round(self.cpu_percent, 1) if self.cpu_percent is not None else None,
            'cpu_warning': self.cpu_warning,
            'active_encoders': self.encoder_counter()
        }

    # -- PRIVATES --

    def _should_log_warning(self) -> bool:
        """Whether enough time has passed since the last warning was logged."""
        if self._last_warning_at is None:
            return True
        return self.clock() - self._last_warning_at >= self.interval * WARNING_BACKOFF_FACTOR

    def _run(self):
        """Sample on the configured interval until stopped."""
        while not self._stop_event.wait(self.interval):
            self.sample()
