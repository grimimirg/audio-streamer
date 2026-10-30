from utilities.Constants import CHANNELS, FFMPEG_THREADS, RATE


def build_mp3_command(bitrate: int) -> list:
    """Build the ffmpeg command that encodes the source PCM to MP3.

    Resampling and channel-mixing flags are only emitted when the output format
    actually differs from the source, since forcing them makes ffmpeg resample
    every chunk for no gain.

    Args:
        bitrate: Bitrate in kbps for re-encoding

    Returns:
        list: FFmpeg command as list of arguments
    """
    command = [
        'ffmpeg',
        '-nostdin',
        '-loglevel', 'error',
        '-i', 'pipe:0',
        '-vn',
        '-f', 'mp3',
        '-codec:a', 'libmp3lame',
        '-b:a', f'{bitrate}k',
    ]

    if RATE != 44100:
        command += ['-ar', '44100']
    if CHANNELS != 2:
        command += ['-ac', '2']
    if FFMPEG_THREADS > 0:
        command += ['-threads', str(FFMPEG_THREADS)]

    command += ['-bufsize', '64k', '-']
    return command
