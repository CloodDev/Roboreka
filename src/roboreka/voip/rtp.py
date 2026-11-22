"""Asyncio RFC 3550 RTP media session with G.711 PCMU feedback and DTMF decoding."""

from __future__ import annotations

import asyncio
import inspect
import logging
import random
import struct
from collections import deque
from dataclasses import dataclass
from typing import Any, Callable, Sequence

from roboreka.voip.dtmf import HybridDTMFDetector, encode_rfc4733
from roboreka.voip.g711 import FRAME_DURATION_MS, FRAME_SAMPLES, ULAW_SILENCE

logger = logging.getLogger(__name__)

PCMU_PAYLOAD_TYPE = 0
SILENCE_FRAME = bytes([ULAW_SILENCE]) * FRAME_SAMPLES


@dataclass(frozen=True)
class RTPPacket:
    """Parsed RFC 3550 RTP packet."""

    version: int
    padding: bool
    extension: bool
    marker: bool
    payload_type: int
    sequence: int
    timestamp: int
    ssrc: int
    payload: bytes


def pack_rtp_packet(
    payload_type: int,
    sequence: int,
    timestamp: int,
    ssrc: int,
    payload: bytes,
    marker: bool = False,
) -> bytes:
    """Serialize an RFC 3550 RTP packet (no CSRC/extensions)."""
    b0 = 0x80
    b1 = (0x80 if marker else 0x00) | (payload_type & 0x7F)
    header = struct.pack("!BBHII", b0, b1, sequence & 0xFFFF, timestamp & 0xFFFFFFFF, ssrc & 0xFFFFFFFF)
    return header + payload


def unpack_rtp_packet(data: bytes) -> RTPPacket | None:
    """Parse an RFC 3550 RTP packet, handling padding, CSRC list, and extensions."""
    if len(data) < 12:
        return None
    b0, b1, sequence, timestamp, ssrc = struct.unpack("!BBHII", data[:12])
    version = (b0 >> 6) & 0x03
    if version != 2:
        return None

    padding = bool(b0 & 0x20)
    extension = bool(b0 & 0x10)
    cc = b0 & 0x0F
    marker = bool(b1 & 0x80)
    payload_type = b1 & 0x7F

    offset = 12 + 4 * cc
    if len(data) < offset:
        return None

    if extension:
        if len(data) < offset + 4:
            return None
        _, ext_words = struct.unpack("!HH", data[offset : offset + 4])
        offset += 4 + 4 * ext_words
        if len(data) < offset:
            return None

    end = len(data)
    if padding:
        pad_len = data[-1]
        if pad_len == 0 or end - pad_len < offset:
            return None
        end -= pad_len

    return RTPPacket(
        version=version,
        padding=padding,
        extension=extension,
        marker=marker,
        payload_type=payload_type,
        sequence=sequence,
        timestamp=timestamp,
        ssrc=ssrc,
        payload=data[offset:end],
    )


class RTPSession(asyncio.DatagramProtocol):
    """Bidirectional RTP UDP session handling PCMU audio feedback and DTMF detection."""

    def __init__(
        self,
        bind_ip: str,
        bind_port: int,
        remote_ip: str,
        remote_port: int,
        telephone_event_pt: int | None = 101,
        on_dtmf: Callable[[str, str], Any] | None = None,
        send_silence: bool = True,
    ) -> None:
        self.bind_ip = bind_ip
        self.bind_port = bind_port
        self.remote_addr = (remote_ip, remote_port)
        self.telephone_event_pt = telephone_event_pt
        self.on_dtmf = on_dtmf
        self.send_silence = send_silence

        self.local_port: int = bind_port
        self.ssrc: int = random.randint(1, 0xFFFFFFFF)
        self._seq: int = random.randint(0, 0xFFFF)
        self._ts: int = random.randint(0, 0xFFFFFFFF)

        self._transport: asyncio.DatagramTransport | None = None
        self._tx_queue: deque[bytes] = deque()
        self._tx_task: asyncio.Task[None] | None = None
        self._detector = HybridDTMFDetector()
        self._running = False

        self.rx_packets: int = 0
        self.rx_audio_packets: int = 0
        self.tx_packets: int = 0

    async def start(self) -> int:
        """Bind the UDP socket and begin the 20 ms RTP transmitter loop."""
        loop = asyncio.get_running_loop()
        transport, _ = await loop.create_datagram_endpoint(
            lambda: self,
            local_addr=(self.bind_ip, self.bind_port),
        )
        self._transport = transport
        sockname = transport.get_extra_info("sockname")
        if sockname:
            self.local_port = int(sockname[1])
        self._running = True
        self._tx_task = asyncio.create_task(self._tx_loop())
        return self.local_port

    async def stop(self) -> None:
        """Stop the RTP session and close its UDP socket."""
        self._running = False
        if self._tx_task is not None:
            self._tx_task.cancel()
            try:
                await self._tx_task
            except asyncio.CancelledError:
                pass
            self._tx_task = None
        if self._transport is not None:
            self._transport.close()
            self._transport = None

    def enqueue_audio(self, frames: Sequence[bytes]) -> None:
        """Queue 160-byte PCMU audio frames to be streamed to the remote peer."""
        self._tx_queue.extend(frames)

    def send_raw_packet(
        self,
        payload_type: int,
        payload: bytes,
        timestamp: int | None = None,
        marker: bool = False,
    ) -> None:
        """Send an immediate RTP packet to the remote peer."""
        if self._transport is None or self.remote_addr[1] <= 0:
            return
        pkt_ts = self._ts if timestamp is None else timestamp
        pkt = pack_rtp_packet(
            payload_type=payload_type,
            sequence=self._seq,
            timestamp=pkt_ts,
            ssrc=self.ssrc,
            payload=payload,
            marker=marker,
        )
        self._seq = (self._seq + 1) & 0xFFFF
        self._transport.sendto(pkt, self.remote_addr)
        self.tx_packets += 1

    async def send_rfc4733_digit(
        self,
        digit: str,
        duration_ms: int = 160,
        pt: int | None = None,
    ) -> None:
        """Transmit a DTMF digit formatted per RFC 4733 (start, interim, 3x end)."""
        event_pt = self.telephone_event_pt if pt is None else pt
        if event_pt is None:
            event_pt = 101

        steps = max(2, duration_ms // FRAME_DURATION_MS)
        event_ts = self._ts
        for step in range(1, steps + 1):
            dur_samples = step * FRAME_SAMPLES
            is_first = step == 1
            payload = encode_rfc4733(digit, end=False, duration=dur_samples)
            self.send_raw_packet(event_pt, payload, timestamp=event_ts, marker=is_first)
            await asyncio.sleep(FRAME_DURATION_MS / 1000.0)

        end_payload = encode_rfc4733(digit, end=True, duration=steps * FRAME_SAMPLES)
        for _ in range(3):
            self.send_raw_packet(event_pt, end_payload, timestamp=event_ts, marker=False)
        self._ts = (self._ts + steps * FRAME_SAMPLES) & 0xFFFFFFFF

    async def _tx_loop(self) -> None:
        loop = asyncio.get_running_loop()
        interval = FRAME_DURATION_MS / 1000.0
        next_tick = loop.time()

        try:
            while self._running:
                if self._tx_queue:
                    frame = self._tx_queue.popleft()
                    self.send_raw_packet(PCMU_PAYLOAD_TYPE, frame)
                    self._ts = (self._ts + FRAME_SAMPLES) & 0xFFFFFFFF
                elif self.send_silence:
                    self.send_raw_packet(PCMU_PAYLOAD_TYPE, SILENCE_FRAME)
                    self._ts = (self._ts + FRAME_SAMPLES) & 0xFFFFFFFF

                next_tick += interval
                delay = next_tick - loop.time()
                if delay > 0:
                    await asyncio.sleep(delay)
                else:
                    next_tick = loop.time()
        except asyncio.CancelledError:
            return

    def _emit_dtmf(self, digit: str, source: str) -> None:
        if self.on_dtmf is None:
            return
        try:
            result = self.on_dtmf(digit, source)
            if inspect.isawaitable(result):
                asyncio.create_task(result)
        except Exception:
            logger.exception("Unhandled exception in DTMF callback for digit %r", digit)

    def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:
        pkt = unpack_rtp_packet(data)
        if pkt is None:
            return

        self.rx_packets += 1
        if self.telephone_event_pt is not None and pkt.payload_type == self.telephone_event_pt:
            digit = self._detector.feed_rfc4733(pkt.timestamp, pkt.payload)
            if digit is not None:
                self._emit_dtmf(digit, "rfc4733")
        elif pkt.payload_type == PCMU_PAYLOAD_TYPE:
            self.rx_audio_packets += 1
            for digit in self._detector.feed_pcmu(pkt.payload):
                self._emit_dtmf(digit, "inband")

    def error_received(self, exc: Exception) -> None:
        # Windows raises ConnectionResetError on UDP when remote port isn't open yet.
        logger.debug("RTP socket error ignored: %s", exc)
