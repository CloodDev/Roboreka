"""Tests for G.711 mu-law codec, Goertzel in-band DTMF, RFC 4733, and hybrid detector."""

from __future__ import annotations

from roboreka.voip.dtmf import (
    DTMF_DIGITS,
    GoertzelDTMFDetector,
    HybridDTMFDetector,
    RFC4733Tracker,
    encode_rfc4733,
    parse_rfc4733,
)
from roboreka.voip.g711 import ULAW_SILENCE, linear_to_ulaw, ulaw_to_linear
from roboreka.voip.tones import dtmf_tone_frames, generate_tone_pcm, pcm_to_rtp_frames


def test_ulaw_roundtrip_accuracy() -> None:
    assert linear_to_ulaw(0) == ULAW_SILENCE
    assert ulaw_to_linear(ULAW_SILENCE) == 0

    for sample in (-30000, -10000, -1000, 1000, 10000, 30000):
        decoded = ulaw_to_linear(linear_to_ulaw(sample))
        assert (decoded > 0) == (sample > 0)
        assert abs(decoded - sample) < max(60, abs(sample) * 0.04)


def test_goertzel_detects_all_16_dtmf_digits() -> None:
    detector = GoertzelDTMFDetector()
    for digit in DTMF_DIGITS.values():
        detector.reset()
        detected: list[str] = []
        for frame in dtmf_tone_frames(digit, duration_ms=100, silence_ms=60):
            detected.extend(detector.feed_ulaw(frame))
        assert detected == [digit], f"Failed detecting digit {digit!r}: got {detected}"


def test_goertzel_rejects_silence_and_single_or_non_dtmf_tones() -> None:
    detector = GoertzelDTMFDetector()
    silence_frame = bytes([ULAW_SILENCE]) * 160
    assert detector.feed_ulaw(silence_frame * 20) == []

    # Pure 440 Hz (dial/ring tone) must not trigger DTMF
    for frame in pcm_to_rtp_frames(generate_tone_pcm([440.0], 400, amplitude=0.45)):
        assert detector.feed_ulaw(frame) == []

    # Single DTMF row frequency without a column frequency must fail twist check
    detector.reset()
    for frame in pcm_to_rtp_frames(generate_tone_pcm([697.0], 400, amplitude=0.45)):
        assert detector.feed_ulaw(frame) == []


def test_goertzel_debounces_repeated_and_sustained_presses() -> None:
    detector = GoertzelDTMFDetector()
    # Continuous 300 ms tone emits once
    detected_long: list[str] = []
    for frame in dtmf_tone_frames("6", duration_ms=300, silence_ms=60):
        detected_long.extend(detector.feed_ulaw(frame))
    assert detected_long == ["6"]

    # Two presses separated by silence emit twice
    frames = dtmf_tone_frames("6", duration_ms=100, silence_ms=80) + dtmf_tone_frames(
        "6", duration_ms=100, silence_ms=80
    )
    detected_double: list[str] = []
    for frame in frames:
        detected_double.extend(detector.feed_ulaw(frame))
    assert detected_double == ["6", "6"]


def test_rfc4733_roundtrip_and_deduplication() -> None:
    tracker = RFC4733Tracker()
    p_start = encode_rfc4733("6", end=False, duration=160)
    p_mid = encode_rfc4733("6", end=False, duration=320)
    p_end = encode_rfc4733("6", end=True, duration=480)

    parsed = parse_rfc4733(p_end)
    assert parsed is not None
    assert parsed.digit == "6"
    assert parsed.end is True
    assert parsed.duration == 480

    # Same timestamp across interim + 3x end packets -> emit exactly once
    assert tracker.feed(1600, p_start) == "6"
    assert tracker.feed(1600, p_mid) is None
    assert tracker.feed(1600, p_end) is None
    assert tracker.feed(1600, p_end) is None
    assert tracker.feed(1600, p_end) is None

    # New timestamp emits again
    assert tracker.feed(3200, p_start) == "6"


def test_hybrid_detector_suppresses_inband_after_rfc4733() -> None:
    now = [100.0]
    hybrid = HybridDTMFDetector(suppression_window_s=0.30, clock_fn=lambda: now[0])

    assert hybrid.feed_rfc4733(1000, encode_rfc4733("6", False, 160)) == "6"

    # Within 300 ms suppression window, in-band frames are ignored
    now[0] = 100.10
    inband_hits: list[str] = []
    for frame in dtmf_tone_frames("6", duration_ms=100, silence_ms=60):
        inband_hits.extend(hybrid.feed_pcmu(frame))
    assert inband_hits == []

    # After suppression window expires, in-band detection resumes
    now[0] = 100.45
    for frame in dtmf_tone_frames("4", duration_ms=100, silence_ms=60):
        inband_hits.extend(hybrid.feed_pcmu(frame))
    assert inband_hits == ["4"]
