"""Standalone loopback web application that proxies to the arm controller API."""

from __future__ import annotations

import argparse
import ipaddress
import json
import logging
import signal
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from roboreka.web import _DASHBOARD_HTML

logger = logging.getLogger(__name__)
_MAX_REQUEST_BYTES = 64 * 1024


class WebUIApplication:
    """Serves the UI separately from the arm process and forwards API traffic."""

    def __init__(
        self,
        api_url: str = "http://127.0.0.1:8081",
        host: str = "127.0.0.1",
        port: int = 8080,
    ) -> None:
        parsed_api = urlsplit(api_url)
        if (
            parsed_api.scheme != "http"
            or not parsed_api.hostname
            or parsed_api.username is not None
            or parsed_api.password is not None
            or parsed_api.path not in ("", "/")
            or parsed_api.query
            or parsed_api.fragment
        ):
            raise ValueError("Arm API URL must be a plain http://host:port URL.")
        try:
            api_ip = ipaddress.ip_address(parsed_api.hostname)
        except ValueError as exc:
            raise ValueError("Arm API host must be a loopback IP address.") from exc
        if not isinstance(api_ip, ipaddress.IPv4Address) or not api_ip.is_loopback:
            raise ValueError("Arm API host must be an IPv4 loopback address.")
        try:
            api_port = parsed_api.port if parsed_api.port is not None else 80
        except ValueError as exc:
            raise ValueError("Arm API URL must use a valid port.") from exc
        if not 1 <= api_port <= 65535:
            raise ValueError("Arm API URL must use a port between 1 and 65535.")
        try:
            ui_ip = ipaddress.ip_address(host)
        except ValueError as exc:
            raise ValueError("Web UI bind address must be a loopback IP address.") from exc
        if not ui_ip.is_loopback:
            raise ValueError("Web UI bind address must be a loopback IP address.")
        self.api_url = f"http://{parsed_api.hostname}:{api_port}"
        self._httpd = self._make_http_server(host, port)
        self._thread: threading.Thread | None = None

    def _make_http_server(self, host: str, port: int) -> ThreadingHTTPServer:
        web_app = self

        class UIHTTPServer(ThreadingHTTPServer):
            daemon_threads = True
            allow_reuse_address = True

        class Handler(BaseHTTPRequestHandler):
            server_version = "RoborekaWeb"
            sys_version = ""

            def log_message(self, format: str, *args: Any) -> None:
                return

            def _is_local_request(self, check_origin: bool = False) -> bool:
                try:
                    if not ipaddress.ip_address(self.client_address[0]).is_loopback:
                        return False
                    host_header = urlsplit("//" + self.headers.get("Host", ""))
                    if host_header.hostname not in ("localhost", "127.0.0.1") or (
                        host_header.port != self.server.server_port
                    ):
                        return False
                    if check_origin:
                        origin = urlsplit(self.headers.get("Origin", ""))
                        if (
                            origin.scheme != "http"
                            or origin.hostname not in ("localhost", "127.0.0.1")
                            or origin.port != self.server.server_port
                        ):
                            return False
                    return True
                except ValueError:
                    return False

            def _send(self, status: int, content_type: str, body: bytes) -> None:
                self.send_response(status)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.send_header("Referrer-Policy", "no-referrer")
                self.send_header(
                    "Content-Security-Policy",
                    "default-src 'self'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; "
                    "connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'",
                )
                self.end_headers()
                self.wfile.write(body)

            def _send_json_error(self, status: int, message: str) -> None:
                self._send(status, "application/json; charset=utf-8", json.dumps({"error": message}).encode())

            def do_GET(self) -> None:
                if not self._is_local_request():
                    self._send_json_error(403, "Use the local web app address.")
                    return
                request_url = urlsplit(self.path)
                if request_url.path == "/":
                    self._send(200, "text/html; charset=utf-8", _DASHBOARD_HTML.encode("utf-8"))
                elif request_url.path.startswith("/api/"):
                    self._proxy("GET")
                else:
                    self._send_json_error(404, "Not found.")

            def do_POST(self) -> None:
                if not self._is_local_request(check_origin=True):
                    self._send_json_error(403, "Control requests must come from the local web app.")
                    return
                if not urlsplit(self.path).path.startswith("/api/"):
                    self._send_json_error(404, "Not found.")
                    return
                self._proxy("POST")

            def _proxy(self, method: str) -> None:
                body = None
                headers = {"Accept": "application/json"}
                if method == "POST":
                    if self.headers.get_content_type() != "application/json":
                        self._send_json_error(415, "Content-Type must be application/json.")
                        return
                    try:
                        content_length = int(self.headers.get("Content-Length", ""))
                    except ValueError:
                        self._send_json_error(400, "A valid Content-Length header is required.")
                        return
                    if content_length < 0 or content_length > _MAX_REQUEST_BYTES:
                        self._send_json_error(413, "Request body must be 64 KiB or smaller.")
                        return
                    body = self.rfile.read(content_length)
                    headers["Content-Type"] = "application/json"
                    api_port = urlsplit(web_app.api_url).port
                    headers["Origin"] = f"http://127.0.0.1:{api_port}"
                target = f"{web_app.api_url}{self.path}"
                api_request = Request(target, data=body, headers=headers, method=method)
                try:
                    with urlopen(api_request, timeout=30) as response:
                        self._send(
                            response.status,
                            response.headers.get("Content-Type", "application/json"),
                            response.read(_MAX_REQUEST_BYTES + 1),
                        )
                except HTTPError as exc:
                    error_body = exc.read(_MAX_REQUEST_BYTES + 1)
                    self._send(
                        exc.code,
                        exc.headers.get("Content-Type", "application/json"),
                        error_body,
                    )
                except (URLError, TimeoutError, OSError) as exc:
                    logger.warning("Arm API request failed: %s", exc)
                    self._send_json_error(502, "Arm controller API is unavailable.")

        return UIHTTPServer((host, port), Handler)

    def start(self) -> None:
        thread = threading.Thread(
            target=self._httpd.serve_forever,
            name="roboreka-web-ui",
            daemon=True,
        )
        thread.start()
        self._thread = thread
        logger.info("Roboreka web UI listening on http://127.0.0.1:%d", self._httpd.server_port)

    def stop(self) -> None:
        if self._thread is not None:
            self._httpd.shutdown()
            self._thread.join(timeout=5)
            self._thread = None
        self._httpd.server_close()


def _port(value: str) -> int:
    try:
        port = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("port must be an integer") from exc
    if not 1 <= port <= 65535:
        raise argparse.ArgumentTypeError("port must be between 1 and 65535")
    return port


def main_web(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="roboreka-web", description="Roboreka web UI process.")
    parser.add_argument("--api-url", default="http://127.0.0.1:8081", help="Loopback arm API URL")
    parser.add_argument("--host", default="127.0.0.1", help="Web UI bind address (loopback only)")
    parser.add_argument("--port", type=_port, default=8080, help="Web UI port (default: 8080)")
    args = parser.parse_args(argv)
    try:
        if not ipaddress.ip_address(args.host).is_loopback:
            parser.error("--host must be a loopback address")
        app = WebUIApplication(api_url=args.api_url, host=args.host, port=args.port)
    except ValueError as exc:
        parser.error(str(exc))

    stopped = threading.Event()

    def stop(_: int, __: Any) -> None:
        stopped.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, stop)
    app.start()
    try:
        stopped.wait()
    finally:
        app.stop()
    return 0
