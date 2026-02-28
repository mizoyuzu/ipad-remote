"""Tests for HIDDispatcher with mocked HID devices."""

import io
import struct
import unittest

from src.hid_dispatcher import HIDDispatcher
from src.hid_keyboard import KeyboardHID
from src.hid_mouse import MouseHID
from src.protocol import Packet


class MockMouseHID(MouseHID):
    """MouseHID with an in-memory buffer instead of a device file."""

    def __init__(self):
        self._path = "<mock>"
        self._fd = io.BytesIO()
        self.reports: list[bytes] = []

    def write(self, buttons: int, dx: int, dy: int, wheel: int) -> None:
        report = self._REPORT.pack(buttons & 0x07, dx, dy, wheel)
        self.reports.append(report)

    def close(self) -> None:
        pass


class MockKeyboardHID(KeyboardHID):
    """KeyboardHID with an in-memory buffer instead of a device file."""

    def __init__(self):
        self._path = "<mock>"
        self._fd = io.BytesIO()
        self.reports: list[bytes] = []

    def write(self, modifier: int, keycode: int) -> None:
        report = self._REPORT.pack(modifier & 0xFF, 0, keycode & 0xFF, 0, 0, 0, 0, 0)
        self.reports.append(report)

    def release(self) -> None:
        self.reports.append(b"\x00" * 8)

    def close(self) -> None:
        pass


class TestHIDDispatcher(unittest.TestCase):
    def setUp(self):
        self.mouse = MockMouseHID()
        self.keyboard = MockKeyboardHID()
        self.dispatcher = HIDDispatcher(self.mouse, self.keyboard)

    def test_trackpad_move(self):
        self.dispatcher.dispatch(Packet(0, 0, 10, -5, 0, 0))
        self.assertEqual(len(self.mouse.reports), 1)
        buttons, dx, dy, wheel = struct.unpack("<Bbbb", self.mouse.reports[0])
        self.assertEqual(dx, 10)
        self.assertEqual(dy, -5)
        self.assertEqual(buttons, 0)

    def test_trackpad_left_click(self):
        self.dispatcher.dispatch(Packet(0, 0x01, 0, 0, 0, 0))
        buttons, _, _, _ = struct.unpack("<Bbbb", self.mouse.reports[0])
        self.assertEqual(buttons, 1)

    def test_trackpad_right_click(self):
        self.dispatcher.dispatch(Packet(0, 0x02, 0, 0, 0, 0))
        buttons, _, _, _ = struct.unpack("<Bbbb", self.mouse.reports[0])
        self.assertEqual(buttons, 2)

    def test_trackpad_scroll(self):
        self.dispatcher.dispatch(Packet(0, 0, 0, 0, -3, 0))
        _, _, _, wheel = struct.unpack("<Bbbb", self.mouse.reports[0])
        self.assertEqual(wheel, -3)

    def test_scroll_mode(self):
        self.dispatcher.dispatch(Packet(1, 0, 0, 0, 5, 0))
        buttons, dx, dy, wheel = struct.unpack("<Bbbb", self.mouse.reports[0])
        self.assertEqual(wheel, 5)
        self.assertEqual(buttons, 0)
        self.assertEqual(dx, 0)
        self.assertEqual(dy, 0)

    def test_arrow_key_press_and_release(self):
        # Press up arrow
        self.dispatcher.dispatch(Packet(2, 0, 0, 0, 0, 0x52))
        self.assertEqual(len(self.keyboard.reports), 1)
        report = self.keyboard.reports[0]
        self.assertEqual(report[0], 0)    # no modifier
        self.assertEqual(report[2], 0x52) # up arrow keycode

        # Release
        self.dispatcher.dispatch(Packet(2, 0, 0, 0, 0, 0))
        self.assertEqual(len(self.keyboard.reports), 2)
        self.assertEqual(self.keyboard.reports[1], b"\x00" * 8)

    def test_cmd_h_shortcut_from_trackpad(self):
        # Send Cmd+H
        self.dispatcher.dispatch(Packet(0, 0x08, 0, 0, 0, 0x0B))
        # Should have mouse report + keyboard report
        self.assertEqual(len(self.mouse.reports), 1)
        self.assertEqual(len(self.keyboard.reports), 1)
        # Check keyboard: modifier=0x08 (GUI), keycode=0x0B (H)
        report = self.keyboard.reports[0]
        self.assertEqual(report[0], 0x08)
        self.assertEqual(report[2], 0x0B)

        # Release
        self.dispatcher.dispatch(Packet(0, 0, 0, 0, 0, 0))
        self.assertEqual(len(self.keyboard.reports), 2)
        self.assertEqual(self.keyboard.reports[1], b"\x00" * 8)

    def test_no_spurious_release(self):
        # Normal trackpad move should not send keyboard release
        self.dispatcher.dispatch(Packet(0, 0, 5, 5, 0, 0))
        self.dispatcher.dispatch(Packet(0, 0, 3, 3, 0, 0))
        self.assertEqual(len(self.keyboard.reports), 0)

    def test_release_all(self):
        self.dispatcher.release_all()
        self.assertEqual(len(self.mouse.reports), 1)
        self.assertEqual(len(self.keyboard.reports), 1)
        # Mouse should be zero report
        self.assertEqual(self.mouse.reports[0], struct.pack("<Bbbb", 0, 0, 0, 0))
        # Keyboard should be zero report
        self.assertEqual(self.keyboard.reports[0], b"\x00" * 8)


if __name__ == "__main__":
    unittest.main()
