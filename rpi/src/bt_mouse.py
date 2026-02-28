"""Bluetooth mouse HID report sender."""

import struct

from .bt_hid_server import BT_INPUT_HEADER, BtHIDServer
from .config import REPORT_ID_MOUSE

_REPORT = struct.Struct("<Bbbb")  # buttons(u8), dx, dy, wheel (signed int8)


class BtMouseHID:
    """
    Sends 4-byte mouse HID reports over the Bluetooth interrupt channel.

    Report wire format: ``\\xa1 <report_id> <4-byte USB-format report>``

    Presents the same write / release / close interface as MouseHID so it
    can be swapped in wherever MouseHID is used.
    """

    def __init__(self, server: BtHIDServer) -> None:
        self._server = server

    def write(self, buttons: int, dx: int, dy: int, wheel: int) -> None:
        report = _REPORT.pack(buttons & 0x07, dx, dy, wheel)
        self._server.send_report(BT_INPUT_HEADER + bytes([REPORT_ID_MOUSE]) + report)

    def release(self) -> None:
        """Send zero report (all buttons released, no movement)."""
        self.write(0, 0, 0, 0)

    def close(self) -> None:
        pass  # Connection lifecycle is owned by BtHIDServer
