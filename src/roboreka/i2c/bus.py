"""I2C bus protocol, Linux SMBus implementation, and in-memory mock bus."""

from __future__ import annotations

from typing import Any, Protocol, Sequence, runtime_checkable


@runtime_checkable
class I2CBus(Protocol):
    """Minimal I2C bus interface matching smbus2/smbus operations."""

    def write_byte_data(self, address: int, register: int, value: int) -> None:
        """Write a single byte to a device register."""

    def read_byte_data(self, address: int, register: int) -> int:
        """Read a single byte from a device register."""

    def write_i2c_block_data(self, address: int, register: int, data: Sequence[int]) -> None:
        """Write a sequence of bytes starting at a register."""

    def close(self) -> None:
        """Release the underlying I2C bus handle."""


class SMBusI2C:
    """Linux hardware I2C bus wrapper (defaults to /dev/i2c-0 on NanoPi NEO v1.4)."""

    def __init__(self, bus_number: int = 0) -> None:
        smbus_cls = self._import_smbus_cls()
        self.bus_number = int(bus_number)
        try:
            self._bus = smbus_cls(self.bus_number)
        except FileNotFoundError as exc:
            raise RuntimeError(
                f"I2C device /dev/i2c-{self.bus_number} not found. On NanoPi NEO v1.4 (Armbian), "
                f"enable the i2c0 overlay in /boot/armbianEnv.txt ('overlays=i2c0') and reboot, "
                f"or pass --mock to run without hardware."
            ) from exc
        except PermissionError as exc:
            raise RuntimeError(
                f"Permission denied opening /dev/i2c-{self.bus_number}. "
                f"Add your user to the 'i2c' group (sudo usermod -aG i2c $USER) or run with sudo."
            ) from exc

    @staticmethod
    def _import_smbus_cls() -> Any:
        try:
            from smbus2 import SMBus  # type: ignore[import-not-found]

            return SMBus
        except ImportError:
            try:
                from smbus import SMBus  # type: ignore[import-not-found]

                return SMBus
            except ImportError as exc:
                raise RuntimeError(
                    "Neither 'smbus2' nor 'smbus' is installed. On NanoPi NEO v1.4, install "
                    "'pip install \".[hardware]\"' or 'sudo apt install python3-smbus', "
                    "or pass --mock for software testing."
                ) from exc

    def write_byte_data(self, address: int, register: int, value: int) -> None:
        self._bus.write_byte_data(address, register, value & 0xFF)

    def read_byte_data(self, address: int, register: int) -> int:
        return int(self._bus.read_byte_data(address, register)) & 0xFF

    def write_i2c_block_data(self, address: int, register: int, data: Sequence[int]) -> None:
        self._bus.write_i2c_block_data(address, register, [b & 0xFF for b in data])

    def close(self) -> None:
        self._bus.close()


class MockI2CBus:
    """In-memory I2C bus that tracks register state and transaction history."""

    def __init__(self) -> None:
        self.registers: dict[tuple[int, int], int] = {}
        self.history: list[tuple[str, int, int, Any]] = []
        self.closed = False

    def write_byte_data(self, address: int, register: int, value: int) -> None:
        byte_val = value & 0xFF
        self.registers[(address, register)] = byte_val
        self.history.append(("write_byte", address, register, byte_val))

    def read_byte_data(self, address: int, register: int) -> int:
        val = self.registers.get((address, register), 0)
        self.history.append(("read_byte", address, register, val))
        return val

    def write_i2c_block_data(self, address: int, register: int, data: Sequence[int]) -> None:
        payload = [b & 0xFF for b in data]
        for offset, byte_val in enumerate(payload):
            self.registers[(address, (register + offset) & 0xFF)] = byte_val
        self.history.append(("write_block", address, register, payload))

    def close(self) -> None:
        self.closed = True
