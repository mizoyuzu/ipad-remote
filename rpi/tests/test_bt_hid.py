"""Tests for Bluetooth HID senders (BtMouseHID, BtKeyboardHID) and FanoutHID."""

import struct
import unittest

from src.bt_keyboard import BtKeyboardHID
from src.bt_mouse import BtMouseHID
from src.config import REPORT_ID_KEYBOARD, REPORT_ID_MOUSE
from src.hid_fanout import FanoutKeyboardHID, FanoutMouseHID

_HID_INPUT = 0xA1


class MockBtHIDServer:
    """BtHIDServer stub that captures sent data."""

    def __init__(self):
        self.reports: list[bytes] = []

    def send_report(self, data: bytes) -> None:
        self.reports.append(data)

    def is_connected(self) -> bool:
        return True

    def close(self) -> None:
        pass


# ---------------------------------------------------------------------------
# BtMouseHID
# ---------------------------------------------------------------------------


class TestBtMouseHID(unittest.TestCase):
    def setUp(self):
        self.server = MockBtHIDServer()
        self.mouse = BtMouseHID(self.server)

    def test_write_sends_hid_input_header(self):
        self.mouse.write(0, 0, 0, 0)
        self.assertEqual(self.server.reports[0][0], _HID_INPUT)

    def test_write_sends_correct_report_id(self):
        self.mouse.write(0, 0, 0, 0)
        self.assertEqual(self.server.reports[0][1], REPORT_ID_MOUSE)

    def test_write_report_content(self):
        self.mouse.write(1, 10, -5, 3)
        payload = self.server.reports[0][2:]
        buttons, dx, dy, wheel = struct.unpack("<Bbbb", payload)
        self.assertEqual(buttons, 1)
        self.assertEqual(dx, 10)
        self.assertEqual(dy, -5)
        self.assertEqual(wheel, 3)

    def test_release_sends_zero_report(self):
        self.mouse.release()
        payload = self.server.reports[0][2:]
        self.assertEqual(payload, struct.pack("<Bbbb", 0, 0, 0, 0))

    def test_buttons_masked_to_3_bits(self):
        self.mouse.write(0xFF, 0, 0, 0)
        buttons, *_ = struct.unpack("<Bbbb", self.server.reports[0][2:])
        self.assertEqual(buttons, 0x07)

    def test_close_does_not_raise(self):
        self.mouse.close()  # should be a no-op


# ---------------------------------------------------------------------------
# BtKeyboardHID
# ---------------------------------------------------------------------------


class TestBtKeyboardHID(unittest.TestCase):
    def setUp(self):
        self.server = MockBtHIDServer()
        self.keyboard = BtKeyboardHID(self.server)

    def test_write_sends_hid_input_header(self):
        self.keyboard.write(0, 0x28)
        self.assertEqual(self.server.reports[0][0], _HID_INPUT)

    def test_write_sends_correct_report_id(self):
        self.keyboard.write(0, 0x28)
        self.assertEqual(self.server.reports[0][1], REPORT_ID_KEYBOARD)

    def test_write_modifier_and_keycode(self):
        self.keyboard.write(0x08, 0x0B)  # Cmd+H
        payload = self.server.reports[0][2:]
        modifier, reserved, keycode = struct.unpack_from("BBB", payload)
        self.assertEqual(modifier, 0x08)
        self.assertEqual(reserved, 0)
        self.assertEqual(keycode, 0x0B)

    def test_write_report_is_8_bytes(self):
        self.keyboard.write(0, 0x28)
        self.assertEqual(len(self.server.reports[0][2:]), 8)

    def test_release_sends_zero_report(self):
        self.keyboard.release()
        payload = self.server.reports[0][2:]
        self.assertEqual(payload, b"\x00" * 8)

    def test_modifier_masked_to_byte(self):
        self.keyboard.write(0x1FF, 0x28)
        modifier = self.server.reports[0][2]
        self.assertEqual(modifier, 0xFF)

    def test_close_does_not_raise(self):
        self.keyboard.close()  # should be a no-op


# ---------------------------------------------------------------------------
# FanoutMouseHID / FanoutKeyboardHID
# ---------------------------------------------------------------------------


class TestFanoutMouseHID(unittest.TestCase):
    def setUp(self):
        self.s1 = MockBtHIDServer()
        self.s2 = MockBtHIDServer()
        self.m1 = BtMouseHID(self.s1)
        self.m2 = BtMouseHID(self.s2)
        self.fanout = FanoutMouseHID(self.m1, self.m2)

    def test_write_reaches_both_backends(self):
        self.fanout.write(0, 5, -3, 0)
        self.assertEqual(len(self.s1.reports), 1)
        self.assertEqual(len(self.s2.reports), 1)
        self.assertEqual(self.s1.reports[0], self.s2.reports[0])

    def test_release_reaches_both_backends(self):
        self.fanout.release()
        self.assertEqual(len(self.s1.reports), 1)
        self.assertEqual(len(self.s2.reports), 1)

    def test_close_reaches_both_backends(self):
        self.fanout.close()  # BtMouseHID.close() is no-op, just must not raise


class TestFanoutKeyboardHID(unittest.TestCase):
    def setUp(self):
        self.s1 = MockBtHIDServer()
        self.s2 = MockBtHIDServer()
        self.k1 = BtKeyboardHID(self.s1)
        self.k2 = BtKeyboardHID(self.s2)
        self.fanout = FanoutKeyboardHID(self.k1, self.k2)

    def test_write_reaches_both_backends(self):
        self.fanout.write(0x08, 0x0B)
        self.assertEqual(len(self.s1.reports), 1)
        self.assertEqual(len(self.s2.reports), 1)
        self.assertEqual(self.s1.reports[0], self.s2.reports[0])

    def test_release_reaches_both_backends(self):
        self.fanout.release()
        self.assertEqual(len(self.s1.reports), 1)
        self.assertEqual(len(self.s2.reports), 1)


if __name__ == "__main__":
    unittest.main()
