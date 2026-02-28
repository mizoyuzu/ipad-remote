"""Mouse HID report writer for /dev/hidg0."""

import struct


class MouseHID:
    """Writes 4-byte mouse HID reports.

    Report format: [buttons(1), dx(1), dy(1), wheel(1)]
    All delta values are signed int8.
    """

    _REPORT = struct.Struct("<Bbbb")  # 4 bytes

    def __init__(self, device_path: str = "/dev/hidg0"):
        self._path = device_path
        self._fd = open(device_path, "wb", buffering=0)

    def write(self, buttons: int, dx: int, dy: int, wheel: int) -> None:
        self._fd.write(self._REPORT.pack(buttons & 0x07, dx, dy, wheel))

    def release(self) -> None:
        """Send zero report (all buttons released, no movement)."""
        self.write(0, 0, 0, 0)

    def close(self) -> None:
        self._fd.close()
