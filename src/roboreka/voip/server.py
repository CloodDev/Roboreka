"""Main Roboreka server wiring SIP/RTP DTMF inputs to the PCA9685 I2C robot arm."""

from __future__ import annotations

import asyncio
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
        self._call_action_tasks: dict[str, asyncio.Task[None]] = {}
        self.loop: asyncio.AbstractEventLoop | None = None
        self._started = False

    async def start(self) -> int:
        """Initialize arm home position (if enabled) and start the SIP UDP server."""
        self.loop = asyncio.get_running_loop()
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
        if self._call_action_tasks:
            await asyncio.gather(*self._call_action_tasks.values())
        if self.config.arm.release_on_shutdown:
            self.arm.release()
        else:
            self.arm.stop()
        self.bus.close()
        self.loop = None
        logger.info("Roboreka server stopped cleanly")

    @property
    def call_action_running(self) -> bool:
        return any(not task.done() for task in self._call_action_tasks.values())

    @property
    def event_loop(self) -> asyncio.AbstractEventLoop:
        if self.loop is None or self.loop.is_closed():
            raise RuntimeError("Roboreka arm controller is not running")
        return self.loop

    async def stop_arm(self, release: bool = False) -> None:
        """Stop automatic call actions and arm movement, optionally releasing servos."""
        tasks = list(self._call_action_tasks.values())
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        if release:
            self.arm.release()
        else:
            self.arm.stop()

    def _on_call_started(self, call: SIPCall) -> None:
        logger.info("Call started: id=%s from=%s", call.call_id, call.from_header)
        call.rtp_session.enqueue_audio(welcome_chime())
        if self.config.arm.call_sequence:
            task = asyncio.create_task(self._run_call_sequence(call))
            self._call_action_tasks[call.call_id] = task
            task.add_done_callback(lambda completed: self._on_call_sequence_done(call.call_id, completed))

    def _on_call_ended(self, call: SIPCall) -> None:
        logger.info("Call ended: id=%s", call.call_id)

    async def _run_call_sequence(self, call: SIPCall) -> None:
        for index, pose in enumerate(self.config.arm.call_sequence, start=1):
            logger.info(
                "Call action pose %d/%d for call %s: %s",
                index,
                len(self.config.arm.call_sequence),
                call.call_id,
                pose.angles,
            )
            await self.arm.move_to_pose(pose.angles)
            current_task = asyncio.current_task()
            if current_task is not None and current_task.cancelling():
                raise asyncio.CancelledError
            if pose.hold_s > 0:
                await asyncio.sleep(pose.hold_s)

        logger.info("Call action complete for call %s; returning all joints home", call.call_id)
        await self.arm.home_all()

    def _on_call_sequence_done(self, call_id: str, task: asyncio.Task[None]) -> None:
        self._call_action_tasks.pop(call_id, None)
        if task.cancelled():
            logger.warning("Call action cancelled for call %s", call_id)
            return
        error = task.exception()
        if error is not None:
            logger.error(
                "Call action failed for call %s",
                call_id,
                exc_info=(type(error), error, error.__traceback__),
            )

    def handle_dtmf(self, call: SIPCall, digit: str, source: str) -> None:
        """Translate a DTMF digit into an I2C servo motion and audio feedback cue."""
        key = digit.upper()
        logger.info("DTMF %r (%s) on call %s", key, source, call.call_id)

        action_task = self._call_action_tasks.get(call.call_id)
        if action_task is not None and not action_task.done():
            call.rtp_session.enqueue_audio(error_beep())
            logger.info("Ignoring DTMF %r while automatic call action is running", key)
            return

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
