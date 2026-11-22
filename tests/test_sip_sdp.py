"""Tests for SIP message parsing and SDP offer/answer negotiation."""

from __future__ import annotations

from roboreka.voip.sdp import build_sdp_answer, parse_sdp
from roboreka.voip.sip import SIPRequest, parse_sip_message


def test_parse_compact_sip_invite_with_multiple_vias() -> None:
    sdp = (
        "v=0\r\n"
        "o=alice 2890844526 2890844526 IN IP4 10.0.0.10\r\n"
        "s=-\r\n"
        "c=IN IP4 10.0.0.10\r\n"
        "t=0 0\r\n"
        "m=audio 40000 RTP/AVP 0 8 106\r\n"
        "a=rtpmap:0 PCMU/8000\r\n"
        "a=rtpmap:8 PCMA/8000\r\n"
        "a=rtpmap:106 telephone-event/8000\r\n"
    )
    raw = (
        "INVITE sip:arm@10.0.0.20:5060 SIP/2.0\r\n"
        "v: SIP/2.0/UDP 10.0.0.1:5060;branch=z9hG4bK-1, SIP/2.0/UDP 10.0.0.10:5060;branch=z9hG4bK-2\r\n"
        "f: <sip:alice@10.0.0.10>;tag=aaa\r\n"
        "t: <sip:arm@10.0.0.20>\r\n"
        "i: call-xyz-123\r\n"
        "CSeq: 1 INVITE\r\n"
        "c: application/sdp\r\n"
        f"l: {len(sdp)}\r\n"
        "\r\n"
        f"{sdp}"
    ).encode("utf-8")

    msg = parse_sip_message(raw)
    assert isinstance(msg, SIPRequest)
    assert msg.method == "INVITE"
    assert len(msg.get_headers("via")) == 2
    assert msg.get_header("call-id") == "call-xyz-123"
    assert msg.get_header("from") == "<sip:alice@10.0.0.10>;tag=aaa"
    assert msg.get_header("content-type") == "application/sdp"

    offer = parse_sdp(msg.body)
    assert offer.remote_ip == "10.0.0.10"
    assert offer.remote_port == 40000
    assert offer.supports_pcmu is True
    assert offer.telephone_event_pt == 106


def test_build_sdp_answer_preserves_dynamic_telephone_event_pt() -> None:
    answer = build_sdp_answer("192.168.1.50", 10002, telephone_event_pt=106)
    parsed = parse_sdp(answer)
    assert parsed.remote_ip == "192.168.1.50"
    assert parsed.remote_port == 10002
    assert parsed.supports_pcmu is True
    assert parsed.telephone_event_pt == 106


def test_sdp_without_telephone_event() -> None:
    sdp = (
        "v=0\r\n"
        "o=- 1 1 IN IP4 127.0.0.1\r\n"
        "s=call\r\n"
        "c=IN IP4 127.0.0.1\r\n"
        "t=0 0\r\n"
        "m=audio 30000 RTP/AVP 0\r\n"
        "a=rtpmap:0 PCMU/8000\r\n"
    )
    offer = parse_sdp(sdp)
    assert offer.supports_pcmu is True
    assert offer.telephone_event_pt is None

    answer = build_sdp_answer("127.0.0.1", 10000, telephone_event_pt=None)
    assert "telephone-event" not in answer
