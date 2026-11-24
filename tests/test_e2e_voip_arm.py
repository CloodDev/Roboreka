"""End-to-end VoIP (SIP + RTP + DTMF) to Mock PCA9685 I2C robot arm tests."""

from __future__ import annotations

import asyncio
import uuid

import pytest

from roboreka.config import AppConfig, ArmConfig, CallActionPose, I2CConfig, SIPConfig
from roboreka.i2c.pca9685 import PCA9685
from roboreka.voip.rtp import RTPSession
from roboreka.voip.sdp import build_sdp_answer, parse_sdp
from roboreka.voip.server import RoborekaServer
from roboreka.voip.sip import SIPResponse, format_sip_message, parse_sip_message
from roboreka.voip.tones import dtmf_tone_frames


class _CallerProtocol(asyncio.DatagramProtocol):
    def __init__(self) -> None:
        self.responses: asyncio.Queue[SIPResponse] = asyncio.Queue()

    def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:
        msg = parse_sip_message(data)
        if isinstance(msg, SIPResponse):
            self.responses.put_nowait(msg)


async def _wait_final(queue: asyncio.Queue[SIPResponse], method: str) -> SIPResponse:
    while True:
        resp = await asyncio.wait_for(queue.get(), timeout=3.0)
        if method in resp.get_header("cseq") and resp.status_code >= 200:
            return resp


async def _dial(
    server_port: int,
    telephone_event_pt: int | None = 101,
) -> tuple[asyncio.DatagramTransport, _CallerProtocol, RTPSession, str, str, str, int]:
    loop = asyncio.get_running_loop()
    proto = _CallerProtocol()
    sip_transport, _ = await loop.create_datagram_endpoint(
        lambda: proto,
        local_addr=("127.0.0.1", 0),
    )
    caller_sip_port = int(sip_transport.get_extra_info("sockname")[1])

    rtp = RTPSession(
        bind_ip="127.0.0.1",
        bind_port=0,
        remote_ip="127.0.0.1",
        remote_port=0,
        telephone_event_pt=telephone_event_pt,
        send_silence=False,
    )
    caller_rtp_port = await rtp.start()

    call_id = uuid.uuid4().hex
    from_tag = uuid.uuid4().hex[:8]
    offer = build_sdp_answer("127.0.0.1", caller_rtp_port, telephone_event_pt=telephone_event_pt)
    invite = format_sip_message(
        f"INVITE sip:arm@127.0.0.1:{server_port} SIP/2.0",
        [
            ("Via", f"SIP/2.0/UDP 127.0.0.1:{caller_sip_port};branch=z9hG4bK-{call_id[:8]}"),
            ("From", f"<sip:tester@127.0.0.1>;tag={from_tag}"),
            ("To", f"<sip:arm@127.0.0.1:{server_port}>"),
            ("Call-ID", call_id),
            ("CSeq", "1 INVITE"),
            ("Contact", f"<sip:tester@127.0.0.1:{caller_sip_port}>"),
            ("Content-Type", "application/sdp"),
        ],
        offer,
    )
    sip_transport.sendto(invite, ("127.0.0.1", server_port))
    resp = await _wait_final(proto.responses, "INVITE")
    assert resp.status_code == 200

    srv_sdp = parse_sdp(resp.body)
    assert srv_sdp.remote_port > 0
    rtp.remote_addr = ("127.0.0.1", srv_sdp.remote_port)

    to_hdr = resp.get_header("to")
    ack = format_sip_message(
        f"ACK sip:arm@127.0.0.1:{server_port} SIP/2.0",
        [
            ("Via", f"SIP/2.0/UDP 127.0.0.1:{caller_sip_port};branch=z9hG4bK-ack-{call_id[:8]}"),
            ("From", f"<sip:tester@127.0.0.1>;tag={from_tag}"),
            ("To", to_hdr),
            ("Call-ID", call_id),
            ("CSeq", "1 ACK"),
        ],
    )
    sip_transport.sendto(ack, ("127.0.0.1", server_port))
    return sip_transport, proto, rtp, call_id, from_tag, to_hdr, caller_sip_port


async def _hangup(
    sip_transport: asyncio.DatagramTransport,
    proto: _CallerProtocol,
    rtp: RTPSession,
    server_port: int,
    caller_sip_port: int,
    call_id: str,
    from_tag: str,
    to_hdr: str,
    cseq: int = 2,
) -> None:
    bye = format_sip_message(
        f"BYE sip:arm@127.0.0.1:{server_port} SIP/2.0",
        [
            ("Via", f"SIP/2.0/UDP 127.0.0.1:{caller_sip_port};branch=z9hG4bK-bye-{call_id[:8]}"),
            ("From", f"<sip:tester@127.0.0.1>;tag={from_tag}"),
            ("To", to_hdr),
            ("Call-ID", call_id),
            ("CSeq", f"{cseq} BYE"),
        ],
    )
    sip_transport.sendto(bye, ("127.0.0.1", server_port))
    resp = await _wait_final(proto.responses, "BYE")
    assert resp.status_code == 200
    await rtp.stop()
    sip_transport.close()


async def test_e2e_voip_turns_arm_via_rfc4733_inband_info_and_busy() -> None:
    cfg = AppConfig(
        sip=SIPConfig(
            host="127.0.0.1",
            port=0,
            rtp_port_start=0,
            rtp_port_end=0,
            max_concurrent_calls=1,
            call_timeout_s=60,
        ),
        i2c=I2CConfig(bus=0, address=0x40, pwm_frequency_hz=50.0, mock=True),
        arm=ArmConfig(home_on_start=True, speed_deg_per_sec=1000.0, release_on_shutdown=True),
    )
    server = RoborekaServer(cfg)
    sip_port = await server.start()

    try:
        # 1) RFC 4733 call: 6 (+15 base), 6 (+15 base -> 120), 2 (+15 shoulder -> 105)
        tx1, proto1, rtp1, cid1, ftag1, to1, csip1 = await _dial(sip_port, telephone_event_pt=101)
        await asyncio.sleep(0.10)
        await rtp1.send_rfc4733_digit("6", duration_ms=80)
        await asyncio.sleep(0.05)
        await rtp1.send_rfc4733_digit("6", duration_ms=80)
        await asyncio.sleep(0.05)
        await rtp1.send_rfc4733_digit("2", duration_ms=80)
        await asyncio.sleep(0.20)

        assert rtp1.rx_audio_packets > 0
        assert server.arm.get_state()["base"] == pytest.approx(120.0)
        assert server.arm.get_state()["shoulder"] == pytest.approx(105.0)
        assert server.pca9685.read_channel_pwm(0) == (0, 375)
        assert server.pca9685.read_channel_pwm(1) == (0, 348)

        # 4) Concurrent second call must be rejected with 486 Busy Here while Call 1 is active
        loop = asyncio.get_running_loop()
        busy_proto = _CallerProtocol()
        busy_tx, _ = await loop.create_datagram_endpoint(lambda: busy_proto, local_addr=("127.0.0.1", 0))
        busy_port = int(busy_tx.get_extra_info("sockname")[1])
        busy_invite = format_sip_message(
            f"INVITE sip:arm@127.0.0.1:{sip_port} SIP/2.0",
            [
                ("Via", f"SIP/2.0/UDP 127.0.0.1:{busy_port};branch=z9hG4bK-busy"),
                ("From", "<sip:intruder@127.0.0.1>;tag=intr1"),
                ("To", f"<sip:arm@127.0.0.1:{sip_port}>"),
                ("Call-ID", "busy-call-id"),
                ("CSeq", "1 INVITE"),
                ("Content-Type", "application/sdp"),
            ],
            build_sdp_answer("127.0.0.1", 40000),
        )
        busy_tx.sendto(busy_invite, ("127.0.0.1", sip_port))
        busy_resp = await _wait_final(busy_proto.responses, "INVITE")
        assert busy_resp.status_code == 486
        busy_tx.close()

        await _hangup(tx1, proto1, rtp1, sip_port, csip1, cid1, ftag1, to1)
        assert len(server.sip_server.calls) == 0

        # 2) In-band Goertzel call: 4 (-15 base -> 105), 5 (home all -> 90)
        tx2, proto2, rtp2, cid2, ftag2, to2, csip2 = await _dial(sip_port, telephone_event_pt=None)
        rtp2.enqueue_audio(dtmf_tone_frames("4"))
        await asyncio.sleep(0.22)
        assert server.arm.get_state()["base"] == pytest.approx(105.0)

        rtp2.enqueue_audio(dtmf_tone_frames("5"))
        await asyncio.sleep(0.22)
        assert server.arm.get_state()["base"] == pytest.approx(90.0)
        assert server.arm.get_state()["shoulder"] == pytest.approx(90.0)
        assert server.pca9685.read_channel_pwm(0) == (0, 307)

        await _hangup(tx2, proto2, rtp2, sip_port, csip2, cid2, ftag2, to2)

        # 3) SIP INFO call: Signal=3 (+45 base -> 135)
        tx3, proto3, rtp3, cid3, ftag3, to3, csip3 = await _dial(sip_port, telephone_event_pt=101)
        info = format_sip_message(
            f"INFO sip:arm@127.0.0.1:{sip_port} SIP/2.0",
            [
                ("Via", f"SIP/2.0/UDP 127.0.0.1:{csip3};branch=z9hG4bK-info1"),
                ("From", f"<sip:tester@127.0.0.1>;tag={ftag3}"),
                ("To", to3),
                ("Call-ID", cid3),
                ("CSeq", "2 INFO"),
                ("Content-Type", "application/dtmf-relay"),
            ],
            "Signal=3\r\nDuration=160\r\n",
        )
        tx3.sendto(info, ("127.0.0.1", sip_port))
        info_resp = await _wait_final(proto3.responses, "INFO")
        assert info_resp.status_code == 200
        await asyncio.sleep(0.15)
        assert server.arm.get_state()["base"] == pytest.approx(135.0)
        # 500 + (135/180)*2000 = 2000 us -> round(2000 / 20000 * 4096) = 410
        assert server.pca9685.read_channel_pwm(0) == (0, 410)

        await _hangup(tx3, proto3, rtp3, sip_port, csip3, cid3, ftag3, to3, cseq=3)
    finally:
        await server.stop()


async def test_call_action_sequence_returns_all_joints_home() -> None:
    cfg = AppConfig(
        sip=SIPConfig(host="127.0.0.1", port=0, rtp_port_start=0, rtp_port_end=0),
        i2c=I2CConfig(mock=True),
        arm=ArmConfig(
            home_on_start=True,
            speed_deg_per_sec=1000.0,
            call_sequence=[CallActionPose(angles={"base": 120.0}, hold_s=0.02)],
        ),
    )
    server = RoborekaServer(cfg)
    sip_port = await server.start()

    try:
        tx, proto, rtp, call_id, from_tag, to_header, caller_port = await _dial(sip_port)
        deadline = asyncio.get_running_loop().time() + 3.0
        while call_id not in server._call_action_tasks:
            if asyncio.get_running_loop().time() >= deadline:
                pytest.fail("automatic call action did not start")
            await asyncio.sleep(0.01)
        while call_id in server._call_action_tasks:
            if asyncio.get_running_loop().time() >= deadline:
                pytest.fail("automatic call action did not finish")
            await asyncio.sleep(0.01)

        assert server.arm.get_state()["base"] == pytest.approx(90.0)
        assert server.arm.get_state()["shoulder"] == pytest.approx(90.0)
        assert server.pca9685.read_channel_pwm(0) == (0, 307)
        assert any(
            operation == "write_block"
            and register == PCA9685.LED0_ON_L
            and data[2:] == [0x77, 0x01]
            for operation, _, register, data in server.bus.history
        )
        await _hangup(tx, proto, rtp, sip_port, caller_port, call_id, from_tag, to_header)
    finally:
        await server.stop()
