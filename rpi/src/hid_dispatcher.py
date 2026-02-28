"""Routes parsed packets to the appropriate HID device."""

from .config import MODE_ARROW, MODE_SCROLL, MODE_TRACKPAD
from .hid_keyboard import KeyboardHID
from .hid_mouse import MouseHID
from .protocol import Packet


class HIDDispatcher:
    def __init__(self, mouse: MouseHID, keyboard: KeyboardHID):
        self._mouse = mouse
        self._keyboard = keyboard
        self._last_keycode: int = 0

    def dispatch(self, packet: Packet) -> None:
        if packet.mode == MODE_TRACKPAD:
            self._handle_trackpad(packet)
        elif packet.mode == MODE_SCROLL:
            self._handle_scroll(packet)
        elif packet.mode == MODE_ARROW:
            self._handle_arrow(packet)

    def _handle_trackpad(self, p: Packet) -> None:
        # Mouse movement + buttons + optional wheel (2-finger scroll)
        self._mouse.write(p.flags, p.dx, p.dy, p.wheel)

        # Keyboard shortcuts (Home, App Switch) can be sent in trackpad mode
        # When keycode != 0, flags is reinterpreted as keyboard modifier.
        # This works because shortcut packets have dx=0,dy=0 (mouse report is a no-op).
        if p.keycode != 0:
            self._keyboard.write(p.flags, p.keycode)
            self._last_keycode = p.keycode
        elif self._last_keycode != 0:
            self._keyboard.release()
            self._last_keycode = 0

    def _handle_scroll(self, p: Packet) -> None:
        # Scroll-only: wheel value in the wheel field
        self._mouse.write(0, 0, 0, p.wheel)

    def _handle_arrow(self, p: Packet) -> None:
        if p.keycode != 0:
            # flags = modifier bitmap, maps directly to USB HID modifier byte
            self._keyboard.write(p.flags, p.keycode)
            self._last_keycode = p.keycode
        elif self._last_keycode != 0:
            self._keyboard.release()
            self._last_keycode = 0

    def release_all(self) -> None:
        """Release all keys and buttons. Called on mode switch or shutdown."""
        self._mouse.release()
        self._keyboard.release()
        self._last_keycode = 0

    def close(self) -> None:
        self.release_all()
        self._mouse.close()
        self._keyboard.close()
