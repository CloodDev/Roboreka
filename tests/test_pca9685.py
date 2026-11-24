"""Tests for PCA9685 I2C driver and NanoPi NEO v1.4 I2C0 configuration defaults."""

from __future__ import annotations

from pathlib import Path

import pytest

from roboreka.arm.controller import RobotArm
from roboreka.config import I2CConfig, load_config
from roboreka.i2c.bus import MockI2CBus
from roboreka.i2c.pca9685 import PCA9685


def test_nanopi_neo_i2c0_defaults() -> None:
    cfg = I2CConfig()
    assert cfg.bus == 0
    assert cfg.address == 0x40

    example = Path(__file__).resolve().parent.parent / "config.example.toml"
    loaded = load_config(example)
    assert loaded.i2c.bus == 0
    assert loaded.i2c.address == 0x40
    assert loaded.i2c.pwm_frequency_hz == 50.0


def test_configured_joint_channel_drives_selected_pca9685_output(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        '[arm]\nhome_on_start = false\n'
        '[[arm.joints]]\nname = "base"\nchannel = 7\n',
        encoding="utf-8",
    )
    config = load_config(config_path)
    bus = MockI2CBus()
    driver = PCA9685(bus, sleep_fn=lambda _: None)
    arm = RobotArm(driver, config.arm)
    arm.set_angle_immediate("base", 90.0)

    assert driver.read_channel_pwm(7) == (0, 307)
    assert (0x40, PCA9685.LED0_ON_L + 4 * 7) in bus.registers
    assert (0x40, PCA9685.LED0_ON_L) not in bus.registers


@pytest.mark.parametrize(
    ("channels", "error"),
    [
        ([16], "between 0 and 15"),
        ([3, 3], "Duplicate PCA9685 channel"),
    ],
)
def test_config_rejects_invalid_joint_channels(
    tmp_path: Path, channels: list[int], error: str
) -> None:
    config_path = tmp_path / "config.toml"
    joints = "".join(
        f'[[arm.joints]]\nname = "joint{index}"\nchannel = {channel}\n'
        for index, channel in enumerate(channels)
    )
    config_path.write_text(joints, encoding="utf-8")

    with pytest.raises(ValueError, match=error):
        load_config(config_path)


def test_config_loads_call_action_poses_and_validates_joint_limits(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        '[arm]\n'
        '[[arm.call_sequence]]\n'
        'angles = { base = 105.0 }\n'
        'hold_s = 0.5\n',
        encoding="utf-8",
    )
    config = load_config(config_path)
    assert len(config.arm.call_sequence) == 1
    assert config.arm.call_sequence[0].angles == {"base": 105.0}
    assert config.arm.call_sequence[0].hold_s == 0.5

    config_path.write_text(
        '[arm]\n'
        '[[arm.call_sequence]]\n'
        'angles = { base = 181.0 }\n',
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="between 0.0 and 180.0"):
        load_config(config_path)


def test_pca9685_init_sequence_and_prescale() -> None:
    bus = MockI2CBus()
    sleeps: list[float] = []
    driver = PCA9685(bus, address=0x40, frequency_hz=50.0, sleep_fn=sleeps.append)

    assert driver.frequency_hz == 50.0
    assert bus.registers[(0x40, PCA9685.MODE2)] == PCA9685.MODE2_OUTDRV
    assert bus.registers[(0x40, PCA9685.PRESCALE)] == 121
    assert bus.registers[(0x40, PCA9685.MODE1)] == (
        PCA9685.MODE1_ALLCALL | PCA9685.MODE1_AI | PCA9685.MODE1_RESTART
    )
    assert sleeps == [0.005, 0.005]

    # Verify SLEEP was enabled on MODE1 right before writing PRESCALE.
    write_regs = [(reg, val) for op, _, reg, val in bus.history if op == "write_byte"]
    prescale_idx = next(i for i, (reg, _) in enumerate(write_regs) if reg == PCA9685.PRESCALE)
    assert write_regs[prescale_idx - 1][0] == PCA9685.MODE1
    assert write_regs[prescale_idx - 1][1] & PCA9685.MODE1_SLEEP


def test_set_pulse_us_1500_writes_expected_ticks() -> None:
    bus = MockI2CBus()
    driver = PCA9685(bus, address=0x40, frequency_hz=50.0, sleep_fn=lambda _: None)

    ticks = driver.set_pulse_us(0, 1500.0)
    assert ticks == 307
    assert bus.registers[(0x40, PCA9685.LED0_ON_L + 0)] == 0x00
    assert bus.registers[(0x40, PCA9685.LED0_ON_L + 1)] == 0x00
    assert bus.registers[(0x40, PCA9685.LED0_ON_L + 2)] == 0x33
    assert bus.registers[(0x40, PCA9685.LED0_ON_L + 3)] == 0x01
    assert driver.read_channel_pwm(0) == (0, 307)


def test_channel_off_and_release_all() -> None:
    bus = MockI2CBus()
    driver = PCA9685(bus, address=0x40, frequency_hz=50.0, sleep_fn=lambda _: None)

    driver.set_channel_off(2)
    assert bus.registers[(0x40, PCA9685.LED0_ON_L + 4 * 2 + 3)] == PCA9685.FULL_OFF_BIT

    driver.release_all()
    assert bus.registers[(0x40, PCA9685.ALL_LED_ON_L + 3)] == PCA9685.FULL_OFF_BIT


def test_pca9685_validation_errors() -> None:
    bus = MockI2CBus()
    with pytest.raises(ValueError):
        PCA9685(bus, address=0x00, sleep_fn=lambda _: None)
    with pytest.raises(ValueError):
        PCA9685(bus, address=0x78, sleep_fn=lambda _: None)
    with pytest.raises(ValueError):
        PCA9685(bus, frequency_hz=10.0, sleep_fn=lambda _: None)

    driver = PCA9685(bus, sleep_fn=lambda _: None)
    with pytest.raises(ValueError):
        driver.set_pwm(-1, 0, 300)
    with pytest.raises(ValueError):
        driver.set_pwm(16, 0, 300)
    with pytest.raises(ValueError):
        driver.set_pwm(0, 0, 4096)
    with pytest.raises(ValueError):
        driver.set_pwm_frequency(2000.0)
