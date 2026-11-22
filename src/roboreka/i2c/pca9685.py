"""PCA9685 16-channel 12-bit PWM servo controller driver over I2C."""

from __future__ import annotations

import time
from typing import Callable

from roboreka.i2c.bus import I2CBus


class PCA9685:
    """Driver for the NXP PCA9685 16-channel I2C PWM controller."""

    MODE1 = 0x00
    MODE2 = 0x01
    PRESCALE = 0xFE
    LED0_ON_L = 0x06
    ALL_LED_ON_L = 0xFA

    MODE1_RESTART = 0x80
    MODE1_AI = 0x20
    MODE1_SLEEP = 0x10
    MODE1_ALLCALL = 0x01
    MODE2_OUTDRV = 0x04
    FULL_OFF_BIT = 0x10

    OSC_CLOCK_HZ = 25_000_000

    def __init__(
        self,
        bus: I2CBus,
        address: int = 0x40,
        frequency_hz: float = 50.0,
        osc_clock_hz: int = OSC_CLOCK_HZ,
        sleep_fn: Callable[[float], None] = time.sleep,
    ) -> None:
        if not (0x03 <= address <= 0x77):
            raise ValueError(f"Invalid 7-bit I2C address: {address:#04x}")
        if not (24.0 <= frequency_hz <= 1526.0):
            raise ValueError(f"PCA9685 PWM frequency must be between 24 and 1526 Hz, got {frequency_hz}")

        self.bus = bus
        self.address = address
        self.frequency_hz = float(frequency_hz)
        self._osc_clock_hz = int(osc_clock_hz)
        self._sleep = sleep_fn

        self._initialize()

    def _initialize(self) -> None:
        self.bus.write_byte_data(self.address, self.MODE2, self.MODE2_OUTDRV)
        self.bus.write_byte_data(self.address, self.MODE1, self.MODE1_ALLCALL | self.MODE1_AI)
        self._sleep(0.005)
        self.set_pwm_frequency(self.frequency_hz)

    def set_pwm_frequency(self, frequency_hz: float) -> int:
        """Configure the global PWM frequency (24-1526 Hz) and return the prescale byte."""
        if not (24.0 <= frequency_hz <= 1526.0):
            raise ValueError(f"PCA9685 PWM frequency must be between 24 and 1526 Hz, got {frequency_hz}")

        prescale = max(3, min(255, round(self._osc_clock_hz / (4096.0 * frequency_hz)) - 1))
        old_mode = self.bus.read_byte_data(self.address, self.MODE1)
        sleep_mode = (old_mode & ~self.MODE1_RESTART) | self.MODE1_SLEEP
        self.bus.write_byte_data(self.address, self.MODE1, sleep_mode)
        self.bus.write_byte_data(self.address, self.PRESCALE, prescale)
        wake_mode = (old_mode & ~self.MODE1_SLEEP) | self.MODE1_AI
        self.bus.write_byte_data(self.address, self.MODE1, wake_mode)
        self._sleep(0.005)
        self.bus.write_byte_data(self.address, self.MODE1, wake_mode | self.MODE1_RESTART | self.MODE1_AI)
        self.frequency_hz = float(frequency_hz)
        return prescale

    @staticmethod
    def _validate_channel(channel: int) -> None:
        if not (0 <= channel <= 15):
            raise ValueError(f"PCA9685 channel must be 0..15, got {channel}")

    def set_pwm(self, channel: int, on: int, off: int) -> None:
        """Set 12-bit ON and OFF tick counts (0..4095) for a channel."""
        self._validate_channel(channel)
        if not (0 <= on <= 4095) or not (0 <= off <= 4095):
            raise ValueError(f"PWM tick counts must be 0..4095, got on={on}, off={off}")

        reg = self.LED0_ON_L + 4 * channel
        payload = [
            on & 0xFF,
            (on >> 8) & 0x0F,
            off & 0xFF,
            (off >> 8) & 0x0F,
        ]
        self.bus.write_i2c_block_data(self.address, reg, payload)

    def set_pulse_us(self, channel: int, pulse_us: float) -> int:
        """Set a servo pulse width in microseconds and return the written 12-bit OFF tick."""
        period_us = 1_000_000.0 / self.frequency_hz
        ticks = max(0, min(4095, round(pulse_us / period_us * 4096.0)))
        self.set_pwm(channel, 0, ticks)
        return ticks

    def set_channel_off(self, channel: int) -> None:
        """Disable PWM output on a single channel (sets FULL_OFF bit)."""
        self._validate_channel(channel)
        reg = self.LED0_ON_L + 4 * channel
        self.bus.write_i2c_block_data(self.address, reg, [0, 0, 0, self.FULL_OFF_BIT])

    def release_all(self) -> None:
        """Disable PWM output on all channels so servos relax."""
        self.bus.write_i2c_block_data(self.address, self.ALL_LED_ON_L, [0, 0, 0, self.FULL_OFF_BIT])

    def read_channel_pwm(self, channel: int) -> tuple[int, int]:
        """Read back the 12-bit (on, off) tick counts from device registers."""
        self._validate_channel(channel)
        reg = self.LED0_ON_L + 4 * channel
        on_l = self.bus.read_byte_data(self.address, reg)
        on_h = self.bus.read_byte_data(self.address, reg + 1)
        off_l = self.bus.read_byte_data(self.address, reg + 2)
        off_h = self.bus.read_byte_data(self.address, reg + 3)
        on = on_l | ((on_h & 0x0F) << 8)
        off = off_l | ((off_h & 0x0F) << 8)
        return on, off
