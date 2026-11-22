"""RFC 4733 telephone-event & Goertzel in-band DTMF detectors."""

from __future__ import annotations

import math
import struct
import time
from dataclasses import dataclass
from typing import Callable

from roboreka.voip.g711 import SAMPLE_RATE, ulaw_to_pcm16

DTMF_DIGITS: dict[int, str] = {
    0: "0",
    1: "1",
    2: "2",
    3: "3",
    4: "4",
    5: "5",
    6: "6",
    7: "7",
    8: "8",
    9: "9",
    10: "*",
    11: "#",
    12: "A",
    13: "B",
    14: "C",
    15: "D",
}

DIGIT_TO_EVENT: dict[str, int] = {v: k for k, v in DTMF_DIGITS.items()}

LOW_FREQS = (697, 770, 852, 941)
HIGH_FREQS = (1209, 1336, 1477, 1633)

DTMF_MATRIX: dict[tuple[int, int], str] = {
    (697, 1209): "1",
    (697, 1336): "2",
    (697, 1477): "3",
    (697, 1633): "A",
    (770, 1209): "4",
    (770, 1336): "5",
    (770, 1477): "6",
    (770, 1633): "B",
    (852, 1209): "7",
    (852, 1336): "8",
    (852, 1477): "9",
    (852, 1633): "C",
    (941, 1209): "*",
    (941, 1336): "0",
    (941, 1477): "#",
    (941, 1633): "D",
}


@dataclass(frozen=True)
class RFC4733Event:
    """Decoded RFC 4733 telephone-event payload."""

    event: int
    digit: str
    end: bool
    volume: int
    duration: int


def parse_rfc4733(payload: bytes) -> RFC4733Event | None:
    """Parse a 4-byte RFC 4733 telephone-event payload, returning None if invalid."""
    if len(payload) < 4:
        return None
    event, flags, duration = struct.unpack("!BBH", payload[:4])
    digit = DTMF_DIGITS.get(event)
    if digit is None:
        return None
    end = bool(flags & 0x80)
    volume = flags & 0x3F
    return RFC4733Event(
        event=event,
        digit=digit,
        end=end,
        volume=volume,
        duration=duration,
    )


def encode_rfc4733(digit: str, end: bool, duration: int, volume: int = 10) -> bytes:
    """Encode a DTMF digit as a 4-byte RFC 4733 telephone-event payload."""
    event = DIGIT_TO_EVENT.get(digit.upper())
    if event is None:
        raise ValueError(f"Unsupported RFC 4733 digit: {digit!r}")
    flags = (0x80 if end else 0x00) | (volume & 0x3F)
    return struct.pack("!BBH", event, flags, duration & 0xFFFF)


class RFC4733Tracker:
    """Deduplicate RFC 4733 RTP event streams across interim and retransmitted end packets."""

    def __init__(self) -> None:
        self._seen_events: set[tuple[int, int]] = set()
        self._recent_order: list[tuple[int, int]] = []

    def feed(self, rtp_timestamp: int, payload: bytes) -> str | None:
        """Process one RFC 4733 packet and return the digit once when first observed."""
        parsed = parse_rfc4733(payload)
        if parsed is None:
            return None

        key = (rtp_timestamp, parsed.event)
        if key in self._seen_events:
            return None

        self._seen_events.add(key)
        self._recent_order.append(key)
        if len(self._recent_order) > 64:
            oldest = self._recent_order.pop(0)
            self._seen_events.discard(oldest)
        return parsed.digit


class GoertzelDTMFDetector:
    """In-band DTMF detector using the Goertzel algorithm over 8 kHz PCM16 audio."""

    def __init__(
        self,
        sample_rate: int = SAMPLE_RATE,
        block_size: int = 205,
        min_consecutive: int = 2,
        min_rms: float = 0.012,
        dominance_ratio: float = 4.0,
        energy_ratio_min: float = 0.45,
        twist_min: float = 0.12,
        twist_max: float = 8.0,
    ) -> None:
        self.sample_rate = sample_rate
        self.block_size = block_size
        self.min_consecutive = min_consecutive
        self.min_rms = min_rms
        self.dominance_ratio = dominance_ratio
        self.energy_ratio_min = energy_ratio_min
        self.twist_min = twist_min
        self.twist_max = twist_max

        self._coeffs: dict[int, float] = {
            freq: 2.0 * math.cos(2.0 * math.pi * freq / sample_rate)
            for freq in (*LOW_FREQS, *HIGH_FREQS)
        }
        self._buffer: list[float] = []
        self._candidate: str | None = None
        self._streak = 0
        self._emitted_for_press = False

    def reset(self) -> None:
        """Clear buffered audio and debounce state."""
        self._buffer.clear()
        self._candidate = None
        self._streak = 0
        self._emitted_for_press = False

    def _goertzel_power(self, samples: list[float], freq: int) -> float:
        coeff = self._coeffs[freq]
        s1 = 0.0
        s2 = 0.0
        for x in samples:
            s0 = x + coeff * s1 - s2
            s2 = s1
            s1 = s0
        return s1 * s1 + s2 * s2 - coeff * s1 * s2

    def _classify_block(self, block: list[float]) -> str | None:
        n = len(block)
        sum_sq = sum(x * x for x in block)
        rms = math.sqrt(sum_sq / n)
        if rms < self.min_rms:
            return None

        row_powers = sorted(
            ((self._goertzel_power(block, f), f) for f in LOW_FREQS),
            reverse=True,
        )
        col_powers = sorted(
            ((self._goertzel_power(block, f), f) for f in HIGH_FREQS),
            reverse=True,
        )

        r1_pow, r1_freq = row_powers[0]
        r2_pow, _ = row_powers[1]
        c1_pow, c1_freq = col_powers[0]
        c2_pow, _ = col_powers[1]

        if r1_pow <= self.dominance_ratio * max(r2_pow, 1e-12):
            return None
        if c1_pow <= self.dominance_ratio * max(c2_pow, 1e-12):
            return None

        twist = c1_pow / max(r1_pow, 1e-12)
        if not (self.twist_min <= twist <= self.twist_max):
            return None

        expected_total = sum_sq * (n / 2.0)
        if expected_total <= 0.0 or ((r1_pow + c1_pow) / expected_total) < self.energy_ratio_min:
            return None

        return DTMF_MATRIX.get((r1_freq, c1_freq))

    def feed_pcm16(self, samples: list[int]) -> list[str]:
        """Feed linear PCM16 samples and return any newly detected DTMF digits."""
        scale = 1.0 / 32768.0
        self._buffer.extend(s * scale for s in samples)

        detected: list[str] = []
        while len(self._buffer) >= self.block_size:
            block = self._buffer[: self.block_size]
            del self._buffer[: self.block_size]

            digit = self._classify_block(block)
            if digit is None:
                self._candidate = None
                self._streak = 0
                self._emitted_for_press = False
                continue

            if digit == self._candidate:
                self._streak += 1
            else:
                self._candidate = digit
                self._streak = 1
                self._emitted_for_press = False

            if self._streak >= self.min_consecutive and not self._emitted_for_press:
                detected.append(digit)
                self._emitted_for_press = True

        return detected

    def feed_ulaw(self, payload: bytes) -> list[str]:
        """Feed G.711 mu-law payload bytes and return any newly detected DTMF digits."""
        return self.feed_pcm16(ulaw_to_pcm16(payload))


class HybridDTMFDetector:
    """Combines RFC 4733 out-of-band events and Goertzel in-band detection without double triggers."""

    def __init__(
        self,
        suppression_window_s: float = 0.30,
        clock_fn: Callable[[], float] = time.monotonic,
    ) -> None:
        self.rfc4733 = RFC4733Tracker()
        self.goertzel = GoertzelDTMFDetector()
        self.suppression_window_s = suppression_window_s
        self._clock = clock_fn
        self._last_rfc4733_at: float = -1e9

    def feed_rfc4733(self, rtp_timestamp: int, payload: bytes) -> str | None:
        """Process an RFC 4733 RTP packet; returns digit on first sighting."""
        digit = self.rfc4733.feed(rtp_timestamp, payload)
        if digit is not None:
            self._last_rfc4733_at = self._clock()
            self.goertzel.reset()
        return digit

    def feed_pcmu(self, payload: bytes) -> list[str]:
        """Process a PCMU RTP audio payload; suppressed shortly after RFC 4733 events."""
        if (self._clock() - self._last_rfc4733_at) < self.suppression_window_s:
            return []
        return self.goertzel.feed_ulaw(payload)
