"""UDP packet parsing."""

import struct
from dataclasses import dataclass

from .config import PACKET_SIZE


@dataclass(slots=True)
class Packet:
    mode: int       # uint8: 0=trackpad, 1=scroll, 2=arrow
    flags: int      # uint8: mode-dependent bit flags
    dx: int         # int8: horizontal delta
    dy: int         # int8: vertical delta
    wheel: int      # int8: scroll delta
    keycode: int    # uint8: USB HID keycode


# Pre-compiled struct: B=uint8, b=int8
_STRUCT = struct.Struct("<BBbbbB")


def parse_packet(data: bytes) -> Packet | None:
    """Parse 6-byte UDP payload into a Packet. Returns None on invalid data."""
    if len(data) != _STRUCT.size:
        return None
    mode, flags, dx, dy, wheel, keycode = _STRUCT.unpack(data)
    if mode > 2:
        return None
    return Packet(mode, flags, dx, dy, wheel, keycode)


def build_packet(mode: int, flags: int, dx: int, dy: int, wheel: int, keycode: int) -> bytes:
    """Build a 6-byte packet from values. Primarily for testing."""
    return _STRUCT.pack(mode, flags, dx, dy, wheel, keycode)
