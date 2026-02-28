"""Fan-out HID wrappers for running multiple backends simultaneously."""


class FanoutMouseHID:
    """Forwards mouse reports to every backend in insertion order."""

    def __init__(self, *backends) -> None:
        self._backends = backends

    def write(self, buttons: int, dx: int, dy: int, wheel: int) -> None:
        for b in self._backends:
            b.write(buttons, dx, dy, wheel)

    def release(self) -> None:
        for b in self._backends:
            b.release()

    def close(self) -> None:
        for b in self._backends:
            b.close()


class FanoutKeyboardHID:
    """Forwards keyboard reports to every backend in insertion order."""

    def __init__(self, *backends) -> None:
        self._backends = backends

    def write(self, modifier: int, keycode: int) -> None:
        for b in self._backends:
            b.write(modifier, keycode)

    def release(self) -> None:
        for b in self._backends:
            b.release()

    def close(self) -> None:
        for b in self._backends:
            b.close()
