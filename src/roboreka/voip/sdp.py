"""Minimal RFC 4566 SDP offer parser and answer builder for PCMU + telephone-event."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SDPOffer:
    """Parsed audio capabilities and endpoint from a remote SDP offer."""

    remote_ip: str = ""
    remote_port: int = 0
    supports_pcmu: bool = False
    telephone_event_pt: int | None = None


def parse_sdp(body: str) -> SDPOffer:
    """Parse an SDP body for IPv4 audio endpoint, PCMU (PT 0), and telephone-event PT."""
    offer = SDPOffer()
    audio_formats: list[str] = []
    in_audio_section = False

    for raw_line in body.replace("\r\n", "\n").split("\n"):
        line = raw_line.strip()
        if not line or "=" not in line:
            continue
        key, value = line.split("=", 1)

        if key == "c" and value.startswith("IN IP4 "):
            ip_part = value.split()[2].split("/", 1)[0]
            if in_audio_section or not offer.remote_ip:
                offer.remote_ip = ip_part
        elif key == "m":
            parts = value.split()
            in_audio_section = bool(parts and parts[0].lower() == "audio")
            if in_audio_section and len(parts) >= 4:
                try:
                    offer.remote_port = int(parts[1])
                except ValueError:
                    offer.remote_port = 0
                audio_formats = parts[3:]
                if "0" in audio_formats:
                    offer.supports_pcmu = True
        elif key == "a" and in_audio_section and value.startswith("rtpmap:"):
            rest = value[7:].strip()
            parts = rest.split(None, 1)
            if len(parts) == 2:
                pt_str, codec_info = parts
                codec_lower = codec_info.lower()
                if codec_lower.startswith("pcmu/") and pt_str in audio_formats:
                    offer.supports_pcmu = True
                elif codec_lower.startswith("telephone-event/") and pt_str in audio_formats:
                    try:
                        offer.telephone_event_pt = int(pt_str)
                    except ValueError:
                        pass

    return offer


def build_sdp_answer(
    local_ip: str,
    local_rtp_port: int,
    telephone_event_pt: int | None = 101,
) -> str:
    """Build an SDP answer offering PCMU (PT 0) and optional RFC 4733 telephone-event."""
    formats = ["0"]
    attrs = ["a=rtpmap:0 PCMU/8000"]
    if telephone_event_pt is not None:
        pt = str(telephone_event_pt)
        formats.append(pt)
        attrs.append(f"a=rtpmap:{pt} telephone-event/8000")
        attrs.append(f"a=fmtp:{pt} 0-15")

    lines = [
        "v=0",
        f"o=roboreka 0 0 IN IP4 {local_ip}",
        "s=Roboreka Arm Control",
        f"c=IN IP4 {local_ip}",
        "t=0 0",
        f"m=audio {local_rtp_port} RTP/AVP {' '.join(formats)}",
        *attrs,
        "a=ptime:20",
        "a=sendrecv",
    ]
    return "\r\n".join(lines) + "\r\n"
