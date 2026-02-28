"""Entry point for the iPad Remote RPi service."""

import argparse
import asyncio
import logging
import signal

from .config import BT_ADAPTER_ADDR, HIDG_KEYBOARD, HIDG_MOUSE, UDP_HOST, UDP_PORT
from .hid_dispatcher import HIDDispatcher
from .hid_fanout import FanoutKeyboardHID, FanoutMouseHID
from .hid_keyboard import KeyboardHID
from .hid_mouse import MouseHID
from .udp_server import RemoteProtocol

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="iPad Remote HID service")
    parser.add_argument(
        "--backend",
        choices=["usb", "bt", "both"],
        default="usb",
        help="HID output backend: usb (default), bt (Bluetooth L2CAP), or both",
    )
    return parser.parse_args()


async def _bt_accept_loop(bt_server) -> None:
    """Continuously accept new BT HID host connections in the background."""
    while True:
        try:
            await asyncio.to_thread(bt_server.accept)
        except asyncio.CancelledError:
            return
        except Exception as exc:
            logger.warning("BT accept error: %s", exc)
            await asyncio.sleep(1)


async def main() -> None:
    args = _parse_args()

    bt_server = None
    bt_accept_task = None

    if args.backend in ("bt", "both"):
        from .bt_hid_server import BtHIDServer
        from .bt_keyboard import BtKeyboardHID
        from .bt_mouse import BtMouseHID

        bt_server = BtHIDServer(BT_ADAPTER_ADDR)
        bt_accept_task = asyncio.create_task(_bt_accept_loop(bt_server))

    if args.backend == "usb":
        mouse = MouseHID(HIDG_MOUSE)
        keyboard = KeyboardHID(HIDG_KEYBOARD)
    elif args.backend == "bt":
        mouse = BtMouseHID(bt_server)
        keyboard = BtKeyboardHID(bt_server)
    else:  # both
        mouse = FanoutMouseHID(MouseHID(HIDG_MOUSE), BtMouseHID(bt_server))
        keyboard = FanoutKeyboardHID(KeyboardHID(HIDG_KEYBOARD), BtKeyboardHID(bt_server))

    dispatcher = HIDDispatcher(mouse, keyboard)

    loop = asyncio.get_running_loop()
    transport, _protocol = await loop.create_datagram_endpoint(
        lambda: RemoteProtocol(dispatcher),
        local_addr=(UDP_HOST, UDP_PORT),
    )

    logger.info("Listening on %s:%d (backend: %s)", UDP_HOST, UDP_PORT, args.backend)

    stop = asyncio.Event()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set)

    await stop.wait()

    logger.info("Shutting down...")
    transport.close()
    dispatcher.close()

    if bt_accept_task is not None:
        bt_accept_task.cancel()
    if bt_server is not None:
        bt_server.close()


if __name__ == "__main__":
    asyncio.run(main())
