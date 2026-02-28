"""Bluetooth keyboard HID report sender."""

import struct

from .bt_hid_server import BT_INPUT_HEADER, BtHIDServer
from .config import REPORT_ID_KEYBOARD

_REPORT = struct.Struct("<8B")


class BtKeyboardHID:
    """
    Sends 8-byte keyboard HID reports over the Bluetooth interrupt channel.

    Report wire format: ``\\xa1 <report_id> <8-byte USB-format report>``

    Presents the same write / release / close interface as KeyboardHID so it
    can be swapped in wherever KeyboardHID is used.
    """

    def __init__(self, server: BtHIDServer) -> None:
        self._server = server

    def write(self, modifier: int, keycode: int) -> None:
        """Send a keyboard report with one key pressed."""
        report = _REPORT.pack(
            modifier & 0xFF,
            0,  # reserved
            keycode & 0xFF,
            0,
            0,
            0,
            0,
            0,  # 5 empty keycode slots
        )
        self._server.send_report(BT_INPUT_HEADER + bytes([REPORT_ID_KEYBOARD]) + report)

    def release(self) -> None:
        """Send zero report (all keys released)."""
        self._server.send_report(
            BT_INPUT_HEADER + bytes([REPORT_ID_KEYBOARD]) + b"\x00" * 8
        )

    def close(self) -> None:
        pass  # Connection lifecycle is owned by BtHIDServer
