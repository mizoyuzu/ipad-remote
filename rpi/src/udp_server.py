"""asyncio UDP server receiving iPhone packets."""

import asyncio
import logging

from .config import PACKET_SIZE
from .hid_dispatcher import HIDDispatcher
from .protocol import parse_packet

logger = logging.getLogger(__name__)


class RemoteProtocol(asyncio.DatagramProtocol):
    """UDP protocol handler. Parses packets and dispatches to HID."""

    def __init__(self, dispatcher: HIDDispatcher):
        self._dispatcher = dispatcher
        self._client_addr: tuple | None = None

    def connection_made(self, transport: asyncio.DatagramTransport) -> None:
        self._transport = transport
        logger.info("UDP server ready")

    def datagram_received(self, data: bytes, addr: tuple) -> None:
        if len(data) != PACKET_SIZE:
            return  # Silently drop invalid-size packets

        packet = parse_packet(data)
        if packet is None:
            return

        if self._client_addr != addr:
            self._client_addr = addr
            logger.info("Client connected from %s", addr)

        self._dispatcher.dispatch(packet)

    def error_received(self, exc: Exception) -> None:
        logger.warning("UDP error: %s", exc)
