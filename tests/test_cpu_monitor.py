import pytest

from utilities.CpuMonitor import WARNING_BACKOFF_FACTOR, CpuMonitor


class FakeClock:
    """Monotonic clock advanced explicitly by the test."""

    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


def build_monitor(samples, threshold=80.0, interval=5.0, encoders=0):
    """Build a monitor that replays a fixed list of CPU samples.

    Args:
        samples: CPU percentages to return, one per sample() call
        threshold: Warning threshold
        interval: Sampling interval
        encoders: Active encoder count to report

    Returns:
        tuple: (monitor, clock)
    """
    remaining = list(samples)
    clock = FakeClock()
    monitor = CpuMonitor(
        threshold=threshold,
        interval=interval,
        encoder_counter=lambda: encoders,
        sampler=lambda: remaining.pop(0),
        clock=clock
    )
    return monitor, clock


def test_sample_above_threshold_warns(mocker):
    warning = mocker.patch('utilities.CpuMonitor.Logger.warning')
    monitor, _ = build_monitor([95.0])

    monitor.sample()

    assert monitor.cpu_warning is True
    warning.assert_called_once()


def test_sample_below_threshold_stays_quiet(mocker):
    warning = mocker.patch('utilities.CpuMonitor.Logger.warning')
    monitor, _ = build_monitor([12.5])

    monitor.sample()

    assert monitor.cpu_warning is False
    warning.assert_not_called()


def test_sample_exactly_at_threshold_is_not_a_warning(mocker):
    warning = mocker.patch('utilities.CpuMonitor.Logger.warning')
    monitor, _ = build_monitor([80.0], threshold=80.0)

    monitor.sample()

    assert monitor.cpu_warning is False
    warning.assert_not_called()


def test_sustained_overload_warns_only_once_per_backoff(mocker):
    warning = mocker.patch('utilities.CpuMonitor.Logger.warning')
    monitor, clock = build_monitor([95.0, 96.0, 97.0], interval=5.0)

    monitor.sample()
    clock.advance(5.0)
    monitor.sample()

    assert warning.call_count == 1

    clock.advance(5.0 * WARNING_BACKOFF_FACTOR)
    monitor.sample()

    assert warning.call_count == 2


def test_recovery_clears_the_warning_flag():
    monitor, _ = build_monitor([95.0, 10.0])

    monitor.sample()
    monitor.sample()

    assert monitor.cpu_warning is False


def test_sampler_failure_keeps_the_last_reading(mocker):
    error = mocker.patch('utilities.CpuMonitor.Logger.error')

    def sampler():
        raise OSError('no such process')

    monitor = CpuMonitor(threshold=80.0, interval=5.0, sampler=sampler, clock=FakeClock())
    monitor.cpu_percent = 42.0

    assert monitor.sample() == 42.0
    error.assert_called_once()


def test_get_stats_reports_usage_encoders_and_warning():
    monitor, _ = build_monitor([51.26], encoders=3)
    monitor.sample()

    assert monitor.get_stats() == {
        'cpu_percent': 51.3,
        'cpu_warning': False,
        'active_encoders': 3
    }


def test_get_stats_before_the_first_sample_reports_no_usage():
    monitor, _ = build_monitor([])

    assert monitor.get_stats()['cpu_percent'] is None


def test_monitor_without_psutil_is_disabled(mocker):
    warning = mocker.patch('utilities.CpuMonitor.Logger.warning')
    mocker.patch('utilities.CpuMonitor.build_process_tree_sampler', return_value=None)
    monitor = CpuMonitor(threshold=80.0, interval=5.0)

    monitor.start()

    assert monitor.enabled is False
    assert monitor.sample() is None
    assert monitor.get_stats()['cpu_percent'] is None
    warning.assert_called_once()


def test_stop_without_start_is_safe():
    monitor, _ = build_monitor([])

    monitor.stop()  # Must not raise


@pytest.mark.parametrize('threshold,sample,expected', [
    (50.0, 49.9, False),
    (50.0, 50.1, True),
    (100.0, 150.0, True),  # Multi-core totals can exceed 100%
])
def test_threshold_boundaries(threshold, sample, expected):
    monitor, _ = build_monitor([sample], threshold=threshold)
    monitor.sample()

    assert monitor.cpu_warning is expected
