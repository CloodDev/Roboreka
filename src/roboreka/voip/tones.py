"""Audio tone feedback and DTMF waveform synthesis encoded as G.711 PCMU frames."""

from __future__ import annotations

import math
from typing import Sequence

from roboreka.voip.g711 import FRAME_SAMPLES, SAMPLE_RATE, ULAW_SILENCE, pcm16_to_ulaw

DTMF_FREQS: dict[str, tuple[int, int]] = {
    "1": (697, 1209),
    "2": (697, 1336),
    "3": (697, 1477),
    "A": (697, 1633),
    "4": (770, 1209),
    "5": (770, 1336),
    "6": (770, 1477),
    "B": (770, 1633),
    "7": (852, 1209),
    "8": (852, 1336),
    "9": (852, 1477),
    "C": (852, 1633),
    "*": (941, 1209),
    "0": (941, 1336),
    "#": (941, 1477),
    "D": (941, 1633),
}


def generate_tone_pcm(
    freqs: Sequence[float],
    duration_ms: int,
    amplitude: float = 0.35,
    sample_rate: int = SAMPLE_RATE,
    fade_ms: int = 5,
) -> list[int]:
    """Synthesize a multi-frequency sine tone as 16-bit linear PCM samples."""
    n_samples = max(0, int(round(sample_rate * duration_ms / 1000.0)))
    if n_samples == 0 or not freqs:
        return [0] * n_samples

    fade_samples = min(n_samples // 2, int(round(sample_rate * fade_ms / 1000.0)))
    per_tone_scale = (32767.0 * amplitude) / len(freqs)
    two_pi_over_fs = 2.0 * math.pi / sample_rate
    omegas = [two_pi_over_fs * f for f in freqs]

    out: list[int] = []
    for i in range(n_samples):
        val = sum(math.sin(w * i) for w in omegas) * per_tone_scale
        if fade_samples > 0:
            if i < fade_samples:
                val *= 0.5 * (1.0 - math.cos(math.pi * i / fade_samples))
            elif i >= n_samples - fade_samples:
                rem = n_samples - 1 - i
                val *= 0.5 * (1.0 - math.cos(math.pi * rem / fade_samples))
        out.append(max(-32768, min(32767, int(round(val)))))
    return out


def pcm_to_rtp_frames(samples: Sequence[int]) -> list[bytes]:
    """Encode PCM16 samples into 20 ms (160-byte) G.711 PCMU RTP payloads."""
    if not samples:
        return []
    encoded = pcm16_to_ulaw(samples)
    frames: list[bytes] = []
    for offset in range(0, len(encoded), FRAME_SAMPLES):
        chunk = encoded[offset : offset + FRAME_SAMPLES]
        if len(chunk) < FRAME_SAMPLES:
            chunk = chunk + bytes([ULAW_SILENCE]) * (FRAME_SAMPLES - len(chunk))
        frames.append(chunk)
    return frames


def welcome_chime() -> list[bytes]:
    """Two-note rising chime played when a VoIP call starts."""
    pcm = (
        generate_tone_pcm([523.25], 80, amplitude=0.30)
        + [0] * 160
        + generate_tone_pcm([659.25], 100, amplitude=0.32)
        + [0] * 160
        + generate_tone_pcm([783.99], 140, amplitude=0.35)
    )
    return pcm_to_rtp_frames(pcm)


def ack_beep(angle_ratio: float = 0.5) -> list[bytes]:
    """Short pitch-mapped acknowledgment beep (440-880 Hz based on joint position)."""
    clamped = max(0.0, min(1.0, float(angle_ratio)))
    freq = 440.0 + clamped * 440.0
    return pcm_to_rtp_frames(generate_tone_pcm([freq], 80, amplitude=0.30))


def limit_buzz() -> list[bytes]:
    """Low harsh double-tone buzz indicating a joint hit its mechanical angle limit."""
    pcm = (
        generate_tone_pcm([220.0, 233.0], 140, amplitude=0.38)
        + [0] * 240
        + generate_tone_pcm([220.0, 233.0], 140, amplitude=0.38)
    )
    return pcm_to_rtp_frames(pcm)


def home_chime() -> list[bytes]:
    """Three-note chime played when returning all joints to home position."""
    pcm = (
        generate_tone_pcm([587.33], 70, amplitude=0.30)
        + generate_tone_pcm([783.99], 70, amplitude=0.30)
        + generate_tone_pcm([1046.50], 120, amplitude=0.32)
    )
    return pcm_to_rtp_frames(pcm)


def stop_chime() -> list[bytes]:
    """Descending alert tone played on emergency stop / servo release."""
    pcm = (
        generate_tone_pcm([660.0], 90, amplitude=0.35)
        + generate_tone_pcm([440.0], 140, amplitude=0.35)
    )
    return pcm_to_rtp_frames(pcm)


def error_beep() -> list[bytes]:
    """Short low tone indicating an unassigned or unrecognized DTMF command."""
    return pcm_to_rtp_frames(generate_tone_pcm([300.0], 120, amplitude=0.28))


def dtmf_tone_frames(
    digit: str,
    duration_ms: int = 100,
    silence_ms: int = 60,
    amplitude: float = 0.45,
) -> list[bytes]:
    """Synthesize an in-band DTMF digit tone followed by trailing silence as PCMU frames."""
    key = digit.upper()
    if key not in DTMF_FREQS:
        raise ValueError(f"Invalid DTMF digit: {digit!r}")
    f_low, f_high = DTMF_FREQS[key]
    tone = generate_tone_pcm([f_low, f_high], duration_ms, amplitude=amplitude)
    silence = [0] * int(round(SAMPLE_RATE * silence_ms / 1000.0))
    return pcm_to_rtp_frames(tone + silence)
