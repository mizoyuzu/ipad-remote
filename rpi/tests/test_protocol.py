"""Tests for protocol parsing and building."""

import struct
import unittest

from src.protocol import Packet, build_packet, parse_packet


class TestParsePacket(unittest.TestCase):
    def test_trackpad_move(self):
        data = build_packet(0, 0, 10, -20, 0, 0)
        pkt = parse_packet(data)
        self.assertIsNotNone(pkt)
        self.assertEqual(pkt.mode, 0)
        self.assertEqual(pkt.flags, 0)
        self.assertEqual(pkt.dx, 10)
        self.assertEqual(pkt.dy, -20)
        self.assertEqual(pkt.wheel, 0)
        self.assertEqual(pkt.keycode, 0)

    def test_trackpad_left_click(self):
        data = build_packet(0, 0x01, 0, 0, 0, 0)
        pkt = parse_packet(data)
        self.assertEqual(pkt.flags, 0x01)

    def test_trackpad_right_click(self):
        data = build_packet(0, 0x02, 0, 0, 0, 0)
        pkt = parse_packet(data)
        self.assertEqual(pkt.flags, 0x02)

    def test_scroll_mode(self):
        data = build_packet(1, 0, 0, 0, -5, 0)
        pkt = parse_packet(data)
        self.assertEqual(pkt.mode, 1)
        self.assertEqual(pkt.wheel, -5)

    def test_arrow_up(self):
        data = build_packet(2, 0, 0, 0, 0, 0x52)
        pkt = parse_packet(data)
        self.assertEqual(pkt.mode, 2)
        self.assertEqual(pkt.keycode, 0x52)

    def test_arrow_enter(self):
        data = build_packet(2, 0, 0, 0, 0, 0x28)
        pkt = parse_packet(data)
        self.assertEqual(pkt.keycode, 0x28)

    def test_cmd_h_shortcut(self):
        data = build_packet(0, 0x08, 0, 0, 0, 0x0B)
        pkt = parse_packet(data)
        self.assertEqual(pkt.flags, 0x08)  # Left GUI
        self.assertEqual(pkt.keycode, 0x0B)  # H

    def test_cmd_tab_shortcut(self):
        data = build_packet(0, 0x08, 0, 0, 0, 0x2B)
        pkt = parse_packet(data)
        self.assertEqual(pkt.flags, 0x08)
        self.assertEqual(pkt.keycode, 0x2B)

    def test_invalid_mode(self):
        data = struct.pack("<BBbbbB", 3, 0, 0, 0, 0, 0)
        self.assertIsNone(parse_packet(data))

    def test_wrong_size(self):
        self.assertIsNone(parse_packet(b"\x00\x00\x00"))
        self.assertIsNone(parse_packet(b""))
        self.assertIsNone(parse_packet(b"\x00" * 7))

    def test_boundary_values(self):
        data = build_packet(0, 0xFF, 127, -128, 127, 0xFF)
        pkt = parse_packet(data)
        self.assertEqual(pkt.dx, 127)
        self.assertEqual(pkt.dy, -128)
        self.assertEqual(pkt.wheel, 127)
        self.assertEqual(pkt.keycode, 0xFF)

    def test_key_release(self):
        data = build_packet(2, 0, 0, 0, 0, 0)
        pkt = parse_packet(data)
        self.assertEqual(pkt.keycode, 0)
        self.assertEqual(pkt.flags, 0)

    def test_packet_size(self):
        data = build_packet(0, 0, 0, 0, 0, 0)
        self.assertEqual(len(data), 6)


class TestBuildPacket(unittest.TestCase):
    def test_roundtrip(self):
        for mode in range(3):
            for dx in (-128, 0, 127):
                for keycode in (0, 0x28, 0xFF):
                    data = build_packet(mode, 0, dx, 0, 0, keycode)
                    pkt = parse_packet(data)
                    self.assertEqual(pkt.mode, mode)
                    self.assertEqual(pkt.dx, dx)
                    self.assertEqual(pkt.keycode, keycode)


if __name__ == "__main__":
    unittest.main()
