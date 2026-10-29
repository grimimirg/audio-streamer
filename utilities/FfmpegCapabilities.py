import subprocess

from utilities.Logger import Logger


def probe_hwaccels(runner=subprocess.run) -> list:
    """List the hardware acceleration methods the local ffmpeg build offers.

    Note that MP3 encoding is always done on the CPU: ffmpeg's hardware
    acceleration covers video codecs, and no mainstream GPU or ASIC exposes an
    MP3 encoder. This probe is therefore informational - it records what the host
    can do so the log explains why encoding stays on the CPU.

    Args:
        runner: Subprocess runner, injectable for testing

    Returns:
        list: Available hwaccel names, empty if none or if ffmpeg is unavailable
    """
    try:
        result = runner(
            ['ffmpeg', '-hide_banner', '-hwaccels'],
            capture_output=True,
            text=True,
            timeout=5
        )
    except FileNotFoundError:
        Logger.warning("ffmpeg not found, bitrate-based streaming will be unavailable")
        return []
    except subprocess.TimeoutExpired:
        Logger.warning("ffmpeg hwaccel probe timed out")
        return []
    except Exception as e:
        Logger.error(f"Error probing ffmpeg hardware acceleration: {e}")
        return []

    if result.returncode != 0:
        Logger.warning(f"ffmpeg hwaccel probe failed with code {result.returncode}")
        return []

    lines = (result.stdout or '').splitlines()
    # Output is a header line ("Hardware acceleration methods:") then one name per line
    return [line.strip() for line in lines[1:] if line.strip()]


def log_encoding_capabilities(runner=subprocess.run):
    """Log the host's ffmpeg hardware acceleration support at startup.

    Args:
        runner: Subprocess runner, injectable for testing
    """
    hwaccels = probe_hwaccels(runner)
    if hwaccels:
        Logger.info(
            f"ffmpeg hardware acceleration available: {', '.join(hwaccels)} "
            "(video only - MP3 encoding runs on the CPU)"
        )
    else:
        Logger.info("No ffmpeg hardware acceleration available, MP3 encoding runs on the CPU")
    return hwaccels
