"""Keyboard HID report writer for /dev/hidg1."""

import struct


class KeyboardHID:
    """Writes 8-byte keyboard HID reports.

    Report format: [modifier(1), reserved(1), keycode1(1), ..., keycode6(1)]
    This implementation only uses a single keycode slot.
    """

    _REPORT = struct.Struct("<8B")  # 8 bytes, all unsigned

    def __init__(self, device_path: str = "/dev/hidg1"):
        self._path = device_path
        self._fd = open(device_path, "wb", buffering=0)

    def write(self, modifier: int, keycode: int) -> None:
        """Send a keyboard report with one key pressed."""
        self._fd.write(
            self._REPORT.pack(
                modifier & 0xFF,
                0,  # reserved
                keycode & 0xFF,
                0,
                0,
                0,
                0,
                0,  # 5 empty keycode slots
            )
        )

    def release(self) -> None:
        """Send zero report (all keys released)."""
        self._fd.write(b"\x00" * 8)

    def close(self) -> None:
        self._fd.close()
