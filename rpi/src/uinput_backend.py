"""uinput backend: injects mouse and keyboard events into the local Linux desktop.

Uses /dev/uinput directly via raw ioctl calls — no third-party libraries required.

Requires /dev/uinput to be writable by the current user.
Grant access with one of:
  sudo chmod a+rw /dev/uinput             (temporary)
  sudo usermod -aG input $USER            (permanent, needs re-login)
  Or configure a udev rule for the 'input' group.
"""

import fcntl
import logging
import struct
import time

logger = logging.getLogger(__name__)

# ── ioctl request codes ────────────────────────────────────────────────────
_UI_SET_EVBIT  = 0x40045564
_UI_SET_KEYBIT = 0x40045565
_UI_SET_RELBIT = 0x40045566
_UI_DEV_SETUP  = 0x405C5503
_UI_DEV_CREATE  = 0x00005501
_UI_DEV_DESTROY = 0x00005502

# ── Linux input event types ────────────────────────────────────────────────
_EV_SYN = 0
_EV_KEY = 1
_EV_REL = 2

_SYN_REPORT = 0

# ── Relative axis codes ────────────────────────────────────────────────────
_REL_X     = 0
_REL_Y     = 1
_REL_WHEEL = 8

# ── Button / key codes ─────────────────────────────────────────────────────
_BTN_LEFT   = 0x110
_BTN_RIGHT  = 0x111
_BTN_MIDDLE = 0x112

# USB HID modifier bits → Linux keycode
_MODIFIER_MAP = {
    0x01: 29,   # LCtrl  → KEY_LEFTCTRL
    0x02: 42,   # LShift → KEY_LEFTSHIFT
    0x04: 56,   # LAlt   → KEY_LEFTALT
    0x08: 125,  # LGUI   → KEY_LEFTMETA
}

# USB HID keycode → Linux keycode (subset used by this project)
_HID_TO_LINUX: dict[int, int] = {
    0x04: 30,   # A
    0x05: 48,   # B
    0x06: 46,   # C
    0x07: 32,   # D
    0x08: 18,   # E
    0x09: 33,   # F
    0x0A: 34,   # G
    0x0B: 35,   # H   ← used for CMD+H (Home)
    0x0C: 23,   # I
    0x0D: 36,   # J
    0x0E: 37,   # K
    0x0F: 38,   # L
    0x10: 50,   # M
    0x11: 49,   # N
    0x12: 24,   # O
    0x13: 25,   # P
    0x14: 16,   # Q
    0x15: 19,   # R
    0x16: 31,   # S
    0x17: 20,   # T
    0x18: 22,   # U
    0x19: 47,   # V
    0x1A: 17,   # W
    0x1B: 45,   # X
    0x1C: 21,   # Y
    0x1D: 44,   # Z
    0x28: 28,   # Enter
    0x29: 1,    # Escape
    0x2A: 14,   # Backspace
    0x2B: 15,   # Tab    ← used for CMD+Tab (App Switch)
    0x2C: 57,   # Space
    0x4F: 106,  # Right Arrow
    0x50: 105,  # Left Arrow
    0x51: 108,  # Down Arrow
    0x52: 103,  # Up Arrow
}

_BUS_VIRTUAL = 0x06

# input_event: timeval(sec:i64 + usec:i64) + type:u16 + code:u16 + value:i32
_EVENT_STRUCT = struct.Struct("=qqHHi")

# uinput_setup: input_id(bus:u16, vendor:u16, product:u16, version:u16) + name[80] + ff_effects_max:u32
_SETUP_STRUCT = struct.Struct("=HHHH80sI")


def _write_event(fd, etype: int, code: int, value: int) -> None:
    t = time.time()
    sec = int(t)
    usec = int((t - sec) * 1_000_000)
    fd.write(_EVENT_STRUCT.pack(sec, usec, etype, code, value))


def _syn(fd) -> None:
    _write_event(fd, _EV_SYN, _SYN_REPORT, 0)


def _create_device(device_path: str, name: str, ev_types: list[int],
                   keybits: list[int], relbits: list[int]):
    fd = open(device_path, "wb", buffering=0)
    fno = fd.fileno()
    for evtype in ev_types:
        fcntl.ioctl(fno, _UI_SET_EVBIT, evtype)
    for kb in keybits:
        fcntl.ioctl(fno, _UI_SET_KEYBIT, kb)
    for rb in relbits:
        fcntl.ioctl(fno, _UI_SET_RELBIT, rb)
    name_bytes = name.encode()[:79] + b"\x00"
    name_padded = name_bytes.ljust(80, b"\x00")
    setup = _SETUP_STRUCT.pack(_BUS_VIRTUAL, 0x1, 0x1, 1, name_padded, 0)
    fcntl.ioctl(fno, _UI_DEV_SETUP, setup)
    fcntl.ioctl(fno, _UI_DEV_CREATE)
    return fd


class UinputMouseHID:
    """Injects mouse events into the local desktop via /dev/uinput."""

    def __init__(self, device_path: str = "/dev/uinput"):
        self._fd = _create_device(
            device_path,
            name="iPad Remote Mouse",
            ev_types=[_EV_SYN, _EV_KEY, _EV_REL],
            keybits=[_BTN_LEFT, _BTN_RIGHT, _BTN_MIDDLE],
            relbits=[_REL_X, _REL_Y, _REL_WHEEL],
        )
        self._buttons = 0
        logger.info("UinputMouseHID: virtual mouse created")

    def write(self, buttons: int, dx: int, dy: int, wheel: int) -> None:
        fd = self._fd
        if dx:
            _write_event(fd, _EV_REL, _REL_X, dx)
        if dy:
            _write_event(fd, _EV_REL, _REL_Y, dy)
        if wheel:
            _write_event(fd, _EV_REL, _REL_WHEEL, wheel)
        new_buttons = buttons & 0x07
        changed = new_buttons ^ self._buttons
        if changed:
            for bit, code in [(0x01, _BTN_LEFT), (0x02, _BTN_RIGHT), (0x04, _BTN_MIDDLE)]:
                if changed & bit:
                    _write_event(fd, _EV_KEY, code, 1 if (new_buttons & bit) else 0)
        self._buttons = new_buttons
        _syn(fd)

    def release(self) -> None:
        if self._buttons:
            self.write(0, 0, 0, 0)

    def close(self) -> None:
        self.release()
        try:
            fcntl.ioctl(self._fd.fileno(), _UI_DEV_DESTROY)
        except OSError:
            pass
        self._fd.close()


class UinputKeyboardHID:
    """Injects keyboard events into the local desktop via /dev/uinput."""

    def __init__(self, device_path: str = "/dev/uinput"):
        # Enable all keys we might use
        keybits = list(_HID_TO_LINUX.values()) + list(_MODIFIER_MAP.values())
        self._fd = _create_device(
            device_path,
            name="iPad Remote Keyboard",
            ev_types=[_EV_SYN, _EV_KEY],
            keybits=keybits,
            relbits=[],
        )
        self._active_keys: list[int] = []
        self._active_mods: list[int] = []
        logger.info("UinputKeyboardHID: virtual keyboard created")

    def write(self, modifier: int, keycode: int) -> None:
        fd = self._fd
        # Press modifier keys
        mods = [lk for bit, lk in _MODIFIER_MAP.items() if modifier & bit]
        for lk in mods:
            _write_event(fd, _EV_KEY, lk, 1)
        # Press main key
        lk = _HID_TO_LINUX.get(keycode)
        if lk is not None:
            _write_event(fd, _EV_KEY, lk, 1)
        _syn(fd)
        self._active_keys = [lk] if lk else []
        self._active_mods = mods

    def release(self) -> None:
        fd = self._fd
        for lk in self._active_keys:
            _write_event(fd, _EV_KEY, lk, 0)
        for lk in self._active_mods:
            _write_event(fd, _EV_KEY, lk, 0)
        if self._active_keys or self._active_mods:
            _syn(fd)
        self._active_keys = []
        self._active_mods = []

    def close(self) -> None:
        self.release()
        try:
            fcntl.ioctl(self._fd.fileno(), _UI_DEV_DESTROY)
        except OSError:
            pass
        self._fd.close()
