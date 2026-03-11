"""Web demo server: HTTP (static files) + WebSocket (real-time control & visualization).

Browser connects via WebSocket, sends input events as JSON, receives HID event
notifications back for real-time visualization.

WebSocket message formats
--------------------------
Browser → Server (input):
    {"type": "trackpad", "dx": int, "dy": int}
    {"type": "click", "button": "left"|"right"|"middle"}
    {"type": "scroll", "amount": int}
    {"type": "arrow", "key": "up"|"down"|"left"|"right"|"enter"}
    {"type": "shortcut", "action": "home"|"appswitch"}

Server → Browser (feedback):
    {"type": "event", "mode": int, "flags": int, "dx": int, "dy": int,
     "wheel": int, "keycode": int, "description": str}
    {"type": "error", "message": str}
"""

import asyncio
import json
import logging
import pathlib

import tornado.web
import tornado.websocket

from .config import MODE_ARROW, MODE_SCROLL, MODE_TRACKPAD
from .hid_dispatcher import HIDDispatcher
from .protocol import Packet

logger = logging.getLogger(__name__)

# USB HID key codes (same as protocol.md)
_KEY_UP = 0x52
_KEY_DOWN = 0x51
_KEY_LEFT = 0x50
_KEY_RIGHT = 0x4F
_KEY_ENTER = 0x28
_KEY_H = 0x0B
_KEY_TAB = 0x2B
_MOD_GUI = 0x08

_WEB_DIR = pathlib.Path(__file__).parent.parent / "web"

# Global set of connected WebSocket clients (shared across handler instances)
_ws_clients: set["WebDemoSocket"] = set()


async def _broadcast(msg: dict) -> None:
    """Send JSON message to all connected WebSocket clients."""
    if not _ws_clients:
        return
    data = json.dumps(msg)
    for ws in list(_ws_clients):
        try:
            await ws.write_message(data)
        except tornado.websocket.WebSocketClosedError:
            pass


def _dispatch_and_notify(dispatcher: HIDDispatcher, packet: Packet, description: str) -> None:
    """Dispatch a packet and schedule a WebSocket broadcast."""
    dispatcher.dispatch(packet)
    asyncio.get_event_loop().create_task(
        _broadcast({
            "type": "event",
            "mode": packet.mode,
            "flags": packet.flags,
            "dx": packet.dx,
            "dy": packet.dy,
            "wheel": packet.wheel,
            "keycode": packet.keycode,
            "description": description,
        })
    )


class WebDemoSocket(tornado.websocket.WebSocketHandler):
    """WebSocket handler — one instance per browser connection."""

    def initialize(self, dispatcher: HIDDispatcher) -> None:
        self._dispatcher = dispatcher

    def check_origin(self, origin: str) -> bool:
        return True  # Allow all origins for local demo

    def open(self) -> None:
        _ws_clients.add(self)
        logger.info("WebSocket client connected from %s", self.request.remote_ip)

    def on_close(self) -> None:
        _ws_clients.discard(self)
        logger.info("WebSocket client disconnected")

    async def on_message(self, raw: str) -> None:  # type: ignore[override]
        try:
            msg = json.loads(raw)
        except json.JSONDecodeError:
            return

        t = msg.get("type")

        if t == "trackpad":
            dx = max(-128, min(127, int(msg.get("dx", 0))))
            dy = max(-128, min(127, int(msg.get("dy", 0))))
            packet = Packet(MODE_TRACKPAD, 0, dx, dy, 0, 0)
            _dispatch_and_notify(self._dispatcher, packet, f"Mouse move dx={dx} dy={dy}")

        elif t == "click":
            button = msg.get("button", "left")
            flag = {"left": 0x01, "right": 0x02, "middle": 0x04}.get(button, 0x01)
            press = Packet(MODE_TRACKPAD, flag, 0, 0, 0, 0)
            _dispatch_and_notify(self._dispatcher, press, f"Mouse {button} click")
            await asyncio.sleep(0.05)
            release = Packet(MODE_TRACKPAD, 0, 0, 0, 0, 0)
            _dispatch_and_notify(self._dispatcher, release, f"Mouse {button} release")

        elif t == "scroll":
            amount = max(-128, min(127, int(msg.get("amount", 0))))
            packet = Packet(MODE_SCROLL, 0, 0, 0, amount, 0)
            _dispatch_and_notify(self._dispatcher, packet, f"Scroll amount={amount}")

        elif t == "arrow":
            key = msg.get("key", "up")
            keycode = {
                "up": _KEY_UP, "down": _KEY_DOWN,
                "left": _KEY_LEFT, "right": _KEY_RIGHT,
                "enter": _KEY_ENTER,
            }.get(key, _KEY_UP)
            key_name = key.capitalize()
            press = Packet(MODE_ARROW, 0, 0, 0, 0, keycode)
            _dispatch_and_notify(self._dispatcher, press, f"Key {key_name}")
            await asyncio.sleep(0.05)
            release = Packet(MODE_ARROW, 0, 0, 0, 0, 0)
            _dispatch_and_notify(self._dispatcher, release, f"Key {key_name} release")

        elif t == "shortcut":
            action = msg.get("action", "home")
            if action == "home":
                packet = Packet(MODE_TRACKPAD, _MOD_GUI, 0, 0, 0, _KEY_H)
                _dispatch_and_notify(self._dispatcher, packet, "Shortcut: Home (GUI+H)")
            elif action == "appswitch":
                packet = Packet(MODE_TRACKPAD, _MOD_GUI, 0, 0, 0, _KEY_TAB)
                _dispatch_and_notify(self._dispatcher, packet, "Shortcut: App Switch (GUI+Tab)")
            await asyncio.sleep(0.05)
            release = Packet(MODE_TRACKPAD, 0, 0, 0, 0, 0)
            self._dispatcher.dispatch(release)


class IndexHandler(tornado.web.RequestHandler):
    """Serves index.html for the root path."""

    def get(self) -> None:
        self.render(str(_WEB_DIR / "index.html"))


def create_tornado_app(dispatcher: HIDDispatcher) -> tornado.web.Application:
    """Create the Tornado application with HTTP and WebSocket routes."""
    return tornado.web.Application(
        [
            (r"/ws", WebDemoSocket, {"dispatcher": dispatcher}),
            (r"/", IndexHandler),
            (r"/(.*)", tornado.web.StaticFileHandler, {"path": str(_WEB_DIR)}),
        ],
        debug=False,
    )

