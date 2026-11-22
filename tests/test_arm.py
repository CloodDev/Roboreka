"""Tests for the RobotArm joint controller and PCA9685 PWM mapping."""

from __future__ import annotations

import asyncio

import pytest

from roboreka.arm.controller import RobotArm
from roboreka.config import ArmConfig, JointConfig
from roboreka.i2c.bus import MockI2CBus
from roboreka.i2c.pca9685 import PCA9685


def _make_arm(speed_deg_per_sec: float = 1000.0) -> tuple[MockI2CBus, PCA9685, RobotArm]:
    bus = MockI2CBus()
    driver = PCA9685(bus, sleep_fn=lambda _: None)
    arm = RobotArm(driver, ArmConfig(speed_deg_per_sec=speed_deg_per_sec))
    return bus, driver, arm


def test_home_all_immediate_sets_base_90_deg() -> None:
    _, driver, arm = _make_arm()
    state = arm.home_all_immediate()
    assert state["base"] == 90.0
    assert driver.read_channel_pwm(0) == (0, 307)


async def test_nudge_turns_base_and_updates_pca9685() -> None:
    _, driver, arm = _make_arm(speed_deg_per_sec=1000.0)
    arm.home_all_immediate()

    angle, hit_limit = await arm.nudge("base", 15.0)
    assert angle == pytest.approx(105.0)
    assert not hit_limit
    assert arm.get_state()["base"] == pytest.approx(105.0)
    # 105/180 * 2000 + 500 = 1666.67 us -> round(1666.6667 / 20000 * 4096) = 341
    assert driver.read_channel_pwm(0) == (0, 341)

    angle, hit_limit = await arm.nudge("base", -15.0)
    assert angle == pytest.approx(90.0)
    assert not hit_limit
    assert driver.read_channel_pwm(0) == (0, 307)


async def test_angle_clamping_reports_limit() -> None:
    _, _, arm = _make_arm(speed_deg_per_sec=2000.0)
    arm.home_all_immediate()

    high, hit_high = await arm.move_to("base", 225.0)
    assert high == 180.0
    assert hit_high

    low, hit_low = await arm.move_to("base", -15.0)
    assert low == 0.0
    assert hit_low


async def test_rapid_consecutive_nudges_accumulate_cleanly() -> None:
    _, _, arm = _make_arm(speed_deg_per_sec=90.0)
    arm.home_all_immediate()

    t1 = asyncio.create_task(arm.nudge("base", 15.0))
    await asyncio.sleep(0.03)
    t2 = asyncio.create_task(arm.nudge("base", 15.0))
    await asyncio.sleep(0.03)
    t3 = asyncio.create_task(arm.nudge("base", 15.0))
    await asyncio.gather(t1, t2, t3)

    assert arm.get_state()["base"] == pytest.approx(135.0)


def test_inverted_joint_mapping_reverses_pulse() -> None:
    joint = JointConfig(
        name="base",
        channel=0,
        min_angle=0.0,
        max_angle=180.0,
        home_angle=90.0,
        min_pulse_us=500.0,
        max_pulse_us=2500.0,
        inverted=True,
    )
    assert RobotArm.angle_to_pulse_us(joint, 0.0) == pytest.approx(2500.0)
    assert RobotArm.angle_to_pulse_us(joint, 90.0) == pytest.approx(1500.0)
    assert RobotArm.angle_to_pulse_us(joint, 180.0) == pytest.approx(500.0)


def test_release_disables_all_pca9685_channels() -> None:
    bus, _, arm = _make_arm()
    arm.home_all_immediate()
    arm.release()
    assert bus.registers[(0x40, PCA9685.ALL_LED_ON_L + 3)] == PCA9685.FULL_OFF_BIT
