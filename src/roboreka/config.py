"""Configuration schema and TOML loader for Roboreka."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python < 3.11 fallback
    import tomli as tomllib  # type: ignore[no-redef]


@dataclass
class SIPConfig:
    """SIP/RTP networking and call limits."""

    host: str = "0.0.0.0"
    port: int = 5060
    advertise_ip: str = ""
    rtp_port_start: int = 10000
    rtp_port_end: int = 10100
    max_concurrent_calls: int = 1
    call_timeout_s: int = 120


@dataclass
class I2CConfig:
    """I2C bus and PCA9685 PWM settings (defaults to NanoPi NEO v1.4 /dev/i2c-0)."""

    bus: int = 0
    address: int = 0x40
    pwm_frequency_hz: float = 50.0
    mock: bool = False


@dataclass
class JointConfig:
    """Calibration and limits for a single servo joint."""

    name: str
    channel: int
    min_angle: float = 0.0
    max_angle: float = 180.0
    home_angle: float = 90.0
    min_pulse_us: float = 500.0
    max_pulse_us: float = 2500.0
    step_deg: float = 15.0
    inverted: bool = False


def default_joints() -> list[JointConfig]:
    """Return default 4-DOF robot arm joint configurations."""
    return [
        JointConfig(
            name="base",
            channel=0,
            min_angle=0.0,
            max_angle=180.0,
            home_angle=90.0,
            min_pulse_us=500.0,
            max_pulse_us=2500.0,
            step_deg=15.0,
        ),
        JointConfig(
            name="shoulder",
            channel=1,
            min_angle=15.0,
            max_angle=165.0,
            home_angle=90.0,
            min_pulse_us=500.0,
            max_pulse_us=2500.0,
            step_deg=15.0,
        ),
        JointConfig(
            name="elbow",
            channel=2,
            min_angle=15.0,
            max_angle=165.0,
            home_angle=90.0,
            min_pulse_us=500.0,
            max_pulse_us=2500.0,
            step_deg=15.0,
        ),
        JointConfig(
            name="gripper",
            channel=3,
            min_angle=10.0,
            max_angle=120.0,
            home_angle=60.0,
            min_pulse_us=500.0,
            max_pulse_us=2500.0,
            step_deg=15.0,
        ),
    ]


@dataclass
class ArmConfig:
    """Robot arm motion and safety behavior."""

    home_on_start: bool = True
    speed_deg_per_sec: float = 90.0
    release_on_shutdown: bool = True
    joints: list[JointConfig] = field(default_factory=default_joints)


@dataclass
class AppConfig:
    """Top-level application configuration."""

    sip: SIPConfig = field(default_factory=SIPConfig)
    i2c: I2CConfig = field(default_factory=I2CConfig)
    arm: ArmConfig = field(default_factory=ArmConfig)


def _parse_int(value: Any) -> int:
    if isinstance(value, str):
        return int(value, 0)
    return int(value)


def _parse_joint(raw: dict[str, Any]) -> JointConfig:
    return JointConfig(
        name=str(raw["name"]),
        channel=int(raw["channel"]),
        min_angle=float(raw.get("min_angle", 0.0)),
        max_angle=float(raw.get("max_angle", 180.0)),
        home_angle=float(raw.get("home_angle", 90.0)),
        min_pulse_us=float(raw.get("min_pulse_us", 500.0)),
        max_pulse_us=float(raw.get("max_pulse_us", 2500.0)),
        step_deg=float(raw.get("step_deg", 15.0)),
        inverted=bool(raw.get("inverted", False)),
    )


def load_config(path: str | Path | None = None) -> AppConfig:
    """Load configuration from a TOML file, or return defaults if path is None."""
    if path is None:
        return AppConfig()

    config_path = Path(path)
    with config_path.open("rb") as fh:
        data = tomllib.load(fh)

    sip_raw = data.get("sip", {})
    sip = SIPConfig(
        host=str(sip_raw.get("host", "0.0.0.0")),
        port=int(sip_raw.get("port", 5060)),
        advertise_ip=str(sip_raw.get("advertise_ip", "")),
        rtp_port_start=int(sip_raw.get("rtp_port_start", 10000)),
        rtp_port_end=int(sip_raw.get("rtp_port_end", 10100)),
        max_concurrent_calls=int(sip_raw.get("max_concurrent_calls", 1)),
        call_timeout_s=int(sip_raw.get("call_timeout_s", 120)),
    )

    i2c_raw = data.get("i2c", {})
    i2c = I2CConfig(
        bus=int(i2c_raw.get("bus", 0)),
        address=_parse_int(i2c_raw.get("address", 0x40)),
        pwm_frequency_hz=float(i2c_raw.get("pwm_frequency_hz", 50.0)),
        mock=bool(i2c_raw.get("mock", False)),
    )

    arm_raw = data.get("arm", {})
    joints_raw = arm_raw.get("joints")
    joints = [_parse_joint(j) for j in joints_raw] if joints_raw is not None else default_joints()
    arm = ArmConfig(
        home_on_start=bool(arm_raw.get("home_on_start", True)),
        speed_deg_per_sec=float(arm_raw.get("speed_deg_per_sec", 90.0)),
        release_on_shutdown=bool(arm_raw.get("release_on_shutdown", True)),
        joints=joints,
    )

    return AppConfig(sip=sip, i2c=i2c, arm=arm)
