import struct


def build_wav_header(sample_rate: int = 44100, channels: int = 2, bits_per_sample: int = 16) -> bytes:
    """Build a WAV header for an endless (streamed) PCM payload.

    The RIFF and data chunk sizes are set to 0xFFFFFFFF because the total length
    of a live stream is unknown; players treat this as "stream until closed".

    Args:
        sample_rate: Sample rate in Hz
        channels: Number of audio channels
        bits_per_sample: Bit depth of each sample

    Returns:
        bytes: WAV header bytes
    """
    byte_rate = sample_rate * channels * bits_per_sample // 8
    block_align = channels * bits_per_sample // 8
    dummy_size = 0xFFFFFFFF

    header = struct.pack('<4sL4s', b'RIFF', dummy_size, b'WAVE')
    header += struct.pack('<4sLHHLLHH4sL',
                          b'fmt ', 16, 1, channels, sample_rate,
                          byte_rate, block_align, bits_per_sample, b'data', dummy_size)
    return header
