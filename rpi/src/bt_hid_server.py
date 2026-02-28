"""Bluetooth HID L2CAP server (classic BT HID, PSM 0x11 / 0x13)."""

import logging
import socket
import threading

logger = logging.getLogger(__name__)

PSM_HID_CTRL = 0x11  # 17 - HID Control channel
PSM_HID_INTR = 0x13  # 19 - HID Interrupt channel

# Bluetooth HID DATA | INPUT message header
BT_INPUT_HEADER = b"\xa1"

# Use all zeros to bind to any available adapter
BDADDR_ANY = "00:00:00:00:00:00"


class BtHIDServer:
    """
    Bluetooth HID device (peripheral) server using L2CAP SEQPACKET sockets.

    Listens on PSM 0x11 (HID Control) and PSM 0x13 (HID Interrupt).
    The HID host (remote PC / Mac) initiates both connections after pairing.
    HID input reports are then sent by the RPi on the interrupt channel.

    All public methods are thread-safe.
    """

    def __init__(self, adapter_addr: str = BDADDR_ANY) -> None:
        self._lock = threading.Lock()
        self._ctrl_conn: socket.socket | None = None
        self._intr_conn: socket.socket | None = None

        self._ctrl_server = self._make_server(adapter_addr, PSM_HID_CTRL)
        self._intr_server = self._make_server(adapter_addr, PSM_HID_INTR)

        logger.info("BT HID server listening (PSM 0x11 / 0x13)")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _make_server(addr: str, psm: int) -> socket.socket:
        s = socket.socket(
            socket.AF_BLUETOOTH, socket.SOCK_SEQPACKET, socket.BTPROTO_L2CAP
        )
        s.bind((addr, psm))
        s.listen(1)
        return s

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def accept(self) -> None:
        """
        Block until a HID host connects on both channels.
        Intended to be called from a background thread / asyncio.to_thread().

        If a previous connection exists it is closed first.
        """
        logger.info("Waiting for BT HID host to connect...")
        ctrl_conn, ctrl_addr = self._ctrl_server.accept()
        logger.info("BT HID control channel connected from %s", ctrl_addr)
        intr_conn, intr_addr = self._intr_server.accept()
        logger.info("BT HID interrupt channel connected from %s", intr_addr)

        with self._lock:
            self._close_connections_locked()
            self._ctrl_conn = ctrl_conn
            self._intr_conn = intr_conn

    def send_report(self, data: bytes) -> None:
        """
        Send raw bytes on the interrupt channel.
        ``data`` must include the 0xa1 header and report ID.
        Silently drops the report if no host is connected.
        """
        with self._lock:
            conn = self._intr_conn
        if conn is None:
            return
        try:
            conn.send(data)
        except OSError as exc:
            logger.warning("BT HID send failed: %s", exc)
            with self._lock:
                self._intr_conn = None

    def is_connected(self) -> bool:
        with self._lock:
            return self._intr_conn is not None

    def close(self) -> None:
        with self._lock:
            self._close_connections_locked()
        for srv in (self._ctrl_server, self._intr_server):
            try:
                srv.close()
            except OSError:
                pass

    # ------------------------------------------------------------------
    # Private helpers (must be called with self._lock held)
    # ------------------------------------------------------------------

    def _close_connections_locked(self) -> None:
        for conn in (self._ctrl_conn, self._intr_conn):
            if conn is not None:
                try:
                    conn.close()
                except OSError:
                    pass
        self._ctrl_conn = None
        self._intr_conn = None
