"""Dry-run HID backends for demo/testing without physical HID devices.

These backends log all HID events instead of writing to /dev/hidg* or Bluetooth.
"""

import logging

logger = logging.getLogger(__name__)


class DryRunMouseHID:
    """Logs mouse HID reports instead of writing to a device."""

    def write(self, buttons: int, dx: int, dy: int, wheel: int) -> None:
        parts = []
        if buttons & 0x01:
            parts.append("LEFT")
        if buttons & 0x02:
            parts.append("RIGHT")
        if buttons & 0x04:
            parts.append("MIDDLE")
        btn_str = "+".join(parts) if parts else "none"
        logger.info("[MOUSE] buttons=%s dx=%d dy=%d wheel=%d", btn_str, dx, dy, wheel)

    def release(self) -> None:
        logger.info("[MOUSE] release")

    def close(self) -> None:
        pass


class DryRunKeyboardHID:
    """Logs keyboard HID reports instead of writing to a device."""

    _MODIFIER_NAMES = {0x01: "LCtrl", 0x02: "LShift", 0x04: "LAlt", 0x08: "LGUI"}
    _KEY_NAMES = {
        0x28: "Enter", 0x4F: "Right", 0x50: "Left", 0x51: "Down", 0x52: "Up",
        0x0B: "H", 0x2B: "Tab",
    }

    def write(self, modifier: int, keycode: int) -> None:
        mods = [name for bit, name in self._MODIFIER_NAMES.items() if modifier & bit]
        key = self._KEY_NAMES.get(keycode, f"0x{keycode:02X}")
        mod_str = "+".join(mods) if mods else "none"
        logger.info("[KEYBOARD] modifier=%s key=%s", mod_str, key)

    def release(self) -> None:
        logger.info("[KEYBOARD] release")

    def close(self) -> None:
        pass
