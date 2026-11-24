"""Multi-joint robot arm controller driving a PCA9685 over I2C."""

from __future__ import annotations

import asyncio
import math

from roboreka.config import ArmConfig, JointConfig
from roboreka.i2c.pca9685 import PCA9685


class RobotArm:
    """High-level kinematics/angle controller for a multi-DOF servo arm."""

    RAMP_HZ = 50.0

    def __init__(self, driver: PCA9685, config: ArmConfig | None = None) -> None:
        self.driver = driver
        self.config = config or ArmConfig()
        self.joints: dict[str, JointConfig] = {}
        seen_channels: set[int] = set()
        for joint in self.config.joints:
            if joint.name in self.joints:
                raise ValueError(f"Duplicate joint name: {joint.name}")
            if joint.channel in seen_channels:
                raise ValueError(f"Duplicate PCA9685 channel: {joint.channel}")
            self.joints[joint.name] = joint
            seen_channels.add(joint.channel)

        self.current_angles: dict[str, float] = {
            name: self._clamp(joint, joint.home_angle)[0]
            for name, joint in self.joints.items()
        }
        self.target_angles: dict[str, float] = dict(self.current_angles)
        self._generations: dict[str, int] = {name: 0 for name in self.joints}
        self._tasks: dict[str, asyncio.Task[tuple[float, bool]]] = {}

    @staticmethod
    def _clamp(joint: JointConfig, angle: float) -> tuple[float, bool]:
        val = float(angle)
        clamped = max(joint.min_angle, min(joint.max_angle, val))
        hit_limit = not math.isclose(clamped, val, abs_tol=1e-6)
        return clamped, hit_limit

    @classmethod
    def angle_to_pulse_us(cls, joint: JointConfig, angle: float) -> float:
        """Convert a joint angle in degrees to a clamped servo pulse width in microseconds."""
        clamped, _ = cls._clamp(joint, angle)
        span = joint.max_angle - joint.min_angle
        ratio = 0.5 if span <= 0.0 else (clamped - joint.min_angle) / span
        if joint.inverted:
            ratio = 1.0 - ratio
        return joint.min_pulse_us + ratio * (joint.max_pulse_us - joint.min_pulse_us)

    def _get_joint(self, joint_name: str) -> JointConfig:
        if joint_name not in self.joints:
            raise KeyError(f"Unknown joint: {joint_name}")
        return self.joints[joint_name]

    def set_angle_immediate(self, joint_name: str, angle: float) -> tuple[float, bool]:
        """Write a joint angle immediately to the PCA9685 without ramping."""
        joint = self._get_joint(joint_name)
        clamped, hit_limit = self._clamp(joint, angle)
        pulse_us = self.angle_to_pulse_us(joint, clamped)
        self.driver.set_pulse_us(joint.channel, pulse_us)
        self.current_angles[joint_name] = clamped
        return clamped, hit_limit

    def home_all_immediate(self) -> dict[str, float]:
        """Synchronously move all joints to their configured home angles."""
        for name, joint in self.joints.items():
            self._generations[name] += 1
            clamped, _ = self.set_angle_immediate(name, joint.home_angle)
            self.target_angles[name] = clamped
        return self.get_state()

    def _prepare_target(self, joint_name: str, angle: float) -> tuple[float, bool, int]:
        joint = self._get_joint(joint_name)
        clamped, hit_limit = self._clamp(joint, angle)
        self._generations[joint_name] += 1
        self.target_angles[joint_name] = clamped
        return clamped, hit_limit, self._generations[joint_name]

    async def _ramp_to(
        self,
        joint_name: str,
        clamped_target: float,
        hit_limit: bool,
        generation: int,
        speed_deg_per_sec: float | None = None,
    ) -> tuple[float, bool]:
        speed = self.config.speed_deg_per_sec if speed_deg_per_sec is None else float(speed_deg_per_sec)
        start = self.current_angles[joint_name]
        delta = clamped_target - start

        if speed <= 0.0 or math.isclose(delta, 0.0, abs_tol=1e-4):
            self.set_angle_immediate(joint_name, clamped_target)
            return clamped_target, hit_limit

        dt = 1.0 / self.RAMP_HZ
        steps = max(1, math.ceil(abs(delta) / (speed * dt)))
        try:
            for step in range(1, steps + 1):
                if self._generations[joint_name] != generation:
                    return self.target_angles[joint_name], hit_limit
                fraction = step / steps
                self.set_angle_immediate(joint_name, start + delta * fraction)
                if step < steps:
                    await asyncio.sleep(dt)
        except asyncio.CancelledError:
            return self.current_angles[joint_name], hit_limit

        return clamped_target, hit_limit

    async def move_to(
        self,
        joint_name: str,
        target_angle: float,
        speed_deg_per_sec: float | None = None,
    ) -> tuple[float, bool]:
        """Smoothly ramp a joint to target_angle and return (clamped_angle, hit_limit)."""
        clamped, hit_limit, gen = self._prepare_target(joint_name, target_angle)
        return await self._ramp_to(joint_name, clamped, hit_limit, gen, speed_deg_per_sec)

    async def nudge(
        self,
        joint_name: str,
        delta_deg: float,
        speed_deg_per_sec: float | None = None,
    ) -> tuple[float, bool]:
        """Nudge a joint relative to its current target_angle so rapid presses accumulate."""
        self._get_joint(joint_name)
        new_raw = self.target_angles[joint_name] + float(delta_deg)
        clamped, hit_limit, gen = self._prepare_target(joint_name, new_raw)
        return await self._ramp_to(joint_name, clamped, hit_limit, gen, speed_deg_per_sec)

    def schedule_nudge(
        self,
        joint_name: str,
        delta_deg: float,
        speed_deg_per_sec: float | None = None,
    ) -> tuple[float, bool]:
        """Compute new target synchronously and launch background smooth ramp."""
        self._get_joint(joint_name)
        new_raw = self.target_angles[joint_name] + float(delta_deg)
        clamped, hit_limit, gen = self._prepare_target(joint_name, new_raw)
        task = asyncio.create_task(
            self._ramp_to(joint_name, clamped, hit_limit, gen, speed_deg_per_sec)
        )
        self._tasks[joint_name] = task
        return clamped, hit_limit

    def schedule_move_to(
        self,
        joint_name: str,
        target_angle: float,
        speed_deg_per_sec: float | None = None,
    ) -> tuple[float, bool]:
        """Schedule a smooth move to an absolute joint angle."""
        self._get_joint(joint_name)
        clamped, hit_limit, generation = self._prepare_target(joint_name, target_angle)
        self._tasks[joint_name] = asyncio.create_task(
            self._ramp_to(joint_name, clamped, hit_limit, generation, speed_deg_per_sec)
        )
        return clamped, hit_limit

    def schedule_home_all(self) -> None:
        """Schedule smooth homing on all joints in the background."""
        for name, joint in self.joints.items():
            clamped, hit_limit, gen = self._prepare_target(name, joint.home_angle)
            self._tasks[name] = asyncio.create_task(
                self._ramp_to(name, clamped, hit_limit, gen)
            )

    async def home_all(self) -> dict[str, float]:
        """Smoothly move all joints to their configured home angles concurrently."""
        await asyncio.gather(
            *(self.move_to(name, joint.home_angle) for name, joint in self.joints.items())
        )
        return self.get_state()

    async def move_to_pose(self, angles: dict[str, float]) -> dict[str, float]:
        """Smoothly move the configured joints in a pose concurrently."""
        await asyncio.gather(*(self.move_to(name, angle) for name, angle in angles.items()))
        return self.get_state()

    def stop(self) -> None:
        """Abort any active joint ramps and lock targets to current angles."""
        for name in self.joints:
            self._generations[name] += 1
            self.target_angles[name] = self.current_angles[name]
            task = self._tasks.pop(name, None)
            if task is not None and not task.done():
                task.cancel()

    def release(self) -> None:
        """Stop all ramps and release PWM output on all PCA9685 channels."""
        self.stop()
        self.driver.release_all()

    def get_state(self) -> dict[str, float]:
        """Return a snapshot mapping joint names to current angles in degrees."""
        return dict(self.current_angles)
