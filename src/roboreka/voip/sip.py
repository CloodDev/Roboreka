"""RFC 3261 UDP SIP parser, formatter, and call signaling server."""

from __future__ import annotations

import asyncio
import inspect
import logging
import re
import socket
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable

from roboreka.config import SIPConfig
from roboreka.voip.rtp import RTPSession
from roboreka.voip.sdp import build_sdp_answer, parse_sdp

logger = logging.getLogger(__name__)

_COMPACT_HEADERS: dict[str, str] = {
    "v": "via",
    "f": "from",
    "t": "to",
    "i": "call-id",
    "l": "content-length",
    "c": "content-type",
    "m": "contact",
}

_CANONICAL_NAMES: dict[str, str] = {
    "via": "Via",
    "from": "From",
    "to": "To",
    "call-id": "Call-ID",
    "cseq": "CSeq",
    "contact": "Contact",
    "content-type": "Content-Type",
    "content-length": "Content-Length",
    "user-agent": "User-Agent",
    "allow": "Allow",
    "supported": "Supported",
    "expires": "Expires",
    "max-forwards": "Max-Forwards",
}

VALID_DTMF_DIGITS = frozenset("0123456789*#ABCD")


@dataclass
class SIPMessage:
    """Base parsed SIP message."""

    headers: dict[str, list[str]]
    body: str = ""

    def get_header(self, name: str, default: str = "") -> str:
        values = self.headers.get(name.lower())
        return values[0] if values else default

    def get_headers(self, name: str) -> list[str]:
        return list(self.headers.get(name.lower(), ()))


@dataclass
class SIPRequest(SIPMessage):
    """Parsed SIP request message."""

    method: str = ""
    uri: str = ""
    version: str = "SIP/2.0"


@dataclass
class SIPResponse(SIPMessage):
    """Parsed SIP response message."""

    status_code: int = 200
    reason: str = "OK"
    version: str = "SIP/2.0"


def parse_sip_message(data: bytes) -> SIPRequest | SIPResponse | None:
    """Parse a raw UDP SIP datagram into a SIPRequest or SIPResponse."""
    text = data.decode("utf-8", errors="replace")
    sep_idx = text.find("\r\n\r\n")
    sep_len = 4
    if sep_idx == -1:
        sep_idx = text.find("\n\n")
        sep_len = 2

    if sep_idx == -1:
        head = text
        body = ""
    else:
        head = text[:sep_idx]
        body = text[sep_idx + sep_len :]

    lines = [ln for ln in head.replace("\r\n", "\n").split("\n") if ln.strip()]
    if not lines:
        return None

    start_line = lines[0].strip()
    headers: dict[str, list[str]] = {}
    last_key: str | None = None
    for line in lines[1:]:
        if line[0] in (" ", "\t") and last_key is not None:
            headers[last_key][-1] += " " + line.strip()
            continue
        if ":" not in line:
            continue
        raw_key, raw_val = line.split(":", 1)
        key = raw_key.strip().lower()
        key = _COMPACT_HEADERS.get(key, key)
        val = raw_val.strip()
        if key == "via":
            headers.setdefault(key, []).extend(part.strip() for part in val.split(",") if part.strip())
        else:
            headers.setdefault(key, []).append(val)
        last_key = key

    if start_line.startswith("SIP/"):
        parts = start_line.split(None, 2)
        if len(parts) < 2:
            return None
        try:
            code = int(parts[1])
        except ValueError:
            return None
        reason = parts[2] if len(parts) > 2 else ""
        return SIPResponse(
            headers=headers,
            body=body,
            version=parts[0],
            status_code=code,
            reason=reason,
        )

    parts = start_line.split(None, 2)
    if len(parts) < 3 or not parts[2].startswith("SIP/"):
        return None
    return SIPRequest(
        headers=headers,
        body=body,
        method=parts[0].upper(),
        uri=parts[1],
        version=parts[2],
    )


def format_sip_message(
    start_line: str,
    headers: list[tuple[str, str]],
    body: str = "",
) -> bytes:
    """Serialize a SIP request or response with Content-Length populated."""
    body_bytes = body.encode("utf-8")
    lines = [start_line]
    has_cl = False
    for name, value in headers:
        lower = name.lower()
        canonical = _CANONICAL_NAMES.get(lower, name)
        if lower == "content-length":
            lines.append(f"Content-Length: {len(body_bytes)}")
            has_cl = True
        else:
            lines.append(f"{canonical}: {value}")
    if not has_cl:
        lines.append(f"Content-Length: {len(body_bytes)}")
    raw_head = ("\r\n".join(lines) + "\r\n\r\n").encode("utf-8")
    return raw_head + body_bytes


def format_sip_response(
    status_code: int,
    reason: str,
    headers: list[tuple[str, str]],
    body: str = "",
) -> bytes:
    """Format an RFC 3261 SIP response datagram."""
    return format_sip_message(f"SIP/2.0 {status_code} {reason}", headers, body)


def detect_advertise_ip(host: str, configured: str) -> str:
    """Resolve a routable IP address to advertise in SDP and SIP Contact headers."""
    if configured:
        return configured
    if host and host not in ("0.0.0.0", "::"):
        return host
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            return str(sock.getsockname()[0])
    except OSError:
        return "127.0.0.1"


def _rewrite_vias_for_response(vias: list[str], src_addr: tuple[str, int]) -> list[str]:
    if not vias:
        return []
    top = vias[0]
    src_ip, src_port = src_addr
    sent_by_host = ""
    parts = top.split(None, 1)
    if len(parts) == 2:
        hostport = parts[1].split(";", 1)[0].strip()
        sent_by_host = hostport.split(":", 1)[0]

    params = top.split(";")
    updated_params: list[str] = [params[0]]
    has_received = False
    for param in params[1:]:
        p = param.strip()
        lower = p.lower()
        if lower == "rport":
            updated_params.append(f"rport={src_port}")
        elif lower.startswith("received="):
            has_received = True
            updated_params.append(p)
        else:
            updated_params.append(p)

    if not has_received and sent_by_host != src_ip:
        updated_params.append(f"received={src_ip}")

    return [";".join(updated_params), *vias[1:]]


def _with_to_tag(to_header: str, local_tag: str) -> str:
    if ";tag=" in to_header.lower():
        return to_header
    return f"{to_header};tag={local_tag}"


def _extract_sip_info_digit(content_type: str, body: str) -> str | None:
    ct_lower = content_type.split(";", 1)[0].strip().lower()
    if ct_lower == "application/dtmf-relay":
        match = re.search(r"(?im)^signal\s*=\s*([0-9*#a-d])", body)
        if match:
            return match.group(1).upper()
        return None
    if ct_lower == "application/dtmf":
        stripped = body.strip()
        if stripped and stripped[0].upper() in VALID_DTMF_DIGITS:
            return stripped[0].upper()
        return None
    return None


@dataclass
class SIPCall:
    """Active SIP dialog and its associated RTP media session."""

    call_id: str
    from_header: str
    to_header: str
    local_tag: str
    remote_addr: tuple[str, int]
    rtp_session: RTPSession
    sdp_answer: str
    confirmed: bool = False
    started_notified: bool = False
    last_activity: float = field(default_factory=time.monotonic)


class SIPServer(asyncio.DatagramProtocol):
    """UDP RFC 3261 SIP server managing INVITE/ACK/INFO/BYE calls and RTP sessions."""

    def __init__(
        self,
        config: SIPConfig,
        on_call_started: Callable[[SIPCall], Any] | None = None,
        on_call_ended: Callable[[SIPCall], Any] | None = None,
        on_dtmf: Callable[[SIPCall, str, str], Any] | None = None,
    ) -> None:
        self.config = config
        self.on_call_started = on_call_started
        self.on_call_ended = on_call_ended
        self.on_dtmf = on_dtmf

        self.advertise_ip = detect_advertise_ip(config.host, config.advertise_ip)
        self.local_port: int = config.port
        self.calls: dict[str, SIPCall] = {}
        self.registrations: dict[str, str] = {}

        self._transport: asyncio.DatagramTransport | None = None
        self._next_rtp_port = config.rtp_port_start
        self._watchdog_task: asyncio.Task[None] | None = None

    async def start(self) -> int:
        """Bind the SIP UDP socket and start the idle-call timeout watchdog."""
        loop = asyncio.get_running_loop()
        transport, _ = await loop.create_datagram_endpoint(
            lambda: self,
            local_addr=(self.config.host, self.config.port),
        )
        self._transport = transport
        sockname = transport.get_extra_info("sockname")
        if sockname:
            self.local_port = int(sockname[1])

        if self.config.call_timeout_s > 0:
            self._watchdog_task = asyncio.create_task(self._timeout_watchdog())
        return self.local_port

    async def stop(self) -> None:
        """Close all active RTP sessions and shut down the SIP socket."""
        if self._watchdog_task is not None:
            self._watchdog_task.cancel()
            try:
                await self._watchdog_task
            except asyncio.CancelledError:
                pass
            self._watchdog_task = None

        for call in list(self.calls.values()):
            await self._teardown_call(call)

        if self._transport is not None:
            self._transport.close()
            self._transport = None

    def _allocate_rtp_port(self) -> int:
        start = self.config.rtp_port_start
        end = self.config.rtp_port_end
        if start <= 0 or end <= 0:
            return 0

        in_use = {call.rtp_session.local_port for call in self.calls.values()}
        span = max(1, (end - start) + 1)
        for offset in range(span):
            candidate = start + ((self._next_rtp_port - start + offset) % span)
            if candidate % 2 == 0 and candidate not in in_use:
                self._next_rtp_port = candidate + 2
                if self._next_rtp_port > end:
                    self._next_rtp_port = start
                return candidate
        return 0

    def _send(self, payload: bytes, addr: tuple[str, int]) -> None:
        if self._transport is not None:
            self._transport.sendto(payload, addr)

    @staticmethod
    def _base_reply_headers(
        req: SIPRequest,
        src_addr: tuple[str, int],
        to_tag: str | None = None,
    ) -> list[tuple[str, str]]:
        headers: list[tuple[str, str]] = []
        for via in _rewrite_vias_for_response(req.get_headers("via"), src_addr):
            headers.append(("Via", via))
        if req.get_header("from"):
            headers.append(("From", req.get_header("from")))
        to_val = req.get_header("to")
        if to_val:
            headers.append(("To", _with_to_tag(to_val, to_tag) if to_tag else to_val))
        if req.get_header("call-id"):
            headers.append(("Call-ID", req.get_header("call-id")))
        if req.get_header("cseq"):
            headers.append(("CSeq", req.get_header("cseq")))
        return headers

    def _contact_header(self) -> str:
        return f"<sip:roboreka@{self.advertise_ip}:{self.local_port}>"

    def _invoke_cb(self, cb: Callable[..., Any] | None, *args: Any) -> None:
        if cb is None:
            return
        try:
            res = cb(*args)
            if inspect.isawaitable(res):
                asyncio.create_task(res)
        except Exception:
            logger.exception("Unhandled exception in SIP callback")

    async def _teardown_call(self, call: SIPCall) -> None:
        removed = self.calls.pop(call.call_id, None)
        await call.rtp_session.stop()
        if removed is not None:
            self._invoke_cb(self.on_call_ended, removed)

    async def _timeout_watchdog(self) -> None:
        try:
            while True:
                await asyncio.sleep(5.0)
                now = time.monotonic()
                expired = [
                    call
                    for call in self.calls.values()
                    if (now - call.last_activity) > self.config.call_timeout_s
                ]
                for call in expired:
                    logger.info("Call %s timed out after %ds of inactivity", call.call_id, self.config.call_timeout_s)
                    await self._teardown_call(call)
        except asyncio.CancelledError:
            return

    def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:
        msg = parse_sip_message(data)
        if isinstance(msg, SIPRequest):
            asyncio.create_task(self._handle_request(msg, addr))

    def error_received(self, exc: Exception) -> None:
        logger.debug("SIP socket error ignored: %s", exc)

    async def _handle_request(self, req: SIPRequest, addr: tuple[str, int]) -> None:
        method = req.method
        if method == "OPTIONS":
            headers = self._base_reply_headers(req, addr, to_tag=uuid.uuid4().hex[:8])
            headers.extend([
                ("Contact", self._contact_header()),
                ("Allow", "INVITE, ACK, BYE, CANCEL, OPTIONS, REGISTER, INFO"),
                ("User-Agent", "Roboreka/0.1"),
            ])
            self._send(format_sip_response(200, "OK", headers), addr)
        elif method == "REGISTER":
            aor = req.get_header("from") or req.get_header("to")
            contact = req.get_header("contact")
            if aor and contact:
                self.registrations[aor] = contact
            headers = self._base_reply_headers(req, addr, to_tag=uuid.uuid4().hex[:8])
            if contact:
                headers.append(("Contact", contact))
            headers.append(("Expires", req.get_header("expires", "3600")))
            self._send(format_sip_response(200, "OK", headers), addr)
        elif method == "INVITE":
            await self._handle_invite(req, addr)
        elif method == "ACK":
            self._handle_ack(req)
        elif method == "INFO":
            self._handle_info(req, addr)
        elif method == "BYE":
            await self._handle_bye(req, addr)
        elif method == "CANCEL":
            await self._handle_cancel(req, addr)
        else:
            headers = self._base_reply_headers(req, addr, to_tag=uuid.uuid4().hex[:8])
            self._send(format_sip_response(501, "Not Implemented", headers), addr)

    async def _handle_invite(self, req: SIPRequest, addr: tuple[str, int]) -> None:
        call_id = req.get_header("call-id")
        if not call_id:
            headers = self._base_reply_headers(req, addr)
            self._send(format_sip_response(400, "Bad Request", headers), addr)
            return

        existing = self.calls.get(call_id)
        if existing is not None:
            existing.last_activity = time.monotonic()
            headers = self._base_reply_headers(req, addr, to_tag=existing.local_tag)
            headers.extend([
                ("Contact", self._contact_header()),
                ("Content-Type", "application/sdp"),
            ])
            self._send(format_sip_response(200, "OK", headers, existing.sdp_answer), addr)
            return

        local_tag = uuid.uuid4().hex[:10]
        if len(self.calls) >= self.config.max_concurrent_calls:
            headers = self._base_reply_headers(req, addr, to_tag=local_tag)
            self._send(format_sip_response(486, "Busy Here", headers), addr)
            return

        offer = parse_sdp(req.body)
        if not offer.supports_pcmu or offer.remote_port <= 0:
            headers = self._base_reply_headers(req, addr, to_tag=local_tag)
            self._send(format_sip_response(488, "Not Acceptable Here", headers), addr)
            return

        remote_ip = offer.remote_ip or addr[0]
        trying_headers = self._base_reply_headers(req, addr)
        self._send(format_sip_response(100, "Trying", trying_headers), addr)

        ringing_headers = self._base_reply_headers(req, addr, to_tag=local_tag)
        ringing_headers.append(("Contact", self._contact_header()))
        self._send(format_sip_response(180, "Ringing", ringing_headers), addr)

        rtp_port_hint = self._allocate_rtp_port()
        bind_ip = self.config.host if self.config.host not in ("", "0.0.0.0") else "0.0.0.0"

        call_holder: list[SIPCall] = []

        def on_rtp_dtmf(digit: str, source: str) -> None:
            if call_holder:
                call_obj = call_holder[0]
                call_obj.last_activity = time.monotonic()
                self._invoke_cb(self.on_dtmf, call_obj, digit, source)

        rtp_session = RTPSession(
            bind_ip=bind_ip,
            bind_port=rtp_port_hint,
            remote_ip=remote_ip,
            remote_port=offer.remote_port,
            telephone_event_pt=offer.telephone_event_pt,
            on_dtmf=on_rtp_dtmf,
        )
        bound_rtp_port = await rtp_session.start()

        sdp_answer = build_sdp_answer(
            local_ip=self.advertise_ip,
            local_rtp_port=bound_rtp_port,
            telephone_event_pt=offer.telephone_event_pt,
        )

        call = SIPCall(
            call_id=call_id,
            from_header=req.get_header("from"),
            to_header=_with_to_tag(req.get_header("to"), local_tag),
            local_tag=local_tag,
            remote_addr=addr,
            rtp_session=rtp_session,
            sdp_answer=sdp_answer,
        )
        call_holder.append(call)
        self.calls[call_id] = call

        ok_headers = self._base_reply_headers(req, addr, to_tag=local_tag)
        ok_headers.extend([
            ("Contact", self._contact_header()),
            ("Allow", "INVITE, ACK, BYE, CANCEL, OPTIONS, REGISTER, INFO"),
            ("Content-Type", "application/sdp"),
        ])
        self._send(format_sip_response(200, "OK", ok_headers, sdp_answer), addr)

    def _handle_ack(self, req: SIPRequest) -> None:
        call_id = req.get_header("call-id")
        call = self.calls.get(call_id)
        if call is None:
            return
        call.confirmed = True
        call.last_activity = time.monotonic()
        if not call.started_notified:
            call.started_notified = True
            self._invoke_cb(self.on_call_started, call)

    def _handle_info(self, req: SIPRequest, addr: tuple[str, int]) -> None:
        call_id = req.get_header("call-id")
        call = self.calls.get(call_id)
        if call is None:
            headers = self._base_reply_headers(req, addr)
            self._send(format_sip_response(481, "Call/Transaction Does Not Exist", headers), addr)
            return

        call.last_activity = time.monotonic()
        digit = _extract_sip_info_digit(req.get_header("content-type"), req.body)
        headers = self._base_reply_headers(req, addr, to_tag=call.local_tag)
        self._send(format_sip_response(200, "OK", headers), addr)
        if digit is not None:
            self._invoke_cb(self.on_dtmf, call, digit, "sip-info")

    async def _handle_bye(self, req: SIPRequest, addr: tuple[str, int]) -> None:
        call_id = req.get_header("call-id")
        call = self.calls.get(call_id)
        if call is None:
            headers = self._base_reply_headers(req, addr)
            self._send(format_sip_response(481, "Call/Transaction Does Not Exist", headers), addr)
            return

        headers = self._base_reply_headers(req, addr, to_tag=call.local_tag)
        await self._teardown_call(call)
        self._send(format_sip_response(200, "OK", headers), addr)

    async def _handle_cancel(self, req: SIPRequest, addr: tuple[str, int]) -> None:
        call_id = req.get_header("call-id")
        call = self.calls.get(call_id)
        headers = self._base_reply_headers(req, addr, to_tag=call.local_tag if call else None)
        if call is not None:
            await self._teardown_call(call)
        self._send(format_sip_response(200, "OK", headers), addr)
