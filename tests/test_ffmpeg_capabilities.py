import subprocess

from utilities.FfmpegCapabilities import log_encoding_capabilities, probe_hwaccels


class FakeResult:
    """Stand-in for a completed subprocess."""

    def __init__(self, stdout='', returncode=0):
        self.stdout = stdout
        self.returncode = returncode


def runner_returning(result):
    """Build a subprocess runner returning a fixed result."""
    def runner(_cmd, **_kwargs):
        return result
    return runner


def test_probe_lists_the_reported_methods():
    runner = runner_returning(FakeResult('Hardware acceleration methods:\nvaapi\nvulkan\n'))

    assert probe_hwaccels(runner) == ['vaapi', 'vulkan']


def test_probe_returns_empty_when_none_are_available():
    runner = runner_returning(FakeResult('Hardware acceleration methods:\n'))

    assert probe_hwaccels(runner) == []


def test_probe_returns_empty_when_ffmpeg_is_missing(mocker):
    warning = mocker.patch('utilities.FfmpegCapabilities.Logger.warning')

    def runner(_cmd, **_kwargs):
        raise FileNotFoundError('ffmpeg')

    assert probe_hwaccels(runner) == []
    warning.assert_called_once()


def test_probe_returns_empty_on_timeout(mocker):
    warning = mocker.patch('utilities.FfmpegCapabilities.Logger.warning')

    def runner(_cmd, **_kwargs):
        raise subprocess.TimeoutExpired(cmd='ffmpeg', timeout=5)

    assert probe_hwaccels(runner) == []
    warning.assert_called_once()


def test_probe_returns_empty_on_non_zero_exit():
    runner = runner_returning(FakeResult('', returncode=1))

    assert probe_hwaccels(runner) == []


def test_probe_tolerates_no_stdout():
    runner = runner_returning(FakeResult(None))

    assert probe_hwaccels(runner) == []


def test_logging_reports_cpu_encoding_either_way(mocker):
    info = mocker.patch('utilities.FfmpegCapabilities.Logger.info')

    assert log_encoding_capabilities(
        runner_returning(FakeResult('Hardware acceleration methods:\nvaapi\n'))
    ) == ['vaapi']
    assert 'CPU' in info.call_args[0][0]

    log_encoding_capabilities(runner_returning(FakeResult('Hardware acceleration methods:\n')))
    assert 'CPU' in info.call_args[0][0]
