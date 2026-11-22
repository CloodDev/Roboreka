"""Main Roboreka server wiring SIP/RTP DTMF inputs to the PCA9685 I2C robot arm."""

from __future__ import annotations

import logging
from typing import Callable

from roboreka.arm.controller import RobotArm
from roboreka.config import AppConfig
from roboreka.i2c.bus import I2CBus, MockI2CBus, SMBusI2C
from roboreka.i2c.pca9685 import PCA9685
from roboreka.voip.sip import SIPCall, SIPServer
from roboreka.voip.tones import (
    ack_beep,
    error_beep,
    home_chime,
    limit_buzz,
    stop_chime,
    welcome_chime,
)

logger = logging.getLogger(__name__)


class RoborekaServer:
    """Bridges VoIP DTMF commands to PCA9685 I2C robot arm motions with audio feedback."""

    # (joint_name, step_multiplier): positive turns right / up / open
    DTMF_NUDGE_MAP: dict[str, tuple[str, float]] = {
        "4": ("base", -1.0),
        "6": ("base", 1.0),
        "1": ("base", -3.0),
        "3": ("base", 3.0),
        "2": ("shoulder", 1.0),
        "8": ("shoulder", -1.0),
        "7": ("elbow", -1.0),
        "9": ("elbow", 1.0),
        "*": ("gripper", -1.0),
        "#": ("gripper", 1.0),
    }

    def __init__(
        self,
        config: AppConfig,
        bus: I2CBus | None = None,
        on_arm_update: Callable[[str, dict[str, float]], None] | None = None,
    ) -> None:
        self.config = config
        self.on_arm_update = on_arm_update

        if bus is not None:
            self.bus: I2CBus = bus
        elif config.i2c.mock:
            self.bus = MockI2CBus()
        else:
            self.bus = SMBusI2C(bus_number=config.i2c.bus)

        self.pca9685 = PCA9685(
            bus=self.bus,
            address=config.i2c.address,
            frequency_hz=config.i2c.pwm_frequency_hz,
        )
        self.arm = RobotArm(driver=self.pca9685, config=config.arm)
        self.sip_server = SIPServer(
            config=config.sip,
            on_call_started=self._on_call_started,
            on_call_ended=self._on_call_ended,
            on_dtmf=self.handle_dtmf,
        )
        self._started = False

    async def start(self) -> int:
        """Initialize arm home position (if enabled) and start the SIP UDP server."""
        if self.config.arm.home_on_start:
            self.arm.home_all_immediate()
            logger.info("Homed robot arm joints: %s", self.arm.get_state())

        sip_port = await self.sip_server.start()
        self._started = True
        mode = "mock I2C" if isinstance(self.bus, MockI2CBus) else f"/dev/i2c-{self.config.i2c.bus}"
        logger.info(
            "Roboreka SIP server listening on %s:%d (advertise=%s, i2c=%s @ %#04x)",
            self.config.sip.host,
            sip_port,
            self.sip_server.advertise_ip,
            mode,
            self.config.i2c.address,
        )
        return sip_port

    async def stop(self) -> None:
        """Stop active SIP/RTP sessions, optionally release servos, and close I2C."""
        if not self._started:
            return
        self._started = False
        await self.sip_server.stop()
        if self.config.arm.release_on_shutdown:
            self.arm.release()
        else:
            self.arm.stop()
        self.bus.close()
        logger.info("Roboreka server stopped cleanly")

    def _on_call_started(self, call: SIPCall) -> None:
        logger.info("Call started: id=%s from=%s", call.call_id, call.from_header)
        call.rtp_session.enqueue_audio(welcome_chime())

    def _on_call_ended(self, call: SIPCall) -> None:
        logger.info("Call ended: id=%s", call.call_id)

    def handle_dtmf(self, call: SIPCall, digit: str, source: str) -> None:
        """Translate a DTMF digit into an I2C servo motion and audio feedback cue."""
        key = digit.upper()
        logger.info("DTMF %r (%s) on call %s", key, source, call.call_id)

        if key == "5":
            self.arm.schedule_home_all()
            call.rtp_session.enqueue_audio(home_chime())
            logger.info("Arm homing all joints -> %s", self.arm.target_angles)
            if self.on_arm_update is not None:
                self.on_arm_update(key, dict(self.arm.target_angles))
            return

        if key == "0":
            self.arm.release()
            call.rtp_session.enqueue_audio(stop_chime())
            logger.warning("Emergency stop / servo release triggered via DTMF '0'")
            if self.on_arm_update is not None:
                self.on_arm_update(key, self.arm.get_state())
            return

        mapping = self.DTMF_NUDGE_MAP.get(key)
        if mapping is None:
            call.rtp_session.enqueue_audio(error_beep())
            logger.debug("Unmapped DTMF digit %r", key)
            return

        joint_name, multiplier = mapping
        joint = self.arm.joints.get(joint_name)
        if joint is None:
            call.rtp_session.enqueue_audio(error_beep())
            logger.warning("DTMF %r mapped to unconfigured joint %r", key, joint_name)
            return

        delta = multiplier * joint.step_deg
        target_angle, hit_limit = self.arm.schedule_nudge(joint_name, delta)
        span = joint.max_angle - joint.min_angle
        ratio = 0.5 if span <= 0 else (target_angle - joint.min_angle) / span

        if hit_limit:
            call.rtp_session.enqueue_audio(limit_buzz())
        else:
            call.rtp_session.enqueue_audio(ack_beep(ratio))

        logger.info(
            "Turned joint=%s (ch=%d) delta=%+.1f -> target=%.1f deg (limit=%s)",
            joint_name,
            joint.channel,
            delta,
            target_angle,
            hit_limit,
        )
        if self.on_arm_update is not None:
            self.on_arm_update(key, dict(self.arm.target_angles))
