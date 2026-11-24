"""Loopback-only dashboard for Roboreka status, logs, and configuration."""

from __future__ import annotations

import asyncio
import concurrent.futures
import ipaddress
import json
import logging
import math
import os
import re
import stat
import tempfile
import threading
import time
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.parse import parse_qs, urlsplit

from roboreka.config import _parse_call_sequence, load_config, tomllib
from roboreka.dashboard_ui import DASHBOARD_HTML as _DASHBOARD_HTML

if TYPE_CHECKING:
    from roboreka.voip.server import RoborekaServer

logger = logging.getLogger(__name__)
_MAX_CONFIG_BYTES = 64 * 1024
_MAX_ACTION_POSES = 100


def _replace_call_sequence(content: str, poses: list[dict[str, Any]]) -> str:
    newline = "\r\n" if "\r\n" in content else "\n"
    lines = content.splitlines(keepends=True)
    table_header = re.compile(r"^\s*\[{1,2}[^\]]+\]{1,2}\s*(?:#.*)?(?:\r?\n)?$")
    action_header = re.compile(r"^\s*\[\[arm\.call_sequence\]\]\s*(?:#.*)?(?:\r?\n)?$")

    kept_lines: list[str] = []
    index = 0
    while index < len(lines):
        if not action_header.match(lines[index]):
            kept_lines.append(lines[index])
            index += 1
            continue
        index += 1
        while index < len(lines) and not table_header.match(lines[index]):
            index += 1

    insert_at = next(
        (i for i, line in enumerate(kept_lines) if re.match(r"^\s*\[\[arm\.joints\]\]", line)),
        None,
    )
    if insert_at is None:
        arm_header = next(
            (i for i, line in enumerate(kept_lines) if re.match(r"^\s*\[arm\]\s*(?:#.*)?(?:\r?\n)?$", line)),
            None,
        )
        if arm_header is None:
            if not poses:
                return "".join(kept_lines)
            kept_lines.extend([newline, "[arm]", newline])
            insert_at = len(kept_lines)
        else:
            insert_at = next(
                (i for i in range(arm_header + 1, len(kept_lines)) if table_header.match(kept_lines[i])),
                len(kept_lines),
            )

    generated: list[str] = []
    for pose in poses:
        angles_literal = (
            "{ "
            + ", ".join(
                f"{json.dumps(name)} = {format(angle, '.15g')}"
                for name, angle in pose["angles"].items()
            )
            + " }"
            if pose["angles"]
            else "{}"
        )
        generated.extend(
            (
                "[[arm.call_sequence]]",
                f"angles = {angles_literal}",
                f"hold_s = {format(pose['hold_s'], '.15g')}",
                "",
            )
        )
    if generated:
        generated = [f"{line}{newline}" for line in generated]
        if insert_at > 0 and kept_lines[insert_at - 1] and not kept_lines[insert_at - 1].endswith(("\n", "\r")):
            generated.insert(0, newline)
        kept_lines[insert_at:insert_at] = generated
    return "".join(kept_lines)


class _MemoryLogHandler(logging.Handler):
    def __init__(self, capacity: int = 500) -> None:
        super().__init__()
        self.records: deque[dict[str, str]] = deque(maxlen=capacity)

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self.records.append(
                {
                    "time": self.formatter.formatTime(record, "%Y-%m-%d %H:%M:%S")
                    if self.formatter
                    else time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(record.created)),
                    "level": record.levelname,
                    "logger": record.name,
                    "message": record.getMessage(),
                }
            )
        except Exception:
            self.handleError(record)

    def snapshot(self, limit: int) -> list[dict[str, str]]:
        self.acquire()
        try:
            return list(self.records)[-limit:]
        finally:
            self.release()


class ArmControlAPI:
    """Local API for arm status, direct controls, logs, and configuration."""

    def __init__(
        self,
        app: RoborekaServer,
        config_path: str | Path | None,
        port: int = 8081,
    ) -> None:
        self.app = app
        self.config_path = Path(config_path).resolve() if config_path is not None else None
        self.started_at = time.monotonic()
        self.log_handler = _MemoryLogHandler()
        self._config_lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._httpd = self._make_http_server(port)

    def _make_http_server(self, port: int) -> ThreadingHTTPServer:
        dashboard = self

        class DashboardHTTPServer(ThreadingHTTPServer):
            daemon_threads = True
            allow_reuse_address = True

        class Handler(BaseHTTPRequestHandler):
            server_version = "RoborekaDashboard"
            sys_version = ""

            def log_message(self, format: str, *args: Any) -> None:
                return

            def _is_local_request(self, check_origin: bool = False) -> bool:
                try:
                    if not ipaddress.ip_address(self.client_address[0]).is_loopback:
                        return False
                    host = urlsplit("//" + self.headers.get("Host", ""))
                    if host.hostname not in ("localhost", "127.0.0.1") or host.port != self.server.server_port:
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

            def _send_json(self, status: int, data: dict[str, Any]) -> None:
                body = json.dumps(data).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self._send_security_headers()
                self.end_headers()
                self.wfile.write(body)

            def _send_security_headers(self) -> None:
                self.send_header("X-Content-Type-Options", "nosniff")
                self.send_header("Referrer-Policy", "no-referrer")
                self.send_header(
                    "Content-Security-Policy",
                    "default-src 'self'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; "
                    "connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'",
                )

            def _send_error_json(self, status: int, message: str) -> None:
                self._send_json(status, {"error": message})

            def do_GET(self) -> None:
                if not self._is_local_request():
                    self._send_error_json(403, "Requests must use the local dashboard address.")
                    return

                path = urlsplit(self.path).path
                if path == "/":
                    self._send_error_json(404, "This is the arm API. Open the separate Roboreka web app.")
                elif path == "/api/status":
                    self._send_json(200, dashboard.status())
                elif path == "/api/action-sequence":
                    try:
                        self._send_json(200, dashboard.action_sequence())
                    except (OSError, ValueError, tomllib.TOMLDecodeError):
                        logger.exception("Unable to load dashboard call action")
                        self._send_error_json(500, "Unable to load the call action configuration.")
                elif path == "/api/logs":
                    query = parse_qs(urlsplit(self.path).query)
                    try:
                        limit = max(1, min(500, int(query.get("limit", ["100"])[0])))
                    except ValueError:
                        self._send_error_json(400, "Log limit must be an integer.")
                        return
                    self._send_json(200, {"logs": dashboard.log_handler.snapshot(limit)})
                elif path == "/api/config":
                    self._get_config()
                else:
                    self._send_error_json(404, "Not found.")

            def _get_config(self) -> None:
                if dashboard.config_path is None:
                    self._send_json(
                        200,
                        {
                            "content": "",
                            "editable": False,
                            "message": "No configuration file was supplied to the server.",
                        },
                    )
                    return
                try:
                    content = dashboard.config_path.read_text(encoding="utf-8")
                except OSError:
                    logger.exception("Unable to read dashboard configuration")
                    self._send_error_json(500, "Unable to read the configuration file.")
                    return
                editable = os.access(dashboard.config_path.parent, os.W_OK | os.X_OK)
                self._send_json(
                    200,
                    {
                        "content": content,
                        "editable": editable,
                        "message": None
                        if editable
                        else "The dashboard process cannot write to the configuration directory.",
                    },
                )

            def do_POST(self) -> None:
                if not self._is_local_request(check_origin=True):
                    self._send_error_json(403, "Configuration changes must come from this local dashboard.")
                    return
                if urlsplit(self.path).path != "/api/config":
                    if urlsplit(self.path).path == "/api/action-sequence":
                        self._post_action_sequence()
                        return
                    if urlsplit(self.path).path.startswith("/api/arm/"):
                        self._post_arm_control()
                        return
                    self._send_error_json(404, "Not found.")
                    return
                if dashboard.config_path is None:
                    self._send_error_json(409, "No configuration file was supplied to the server.")
                    return
                if not os.access(dashboard.config_path.parent, os.W_OK | os.X_OK):
                    self._send_error_json(403, "The dashboard process cannot write to the configuration directory.")
                    return
                if self.headers.get_content_type() != "application/json":
                    self._send_error_json(415, "Content-Type must be application/json.")
                    return
                try:
                    content_length = int(self.headers.get("Content-Length", ""))
                except ValueError:
                    self._send_error_json(400, "A valid Content-Length header is required.")
                    return
                if content_length < 0 or content_length > _MAX_CONFIG_BYTES:
                    self._send_error_json(413, "Configuration must be 64 KiB or smaller.")
                    return
                try:
                    payload = json.loads(self.rfile.read(content_length))
                    if not isinstance(payload, dict) or not isinstance(payload.get("content"), str):
                        raise ValueError("Configuration content must be a string.")
                    content = payload["content"]
                    dashboard.save_config(content)
                except (
                    json.JSONDecodeError,
                    UnicodeDecodeError,
                    ValueError,
                    TypeError,
                    KeyError,
                    OverflowError,
                    tomllib.TOMLDecodeError,
                ) as exc:
                    self._send_error_json(400, f"Invalid configuration: {exc}")
                    return
                except OSError:
                    logger.exception("Unable to save dashboard configuration")
                    self._send_error_json(500, "Unable to save the configuration file.")
                    return
                self._send_json(
                    200,
                    {"message": "Configuration saved. Restart Roboreka to apply the changes."},
                )

            def _read_json_payload(self) -> dict[str, Any]:
                if self.headers.get_content_type() != "application/json":
                    raise ValueError("Content-Type must be application/json.")
                try:
                    content_length = int(self.headers.get("Content-Length", ""))
                except ValueError as exc:
                    raise ValueError("A valid Content-Length header is required.") from exc
                if content_length < 0 or content_length > _MAX_CONFIG_BYTES:
                    raise OverflowError("Request body must be 64 KiB or smaller.")
                payload = json.loads(self.rfile.read(content_length))
                if not isinstance(payload, dict):
                    raise ValueError("The JSON request body must be an object.")
                return payload

            def _post_arm_control(self) -> None:
                action = urlsplit(self.path).path.removeprefix("/api/arm/")
                try:
                    payload = self._read_json_payload()
                except OverflowError as exc:
                    self._send_error_json(413, str(exc))
                    return
                except (ValueError, json.JSONDecodeError, UnicodeDecodeError) as exc:
                    self._send_error_json(400, str(exc))
                    return
                try:
                    loop = dashboard.app.event_loop
                except RuntimeError as exc:
                    self._send_error_json(503, str(exc))
                    return

                if action == "move":
                    joint_name = payload.get("joint")
                    angle = payload.get("angle")
                    if not isinstance(joint_name, str) or joint_name not in dashboard.app.arm.joints:
                        self._send_error_json(400, "joint must name a configured arm joint.")
                        return
                    if isinstance(angle, bool) or not isinstance(angle, (int, float)):
                        self._send_error_json(400, "angle must be a number.")
                        return
                    joint = dashboard.app.arm.joints[joint_name]
                    target = float(angle)
                    if not math.isfinite(target) or not joint.min_angle <= target <= joint.max_angle:
                        self._send_error_json(
                            400,
                            f"angle must be between {joint.min_angle} and {joint.max_angle} degrees.",
                        )
                        return
                    if dashboard.app.call_action_running:
                        self._send_error_json(409, "Wait for the automatic call action to finish first.")
                        return
                    try:
                        asyncio.run_coroutine_threadsafe(
                            dashboard.app.arm.move_to(joint_name, target),
                            loop,
                        ).result(timeout=30)
                    except concurrent.futures.TimeoutError:
                        self._send_error_json(504, "The arm move did not finish in time.")
                        return
                    except (KeyError, ValueError, OSError) as exc:
                        self._send_error_json(400, str(exc))
                        return
                    self._send_json(200, {"message": f"Moved {joint_name} to {target:g}°."})
                    return

                if action == "pose":
                    raw_angles = payload.get("angles")
                    if not isinstance(raw_angles, dict) or not raw_angles:
                        self._send_error_json(400, "angles must be a non-empty object mapping joint names to degrees.")
                        return
                    angles: dict[str, float] = {}
                    for joint_name, raw_angle in raw_angles.items():
                        if not isinstance(joint_name, str) or joint_name not in dashboard.app.arm.joints:
                            self._send_error_json(400, "angles keys must name configured arm joints.")
                            return
                        if isinstance(raw_angle, bool) or not isinstance(raw_angle, (int, float)):
                            self._send_error_json(400, f"angle for {joint_name} must be a number.")
                            return
                        joint = dashboard.app.arm.joints[joint_name]
                        target = float(raw_angle)
                        if not math.isfinite(target) or not joint.min_angle <= target <= joint.max_angle:
                            self._send_error_json(
                                400,
                                f"angle for {joint_name} must be between {joint.min_angle} and {joint.max_angle} degrees.",
                            )
                            return
                        angles[joint_name] = target
                    if dashboard.app.call_action_running:
                        self._send_error_json(409, "Wait for the automatic call action to finish first.")
                        return
                    try:
                        asyncio.run_coroutine_threadsafe(
                            dashboard.app.arm.move_to_pose(angles),
                            loop,
                        ).result(timeout=30)
                    except concurrent.futures.TimeoutError:
                        self._send_error_json(504, "The arm pose move did not finish in time.")
                        return
                    except (KeyError, ValueError, OSError) as exc:
                        self._send_error_json(400, str(exc))
                        return
                    self._send_json(200, {"message": f"Moved {len(angles)} joint(s) to target pose."})
                    return

                if action in ("home", "stop", "release") and dashboard.app.call_action_running:
                    if action == "stop" or action == "release":
                        try:
                            asyncio.run_coroutine_threadsafe(
                                dashboard.app.stop_arm(release=action == "release"),
                                loop,
                            ).result(timeout=30)
                        except concurrent.futures.TimeoutError:
                            self._send_error_json(504, "The arm stop action did not finish in time.")
                            return
                        except (OSError, ValueError) as exc:
                            self._send_error_json(500, str(exc))
                            return
                        message = "Motion stopped." if action == "stop" else "Motion stopped and servos released."
                        self._send_json(200, {"message": message})
                        return
                    self._send_error_json(409, "Wait for the automatic call action to finish first.")
                    return

                if action == "home":
                    operation = dashboard.app.arm.home_all()
                    message = "All joints returned home."
                elif action == "stop":
                    operation = dashboard.app.stop_arm(release=False)
                    message = "Motion stopped."
                elif action == "release":
                    operation = dashboard.app.stop_arm(release=True)
                    message = "Motion stopped and servos released."
                else:
                    self._send_error_json(404, "Unknown arm control action.")
                    return
                try:
                    asyncio.run_coroutine_threadsafe(operation, loop).result(timeout=30)
                except concurrent.futures.TimeoutError:
                    self._send_error_json(504, "The arm control action did not finish in time.")
                    return
                except (OSError, ValueError) as exc:
                    self._send_error_json(500, str(exc))
                    return
                self._send_json(200, {"message": message})

            def _post_action_sequence(self) -> None:
                if dashboard.config_path is None:
                    self._send_error_json(409, "No configuration file was supplied to the server.")
                    return
                if not os.access(dashboard.config_path.parent, os.W_OK | os.X_OK):
                    self._send_error_json(403, "The dashboard process cannot write to the configuration directory.")
                    return
                if self.headers.get_content_type() != "application/json":
                    self._send_error_json(415, "Content-Type must be application/json.")
                    return
                try:
                    content_length = int(self.headers.get("Content-Length", ""))
                except ValueError:
                    self._send_error_json(400, "A valid Content-Length header is required.")
                    return
                if content_length < 0 or content_length > _MAX_CONFIG_BYTES:
                    self._send_error_json(413, "Action sequence must fit within 64 KiB.")
                    return
                try:
                    payload = json.loads(self.rfile.read(content_length))
                    raw_poses = payload.get("poses") if isinstance(payload, dict) else None
                    if not isinstance(raw_poses, list):
                        raise ValueError("poses must be a list.")
                    if len(raw_poses) > _MAX_ACTION_POSES:
                        raise ValueError(f"Use no more than {_MAX_ACTION_POSES} pose blocks.")
                    file_config = load_config(dashboard.config_path)
                    parsed = _parse_call_sequence(raw_poses, file_config.arm.joints)
                    poses = [
                        {"angles": pose.angles, "hold_s": pose.hold_s}
                        for pose in parsed
                    ]
                    content = dashboard.config_path.read_text(encoding="utf-8")
                    updated = _replace_call_sequence(content, poses)
                    dashboard.save_config(updated)
                except (
                    json.JSONDecodeError,
                    UnicodeDecodeError,
                    ValueError,
                    TypeError,
                    KeyError,
                    OverflowError,
                    tomllib.TOMLDecodeError,
                ) as exc:
                    self._send_error_json(400, f"Invalid call action: {exc}")
                    return
                except OSError:
                    logger.exception("Unable to save dashboard call action")
                    self._send_error_json(500, "Unable to save the call action.")
                    return
                self._send_json(
                    200,
                    {
                        "config": updated,
                        "message": f"Saved {len(poses)} pose block(s). Restart Roboreka to apply them.",
                    },
                )

        return DashboardHTTPServer(("127.0.0.1", port), Handler)

    def start(self) -> None:
        logging.getLogger().addHandler(self.log_handler)
        thread = threading.Thread(
            target=self._httpd.serve_forever,
            name="roboreka-dashboard",
            daemon=True,
        )
        thread.start()
        self._thread = thread
        logger.info("Roboreka dashboard listening on http://127.0.0.1:%d", self._httpd.server_port)

    def stop(self) -> None:
        if self._thread is not None:
            self._httpd.shutdown()
            self._thread.join(timeout=5)
            self._thread = None
        self._httpd.server_close()
        logging.getLogger().removeHandler(self.log_handler)

    def status(self) -> dict[str, Any]:
        config = self.app.config
        mock = config.i2c.mock
        device_path = Path(f"/dev/i2c-{config.i2c.bus}")
        return {
            "uptime_seconds": max(0, int(time.monotonic() - self.started_at)),
            "active_calls": len(self.app.sip_server.calls),
            "max_concurrent_calls": config.sip.max_concurrent_calls,
            "sip": {"host": config.sip.host, "port": config.sip.port},
            "i2c": {
                "mock": mock,
                "bus": config.i2c.bus,
                "address": config.i2c.address,
                "device_available": None if mock else device_path.exists(),
            },
            "arm": {
                "joint_count": len(config.arm.joints),
                "home_on_start": config.arm.home_on_start,
                "speed_deg_per_sec": config.arm.speed_deg_per_sec,
                "call_sequence_poses": len(config.arm.call_sequence),
                "call_action_running": bool(getattr(self.app, "call_action_running", False)),
            },
            "joints": [
                {
                    "name": joint.name,
                    "channel": joint.channel,
                    "min_angle": joint.min_angle,
                    "max_angle": joint.max_angle,
                    "current_angle": self.app.arm.current_angles[joint.name],
                    "target_angle": self.app.arm.target_angles[joint.name],
                    "home_angle": joint.home_angle,
                }
                for joint in config.arm.joints
            ],
        }

    def action_sequence(self) -> dict[str, Any]:
        config = load_config(self.config_path) if self.config_path is not None else self.app.config
        editable = (
            self.config_path is not None
            and os.access(self.config_path.parent, os.W_OK | os.X_OK)
        )
        return {
            "editable": editable,
            "message": None if editable else "The dashboard cannot write to the configuration directory.",
            "joints": [
                {
                    "name": joint.name,
                    "channel": joint.channel,
                    "min_angle": joint.min_angle,
                    "max_angle": joint.max_angle,
                    "home_angle": joint.home_angle,
                }
                for joint in config.arm.joints
            ],
            "poses": [
                {"angles": pose.angles, "hold_s": pose.hold_s}
                for pose in config.arm.call_sequence
            ],
        }

    def save_config(self, content: str) -> None:
        if len(content.encode("utf-8")) > _MAX_CONFIG_BYTES:
            raise ValueError("Configuration must be 64 KiB or smaller.")
        if self.config_path is None:
            raise ValueError("No configuration file was supplied to the server.")

        parent = self.config_path.parent
        temporary_path: str | None = None
        with self._config_lock:
            try:
                with tempfile.NamedTemporaryFile(
                    mode="w",
                    encoding="utf-8",
                    dir=parent,
                    prefix=".roboreka-config-",
                    suffix=".toml",
                    delete=False,
                ) as temporary:
                    temporary_path = temporary.name
                    temporary.write(content)
                    temporary.flush()
                    os.fsync(temporary.fileno())
                mode = (
                    stat.S_IMODE(self.config_path.stat().st_mode)
                    if self.config_path.exists()
                    else 0o640
                )
                os.chmod(temporary_path, mode)
                data = tomllib.loads(content)
                for section in ("sip", "i2c", "arm"):
                    if not isinstance(data.get(section, {}), dict):
                        raise ValueError(f"The [{section}] section must be a TOML table.")
                joints = data.get("arm", {}).get("joints")
                if joints is not None and (
                    not isinstance(joints, list)
                    or any(
                        not isinstance(joint, dict)
                        or "name" not in joint
                        or "channel" not in joint
                        for joint in joints
                    )
                ):
                    raise ValueError("arm.joints must be an array of tables with name and channel for each joint.")
                load_config(temporary_path)
                os.replace(temporary_path, self.config_path)
                temporary_path = None
            finally:
                if temporary_path is not None:
                    try:
                        os.unlink(temporary_path)
                    except FileNotFoundError:
                        pass
