"""CLI entrypoints for roboreka-server and the built-in roboreka-call softphone."""

from __future__ import annotations

import argparse
import asyncio
import logging
import signal
import socket
import sys
import uuid
from typing import Sequence

from roboreka.config import AppConfig, load_config
from roboreka.voip.rtp import RTPSession
from roboreka.voip.sdp import build_sdp_answer, parse_sdp
from roboreka.voip.sip import (
    SIPResponse,
    VALID_DTMF_DIGITS,
    format_sip_message,
    parse_sip_message,
)
from roboreka.voip.server import RoborekaServer
from roboreka.voip.tones import dtmf_tone_frames
from roboreka.web import ArmControlAPI


def _parse_port(value: str) -> int:
    try:
        port = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("port must be an integer") from exc
    if not 1 <= port <= 65535:
        raise argparse.ArgumentTypeError("port must be between 1 and 65535")
    return port


def _build_server_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="roboreka-server",
        description="VoIP (SIP/RTP + DTMF) server controlling a PCA9685 robot arm over I2C.",
    )
    parser.add_argument("--config", type=str, default=None, help="Path to TOML configuration file")
    parser.add_argument("--host", type=str, default=None, help="SIP/RTP bind IP address")
    parser.add_argument("--sip-port", type=int, default=None, help="SIP UDP listen port (default: 5060)")
    parser.add_argument("--advertise-ip", type=str, default=None, help="IP advertised in SDP/Contact")
    parser.add_argument(
        "--i2c-bus",
        type=int,
        default=None,
        help="Linux I2C bus number (NanoPi NEO v1.4 default: 0 for /dev/i2c-0)",
    )
    parser.add_argument(
        "--i2c-addr",
        type=lambda s: int(s, 0),
        default=None,
        help="PCA9685 7-bit I2C address (e.g. 0x40)",
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Use in-memory MockI2CBus instead of hardware /dev/i2c-*",
    )
    parser.add_argument(
        "--no-home",
        action="store_true",
        help="Skip homing servos to their initial angles on startup",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging verbosity (default: INFO)",
    )
    parser.add_argument("--api-port", type=_parse_port, default=8081, help="Local arm API port (default: 8081)")
    parser.add_argument(
        "--no-api",
        action="store_true",
        help="Disable the local arm API (the separate web app will not be able to control the arm)",
    )
    return parser


async def _run_server(
    config: AppConfig,
    config_path: str | None = None,
    api_enabled: bool = True,
    api_port: int = 8081,
) -> None:
    server = RoborekaServer(config)
    arm_api = ArmControlAPI(server, config_path, port=api_port) if api_enabled else None
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop_event.set)
        except (NotImplementedError, AttributeError, RuntimeError):
            pass

    try:
        await server.start()
        if arm_api is not None:
            arm_api.start()
        await stop_event.wait()
    finally:
        try:
            if arm_api is not None:
                arm_api.stop()
        finally:
            await server.stop()


def main_server(argv: Sequence[str] | None = None) -> int:
    """Entry point for `roboreka-server`."""
    args = _build_server_parser().parse_args(list(argv) if argv is not None else None)
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )

    config = load_config(args.config)
    if args.host is not None:
        config.sip.host = args.host
    if args.sip_port is not None:
        config.sip.port = args.sip_port
    if args.advertise_ip is not None:
        config.sip.advertise_ip = args.advertise_ip
    if args.i2c_bus is not None:
        config.i2c.bus = args.i2c_bus
    if args.i2c_addr is not None:
        config.i2c.address = args.i2c_addr
    if args.mock:
        config.i2c.mock = True
    if args.no_home:
        config.arm.home_on_start = False

    try:
        asyncio.run(
            _run_server(
                config,
                config_path=args.config,
                api_enabled=not args.no_api,
                api_port=args.api_port,
            )
        )
    except KeyboardInterrupt:
        pass
    return 0


def _parse_target(target: str) -> tuple[str, int]:
    if ":" in target:
        host, port_str = target.rsplit(":", 1)
        return host, int(port_str)
    return target, 5060


def _detect_local_ip_for(target_ip: str, target_port: int) -> str:
    if target_ip in ("127.0.0.1", "localhost"):
        return "127.0.0.1"
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect((target_ip, target_port))
            return str(sock.getsockname()[0])
    except OSError:
        return "127.0.0.1"


class _SIPClientProtocol(asyncio.DatagramProtocol):
    def __init__(self) -> None:
        self.transport: asyncio.DatagramTransport | None = None
        self.responses: asyncio.Queue[SIPResponse] = asyncio.Queue()

    def connection_made(self, transport: asyncio.BaseTransport) -> None:
        self.transport = transport  # type: ignore[assignment]

    def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:
        msg = parse_sip_message(data)
        if isinstance(msg, SIPResponse):
            self.responses.put_nowait(msg)

    def error_received(self, exc: Exception) -> None:
        logging.getLogger(__name__).debug("SIP client socket error ignored: %s", exc)


async def _wait_for_final_response(
    queue: asyncio.Queue[SIPResponse],
    expected_cseq_method: str,
    timeout: float,
) -> SIPResponse:
    deadline = asyncio.get_running_loop().time() + timeout
    while True:
        remaining = deadline - asyncio.get_running_loop().time()
        if remaining <= 0:
            raise TimeoutError(f"Timed out waiting for SIP {expected_cseq_method} response")
        resp = await asyncio.wait_for(queue.get(), timeout=remaining)
        cseq = resp.get_header("cseq")
        if expected_cseq_method in cseq and resp.status_code >= 200:
            return resp


async def _run_call(
    target: str,
    digits: str | None,
    mode: str,
    delay: float,
    timeout: float,
    bind_ip: str | None,
) -> int:
    target_ip, target_port = _parse_target(target)
    local_ip = bind_ip or _detect_local_ip_for(target_ip, target_port)

    loop = asyncio.get_running_loop()
    sip_proto = _SIPClientProtocol()
    sip_transport, _ = await loop.create_datagram_endpoint(
        lambda: sip_proto,
        local_addr=(local_ip, 0),
    )
    local_sip_port = int(sip_transport.get_extra_info("sockname")[1])

    rtp = RTPSession(
        bind_ip=local_ip,
        bind_port=0,
        remote_ip=target_ip,
        remote_port=0,
        telephone_event_pt=101,
        send_silence=False,
    )
    local_rtp_port = await rtp.start()

    call_id = uuid.uuid4().hex
    from_tag = uuid.uuid4().hex[:8]
    branch_base = f"z9hG4bK-{uuid.uuid4().hex[:8]}"
    cseq = 1

    try:
        offer_sdp = build_sdp_answer(local_ip, local_rtp_port, telephone_event_pt=101)
        invite = format_sip_message(
            f"INVITE sip:arm@{target_ip}:{target_port} SIP/2.0",
            [
                ("Via", f"SIP/2.0/UDP {local_ip}:{local_sip_port};branch={branch_base}-1;rport"),
                ("Max-Forwards", "70"),
                ("From", f"<sip:controller@{local_ip}>;tag={from_tag}"),
                ("To", f"<sip:arm@{target_ip}:{target_port}>"),
                ("Call-ID", call_id),
                ("CSeq", f"{cseq} INVITE"),
                ("Contact", f"<sip:controller@{local_ip}:{local_sip_port}>"),
                ("Content-Type", "application/sdp"),
            ],
            offer_sdp,
        )
        sip_transport.sendto(invite, (target_ip, target_port))

        resp = await _wait_for_final_response(sip_proto.responses, "INVITE", timeout)
        if resp.status_code != 200:
            print(f"INVITE failed: {resp.status_code} {resp.reason}", file=sys.stderr)
            return 1

        to_header = resp.get_header("to") or f"<sip:arm@{target_ip}:{target_port}>"
        srv_sdp = parse_sdp(resp.body)
        if srv_sdp.remote_port <= 0:
            print("Server SDP did not include a valid RTP port", file=sys.stderr)
            return 1

        rtp.remote_addr = (srv_sdp.remote_ip or target_ip, srv_sdp.remote_port)
        rtp.telephone_event_pt = srv_sdp.telephone_event_pt

        ack = format_sip_message(
            f"ACK sip:arm@{target_ip}:{target_port} SIP/2.0",
            [
                ("Via", f"SIP/2.0/UDP {local_ip}:{local_sip_port};branch={branch_base}-ack;rport"),
                ("Max-Forwards", "70"),
                ("From", f"<sip:controller@{local_ip}>;tag={from_tag}"),
                ("To", to_header),
                ("Call-ID", call_id),
                ("CSeq", f"{cseq} ACK"),
            ],
        )
        sip_transport.sendto(ack, (target_ip, target_port))
        print(f"Connected to {target_ip}:{target_port} (RTP {rtp.remote_addr[0]}:{rtp.remote_addr[1]}, mode={mode})")

        await asyncio.sleep(0.15)
        sent_digits: list[str] = []

        async def send_digit(ch: str) -> None:
            nonlocal cseq
            key = ch.upper()
            if key not in VALID_DTMF_DIGITS:
                raise ValueError(f"Unsupported DTMF digit: {ch!r}")
            if mode == "rfc4733":
                await rtp.send_rfc4733_digit(key)
            elif mode == "inband":
                rtp.enqueue_audio(dtmf_tone_frames(key))
                await asyncio.sleep(0.18)
            else:
                cseq += 1
                info_pkt = format_sip_message(
                    f"INFO sip:arm@{target_ip}:{target_port} SIP/2.0",
                    [
                        ("Via", f"SIP/2.0/UDP {local_ip}:{local_sip_port};branch={branch_base}-{cseq};rport"),
                        ("Max-Forwards", "70"),
                        ("From", f"<sip:controller@{local_ip}>;tag={from_tag}"),
                        ("To", to_header),
                        ("Call-ID", call_id),
                        ("CSeq", f"{cseq} INFO"),
                        ("Content-Type", "application/dtmf-relay"),
                    ],
                    f"Signal={key}\r\nDuration=160\r\n",
                )
                sip_transport.sendto(info_pkt, (target_ip, target_port))
                info_resp = await _wait_for_final_response(sip_proto.responses, "INFO", timeout)
                if info_resp.status_code != 200:
                    raise RuntimeError(f"INFO failed: {info_resp.status_code} {info_resp.reason}")
            sent_digits.append(key)

        if digits is not None:
            for ch in digits:
                if ch.isspace():
                    continue
                await send_digit(ch)
                await asyncio.sleep(delay)
        else:
            print("Enter DTMF digits (0-9, *, #, A-D) or 'q' to hang up:")
            while True:
                line = await asyncio.to_thread(sys.stdin.readline)
                if not line:
                    break
                cmd = line.strip()
                if cmd.lower() in ("q", "quit", "exit"):
                    break
                for ch in cmd:
                    if ch.isspace():
                        continue
                    await send_digit(ch)
                    await asyncio.sleep(delay)

        await asyncio.sleep(0.25)

        cseq += 1
        bye = format_sip_message(
            f"BYE sip:arm@{target_ip}:{target_port} SIP/2.0",
            [
                ("Via", f"SIP/2.0/UDP {local_ip}:{local_sip_port};branch={branch_base}-bye;rport"),
                ("Max-Forwards", "70"),
                ("From", f"<sip:controller@{local_ip}>;tag={from_tag}"),
                ("To", to_header),
                ("Call-ID", call_id),
                ("CSeq", f"{cseq} BYE"),
            ],
        )
        sip_transport.sendto(bye, (target_ip, target_port))
        await _wait_for_final_response(sip_proto.responses, "BYE", timeout)
        print(f"Sent digits={''.join(sent_digits)!r} | received {rtp.rx_audio_packets} RTP audio feedback packets")
        return 0
    finally:
        await rtp.stop()
        sip_transport.close()


def _build_call_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="roboreka-call",
        description="Lightweight SIP/RTP DTMF softphone client for testing Roboreka.",
    )
    parser.add_argument("target", help="Target SIP server host[:port] (e.g. 127.0.0.1:5060)")
    parser.add_argument("--digits", type=str, default=None, help='DTMF digits to send (e.g. "66425")')
    parser.add_argument(
        "--mode",
        choices=["rfc4733", "inband", "info"],
        default="rfc4733",
        help="DTMF transport mode (default: rfc4733)",
    )
    parser.add_argument("--delay", type=float, default=0.35, help="Pause between digits in seconds")
    parser.add_argument("--timeout", type=float, default=5.0, help="SIP transaction timeout in seconds")
    parser.add_argument("--bind-ip", type=str, default=None, help="Local bind IP address")
    return parser


def main_call(argv: Sequence[str] | None = None) -> int:
    """Entry point for `roboreka-call`."""
    args = _build_call_parser().parse_args(list(argv) if argv is not None else None)
    return asyncio.run(
        _run_call(
            target=args.target,
            digits=args.digits,
            mode=args.mode,
            delay=args.delay,
            timeout=args.timeout,
            bind_ip=args.bind_ip,
        )
    )
