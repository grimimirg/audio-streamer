from utilities import FfmpegCommand as ffmpeg_command_module
from utilities.FfmpegCommand import build_mp3_command


def test_command_carries_the_requested_bitrate():
    command = build_mp3_command(192)

    assert command[0] == 'ffmpeg'
    assert command[command.index('-b:a') + 1] == '192k'
    assert command[-1] == '-'


def test_command_omits_resampling_when_the_source_already_matches():
    command = build_mp3_command(128)

    assert '-ar' not in command
    assert '-ac' not in command


def test_command_resamples_when_the_source_differs(monkeypatch):
    monkeypatch.setattr(ffmpeg_command_module, 'RATE', 48000)
    monkeypatch.setattr(ffmpeg_command_module, 'CHANNELS', 1)

    command = build_mp3_command(128)

    assert command[command.index('-ar') + 1] == '44100'
    assert command[command.index('-ac') + 1] == '2'


def test_command_omits_thread_limit_when_unset():
    command = build_mp3_command(128)

    assert '-threads' not in command


def test_command_applies_the_configured_thread_limit(monkeypatch):
    monkeypatch.setattr(ffmpeg_command_module, 'FFMPEG_THREADS', 2)

    command = build_mp3_command(128)

    assert command[command.index('-threads') + 1] == '2'
