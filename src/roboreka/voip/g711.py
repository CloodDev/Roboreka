"""Pure-Python ITU-T G.711 mu-law (PCMU) codec (no audioop dependency)."""

from __future__ import annotations

from typing import Sequence

SAMPLE_RATE = 8000
FRAME_DURATION_MS = 20
FRAME_SAMPLES = 160
ULAW_SILENCE = 0xFF

_BIAS = 0x84
_CLIP = 32635


def linear_to_ulaw(sample: int) -> int:
    """Encode a signed 16-bit linear PCM sample (-32768..32767) into an 8-bit mu-law byte."""
    if sample < 0:
        sign = 0x80
        sample = -sample
    else:
        sign = 0x00

    if sample > _CLIP:
        sample = _CLIP

    sample += _BIAS
    exponent = 7
    mask = 0x4000
    while exponent > 0 and (sample & mask) == 0:
        exponent -= 1
        mask >>= 1

    mantissa = (sample >> (exponent + 3)) & 0x0F
    return (~(sign | (exponent << 4) | mantissa)) & 0xFF


def _decode_ulaw_byte(u_val: int) -> int:
    u_val = (~u_val) & 0xFF
    sign = u_val & 0x80
    exponent = (u_val >> 4) & 0x07
    mantissa = u_val & 0x0F
    sample = ((mantissa << 3) + _BIAS) << exponent
    sample -= _BIAS
    return -sample if sign else sample


ULAW_TO_LINEAR: tuple[int, ...] = tuple(_decode_ulaw_byte(i) for i in range(256))


def ulaw_to_linear(byte: int) -> int:
    """Decode a single 8-bit mu-law byte to signed 16-bit PCM."""
    return ULAW_TO_LINEAR[byte & 0xFF]


def pcm16_to_ulaw(samples: Sequence[int]) -> bytes:
    """Encode a sequence of signed 16-bit PCM samples into G.711 mu-law bytes."""
    encode = linear_to_ulaw
    return bytes(encode(s) for s in samples)


def ulaw_to_pcm16(data: bytes) -> list[int]:
    """Decode G.711 mu-law bytes into a list of signed 16-bit PCM samples."""
    lut = ULAW_TO_LINEAR
    return [lut[b] for b in data]
