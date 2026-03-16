"""BLE HOGP (HID over GATT Profile) server using BlueZ D-Bus API.

Implements a BLE HID peripheral exposing keyboard and mouse input reports
via GATT notifications. Compatible with iOS/iPadOS (iPhone / iPad).

Architecture:
  - GATT D-Bus objects are registered with BlueZ.
  - A GLib main loop running in a daemon thread drives all D-Bus I/O.
  - HID reports are dispatched from any thread (asyncio included) via
    GLib.idle_add(), which is the only GLib-provided thread-safe API.
"""

import logging
import threading
from typing import Optional

import dbus
import dbus.mainloop.glib
import dbus.service
from gi.repository import GLib

from .bt_profile import HID_REPORT_DESCRIPTOR
from .config import REPORT_ID_KEYBOARD, REPORT_ID_MOUSE

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# D-Bus / BlueZ interface name constants
# ---------------------------------------------------------------------------

DBUS_OM_IFACE    = "org.freedesktop.DBus.ObjectManager"
DBUS_PROP_IFACE  = "org.freedesktop.DBus.Properties"
BLUEZ_SERVICE    = "org.bluez"
ADAPTER_IFACE    = "org.bluez.Adapter1"
GATT_MGR_IFACE   = "org.bluez.GattManager1"
GATT_SVC_IFACE   = "org.bluez.GattService1"
GATT_CHR_IFACE   = "org.bluez.GattCharacteristic1"
GATT_DSC_IFACE   = "org.bluez.GattDescriptor1"
LE_ADV_IFACE     = "org.bluez.LEAdvertisement1"
LE_ADV_MGR_IFACE = "org.bluez.LEAdvertisingManager1"

# ---------------------------------------------------------------------------
# GATT UUID constants
# ---------------------------------------------------------------------------

HID_SERVICE_UUID     = "00001812-0000-1000-8000-00805f9b34fb"
DEVINFO_SERVICE_UUID = "0000180a-0000-1000-8000-00805f9b34fb"
BATTERY_SERVICE_UUID = "0000180f-0000-1000-8000-00805f9b34fb"
REPORT_MAP_UUID      = "00002a4b-0000-1000-8000-00805f9b34fb"
HID_INFO_UUID        = "00002a4a-0000-1000-8000-00805f9b34fb"
PROTOCOL_MODE_UUID   = "00002a4e-0000-1000-8000-00805f9b34fb"
HID_CTRL_POINT_UUID  = "00002a4c-0000-1000-8000-00805f9b34fb"
REPORT_UUID          = "00002a4d-0000-1000-8000-00805f9b34fb"
REPORT_REF_UUID      = "00002908-0000-1000-8000-00805f9b34fb"
MANUFACTURER_UUID    = "00002a29-0000-1000-8000-00805f9b34fb"
MODEL_NUM_UUID       = "00002a24-0000-1000-8000-00805f9b34fb"
BATTERY_LEVEL_UUID   = "00002a19-0000-1000-8000-00805f9b34fb"

# Root D-Bus object paths
_APP_PATH = "/com/ipadremote/hid"
_ADV_PATH = "/com/ipadremote/hid/advert"


# ---------------------------------------------------------------------------
# Internal helper: adapter discovery
# ---------------------------------------------------------------------------

def _find_adapter(bus: dbus.SystemBus, adapter_addr: str = "") -> str:
    """Return the D-Bus object path of the first matching BT adapter."""
    obj_mgr = dbus.Interface(
        bus.get_object(BLUEZ_SERVICE, "/"), DBUS_OM_IFACE
    )
    for path, ifaces in obj_mgr.GetManagedObjects().items():
        if ADAPTER_IFACE in ifaces:
            if not adapter_addr or ifaces[ADAPTER_IFACE].get("Address") == adapter_addr:
                return str(path)
    raise RuntimeError("No Bluetooth adapter found")


# ---------------------------------------------------------------------------
# GATT object helpers
# ---------------------------------------------------------------------------

class _GattObject(dbus.service.Object):
    """Mixin: exposes get_path() and a default GetAll() for D-Bus Properties."""

    def get_path(self) -> dbus.ObjectPath:
        return dbus.ObjectPath(self.path)  # type: ignore[attr-defined]

    def get_properties(self) -> dict:
        raise NotImplementedError

    @dbus.service.method(DBUS_PROP_IFACE, in_signature="s", out_signature="a{sv}")
    def GetAll(self, interface: str) -> dict:
        return self.get_properties().get(interface, {})


class _ReportRefDescriptor(_GattObject):
    """Report Reference descriptor (UUID 0x2908) linking a Report char to a report ID."""

    def __init__(self, bus: dbus.SystemBus, index: int,
                 report_id: int, chrc_path: str) -> None:
        self.path = chrc_path + f"/desc{index}"
        self._chrc_path = chrc_path
        # [report_id (1 byte), report_type 0x01 = Input]
        self._value = dbus.Array([dbus.Byte(report_id), dbus.Byte(0x01)], signature="y")
        super().__init__(bus, self.path)

    def get_properties(self) -> dict:
        return {
            GATT_DSC_IFACE: {
                "Characteristic": dbus.ObjectPath(self._chrc_path),
                "UUID":  REPORT_REF_UUID,
                "Flags": dbus.Array(["read"], signature="s"),
                "Value": self._value,
            }
        }

    @dbus.service.method(GATT_DSC_IFACE, in_signature="a{sv}", out_signature="ay")
    def ReadValue(self, options: dict) -> dbus.Array:
        return self._value


class _StaticReadChar(_GattObject):
    """Read-only (optionally also write-without-response) characteristic with fixed value."""

    def __init__(self, bus: dbus.SystemBus, index: int, uuid: str,
                 value: list, flags: list, svc_path: str) -> None:
        self.path = svc_path + f"/char{index}"
        self._uuid = uuid
        self._value = dbus.Array([dbus.Byte(b) for b in value], signature="y")
        self._flags = dbus.Array(flags, signature="s")
        self._svc_path = svc_path
        self.descriptors: list = []
        super().__init__(bus, self.path)

    def get_properties(self) -> dict:
        return {
            GATT_CHR_IFACE: {
                "Service":     dbus.ObjectPath(self._svc_path),
                "UUID":        self._uuid,
                "Flags":       self._flags,
                "Descriptors": dbus.Array([], signature="o"),
            }
        }

    @dbus.service.method(GATT_CHR_IFACE, in_signature="a{sv}", out_signature="ay")
    def ReadValue(self, options: dict) -> dbus.Array:
        return self._value

    @dbus.service.method(GATT_CHR_IFACE, in_signature="aya{sv}")
    def WriteValue(self, value: list, options: dict) -> None:
        self._value = dbus.Array([dbus.Byte(b) for b in value], signature="y")


class _WriteOnlyChar(_GattObject):
    """Write-without-response characteristic (e.g. HID Control Point)."""

    def __init__(self, bus: dbus.SystemBus, index: int, uuid: str, svc_path: str) -> None:
        self.path = svc_path + f"/char{index}"
        self._uuid = uuid
        self._svc_path = svc_path
        self.descriptors: list = []
        super().__init__(bus, self.path)

    def get_properties(self) -> dict:
        return {
            GATT_CHR_IFACE: {
                "Service": dbus.ObjectPath(self._svc_path),
                "UUID":    self._uuid,
                "Flags":   dbus.Array(["write-without-response"], signature="s"),
                "Descriptors": dbus.Array([], signature="o"),
            }
        }

    @dbus.service.method(GATT_CHR_IFACE, in_signature="aya{sv}")
    def WriteValue(self, value: list, options: dict) -> None:
        pass  # HID Control Point writes are intentionally ignored


class ReportCharacteristic(_GattObject):
    """
    HID Report characteristic (UUID 0x2A4D) with notifications.

    Handles either the keyboard report (8-byte payload, report ID 1) or the
    mouse report (4-byte payload, report ID 2).  iOS requires both
    ``encrypt-read`` and ``encrypt-notify`` flags for HOGP to function.
    """

    def __init__(self, bus: dbus.SystemBus, index: int,
                 report_id: int, payload_len: int, svc_path: str) -> None:
        self.path = svc_path + f"/char{index}"
        self._report_id = report_id
        self._value: list = [dbus.Byte(0)] * payload_len
        self._notifying = False
        self._svc_path = svc_path
        self.descriptors: list[_ReportRefDescriptor] = []
        super().__init__(bus, self.path)

    def get_properties(self) -> dict:
        return {
            GATT_CHR_IFACE: {
                "Service": dbus.ObjectPath(self._svc_path),
                "UUID":    REPORT_UUID,
                "Flags":   dbus.Array(
                    ["read", "notify", "encrypt-read", "encrypt-notify"],
                    signature="s",
                ),
                "Descriptors": dbus.Array(
                    [d.get_path() for d in self.descriptors], signature="o"
                ),
            }
        }

    @dbus.service.method(GATT_CHR_IFACE, in_signature="a{sv}", out_signature="ay")
    def ReadValue(self, options: dict) -> dbus.Array:
        return dbus.Array(self._value, signature="y")

    @dbus.service.method(GATT_CHR_IFACE)
    def StartNotify(self) -> None:
        self._notifying = True
        logger.debug("Report ID %d: notify started", self._report_id)

    @dbus.service.method(GATT_CHR_IFACE)
    def StopNotify(self) -> None:
        self._notifying = False
        logger.debug("Report ID %d: notify stopped", self._report_id)

    @dbus.service.signal(DBUS_PROP_IFACE, signature="sa{sv}as")
    def PropertiesChanged(self, interface: str, changed: dict, invalidated: list) -> None:
        pass  # dbus-python emits this as a D-Bus signal automatically

    def do_notify(self, payload: bytes) -> bool:
        """
        Emit a PropertiesChanged signal carrying the new report value.

        Must be called from the GLib main loop thread (via GLib.idle_add).
        Returns False so that GLib.idle_add does not reschedule it.
        """
        if self._notifying:
            self._value = [dbus.Byte(b) for b in payload]
            self.PropertiesChanged(
                GATT_CHR_IFACE,
                {"Value": dbus.Array(self._value, signature="y")},
                dbus.Array([], signature="s"),
            )
        return False


# ---------------------------------------------------------------------------
# GATT Service
# ---------------------------------------------------------------------------

class _Service(_GattObject):
    """A GATT service containing an ordered list of characteristics."""

    def __init__(self, bus: dbus.SystemBus, index: int,
                 uuid: str, primary: bool, app_path: str) -> None:
        self.path = app_path + f"/service{index}"
        self._uuid = uuid
        self._primary = primary
        self.characteristics: list[_GattObject] = []
        super().__init__(bus, self.path)

    def get_properties(self) -> dict:
        return {
            GATT_SVC_IFACE: {
                "UUID":            self._uuid,
                "Primary":         dbus.Boolean(self._primary),
                "Characteristics": dbus.Array(
                    [c.get_path() for c in self.characteristics], signature="o"
                ),
            }
        }


# ---------------------------------------------------------------------------
# GATT Application (ObjectManager root)
# ---------------------------------------------------------------------------

class _Application(dbus.service.Object):
    """
    BlueZ GATT Application.

    Implements ``org.freedesktop.DBus.ObjectManager.GetManagedObjects`` to
    return the full tree of services, characteristics, and descriptors.
    """

    def __init__(self, bus: dbus.SystemBus) -> None:
        super().__init__(bus, _APP_PATH)
        self._services: list[_Service] = []

    def get_path(self) -> dbus.ObjectPath:
        return dbus.ObjectPath(_APP_PATH)

    def add_service(self, svc: _Service) -> None:
        self._services.append(svc)

    @dbus.service.method(DBUS_OM_IFACE, out_signature="a{oa{sa{sv}}}")
    def GetManagedObjects(self) -> dict:
        result: dict = {}
        for svc in self._services:
            result[svc.get_path()] = svc.get_properties()
            for chrc in svc.characteristics:
                result[chrc.get_path()] = chrc.get_properties()
                if hasattr(chrc, "descriptors"):
                    for desc in chrc.descriptors:
                        result[desc.get_path()] = desc.get_properties()
        return result


# ---------------------------------------------------------------------------
# BLE Advertisement
# ---------------------------------------------------------------------------

class _Advertisement(dbus.service.Object):
    """BLE peripheral advertisement broadcasting the HID service UUID."""

    def __init__(self, bus: dbus.SystemBus) -> None:
        super().__init__(bus, _ADV_PATH)

    @dbus.service.method(DBUS_PROP_IFACE, in_signature="s", out_signature="a{sv}")
    def GetAll(self, interface: str) -> dict:
        if interface != LE_ADV_IFACE:
            raise dbus.exceptions.DBusException(
                "org.freedesktop.DBus.Error.InvalidArgs",
                f"Unknown interface: {interface}",
            )
        return {
            "Type":         dbus.String("peripheral"),
            "ServiceUUIDs": dbus.Array([HID_SERVICE_UUID], signature="s"),
            # 0x03C1 = Keyboard appearance; recognised by iOS
            "Appearance":   dbus.UInt16(0x03C1),
            "LocalName":    dbus.String("iPad Remote"),
            "Includes":     dbus.Array(["tx-power"], signature="s"),
        }

    @dbus.service.method(LE_ADV_IFACE)
    def Release(self) -> None:
        logger.info("BLE advertisement released by BlueZ")


# ---------------------------------------------------------------------------
# Public server class
# ---------------------------------------------------------------------------

class BleHIDServer:
    """
    BLE HID peripheral (HOGP) for iPhone / iPad.

    Call ``start()`` once to register GATT services and begin advertising.
    Then call ``send_report()`` from any thread (including asyncio tasks) to
    deliver keyboard and mouse input reports.

    The send_report() wire format is identical to BtHIDServer so that the
    BleKeyboardHID / BleMouseHID wrappers can be drop-in replacements
    for BtKeyboardHID / BtMouseHID.
    """

    def __init__(self, adapter_addr: str = "") -> None:
        self._adapter_addr = adapter_addr
        self._keyboard_char: Optional[ReportCharacteristic] = None
        self._mouse_char:    Optional[ReportCharacteristic] = None
        self._mainloop: Optional[GLib.MainLoop] = None
        self._started = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self) -> None:
        """
        Register the BLE GATT HID application and start advertising.

        Spawns a daemon thread (``"ble-glib"``) running a GLib main loop to
        process all D-Bus I/O.  This method returns promptly; pairing and
        connection happen asynchronously in that thread.
        """
        # Must be called before the first SystemBus() on this process.
        # Safe to call multiple times (no-op after first install).
        dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
        dbus.mainloop.glib.threads_init()

        bus = dbus.SystemBus()
        adapter_path = _find_adapter(bus, self._adapter_addr)

        self._configure_adapter(bus, adapter_path)

        app = self._build_application(bus)
        kbd_char, mouse_char = self._extract_report_chars(app)

        self._register_application(bus, adapter_path, app)
        self._register_advertisement(bus, adapter_path)

        self._keyboard_char = kbd_char
        self._mouse_char    = mouse_char

        # Start GLib main loop in a dedicated daemon thread.
        self._mainloop = GLib.MainLoop()
        threading.Thread(
            target=self._mainloop.run, daemon=True, name="ble-glib"
        ).start()

        self._started = True
        logger.info("BLE HID server started — device is advertising as 'iPad Remote'")

    def send_report(self, data: bytes) -> None:
        """
        Dispatch a HID input report to the appropriate GATT characteristic.

        ``data`` format: ``b"\\xa1" + bytes([report_id]) + payload``
        (identical to BtHIDServer.send_report).
        """
        if not self._started or len(data) < 3:
            return

        report_id = data[1]
        payload   = bytes(data[2:])

        if report_id == REPORT_ID_KEYBOARD and self._keyboard_char is not None:
            GLib.idle_add(self._keyboard_char.do_notify, payload)
        elif report_id == REPORT_ID_MOUSE and self._mouse_char is not None:
            GLib.idle_add(self._mouse_char.do_notify, payload)

    def is_connected(self) -> bool:
        """Return True once the server has started advertising."""
        return self._started

    def close(self) -> None:
        """Stop the GLib main loop and shut down the BLE server."""
        if self._mainloop is not None and self._mainloop.is_running():
            self._mainloop.quit()
        self._started = False

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _configure_adapter(bus: dbus.SystemBus, adapter_path: str) -> None:
        props = dbus.Interface(
            bus.get_object(BLUEZ_SERVICE, adapter_path), DBUS_PROP_IFACE
        )
        props.Set(ADAPTER_IFACE, "Powered",             dbus.Boolean(True))
        props.Set(ADAPTER_IFACE, "Discoverable",        dbus.Boolean(True))
        props.Set(ADAPTER_IFACE, "DiscoverableTimeout", dbus.UInt32(0))
        props.Set(ADAPTER_IFACE, "Pairable",            dbus.Boolean(True))
        props.Set(ADAPTER_IFACE, "PairableTimeout",     dbus.UInt32(0))

    @staticmethod
    def _build_application(bus: dbus.SystemBus) -> _Application:
        """Construct the full GATT D-Bus object tree and return the Application."""
        app = _Application(bus)

        # ---- HID Service (0x1812, primary) --------------------------------
        hid_svc = _Service(bus, 0, HID_SERVICE_UUID, True, _APP_PATH)

        # char0: Report Map — the combined keyboard+mouse HID descriptor
        report_map_char = _StaticReadChar(
            bus, 0, REPORT_MAP_UUID,
            list(HID_REPORT_DESCRIPTOR),
            ["read"],
            hid_svc.path,
        )

        # char1: HID Information [bcdHID=0x0111, CountryCode=0x00, Flags=0x03]
        # Flags: RemoteWake (0x01) | NormallyConnectable (0x02)
        hid_info_char = _StaticReadChar(
            bus, 1, HID_INFO_UUID,
            [0x11, 0x01, 0x00, 0x03],
            ["read"],
            hid_svc.path,
        )

        # char2: Protocol Mode (report protocol = 0x01; supports write for host)
        proto_mode_char = _StaticReadChar(
            bus, 2, PROTOCOL_MODE_UUID,
            [0x01],
            ["read", "write-without-response"],
            hid_svc.path,
        )

        # char3: HID Control Point (write-only — suspend/exit-suspend)
        ctrl_point_char = _WriteOnlyChar(bus, 3, HID_CTRL_POINT_UUID, hid_svc.path)

        # char4: Keyboard Report (Report ID 1, 8-byte payload)
        kbd_char = ReportCharacteristic(bus, 4, REPORT_ID_KEYBOARD, 8, hid_svc.path)
        kbd_char.descriptors.append(
            _ReportRefDescriptor(bus, 0, REPORT_ID_KEYBOARD, kbd_char.path)
        )

        # char5: Mouse Report (Report ID 2, 4-byte payload)
        mouse_char = ReportCharacteristic(bus, 5, REPORT_ID_MOUSE, 4, hid_svc.path)
        mouse_char.descriptors.append(
            _ReportRefDescriptor(bus, 0, REPORT_ID_MOUSE, mouse_char.path)
        )

        hid_svc.characteristics = [
            report_map_char, hid_info_char, proto_mode_char,
            ctrl_point_char, kbd_char, mouse_char,
        ]
        app.add_service(hid_svc)

        # ---- Device Info Service (0x180A) ---------------------------------
        devinfo_svc = _Service(bus, 1, DEVINFO_SERVICE_UUID, True, _APP_PATH)
        devinfo_svc.characteristics = [
            _StaticReadChar(bus, 0, MANUFACTURER_UUID,
                            list(b"iPad Remote"), ["read"], devinfo_svc.path),
            _StaticReadChar(bus, 1, MODEL_NUM_UUID,
                            list(b"RPi Zero 2W"), ["read"], devinfo_svc.path),
        ]
        app.add_service(devinfo_svc)

        # ---- Battery Service (0x180F) -- iOS shows battery icon for HID ---
        batt_svc = _Service(bus, 2, BATTERY_SERVICE_UUID, True, _APP_PATH)
        batt_svc.characteristics = [
            _StaticReadChar(bus, 0, BATTERY_LEVEL_UUID,
                            [0x64], ["read", "notify"], batt_svc.path),
        ]
        app.add_service(batt_svc)

        return app

    @staticmethod
    def _extract_report_chars(
        app: _Application,
    ) -> "tuple[ReportCharacteristic, ReportCharacteristic]":
        """Pull the keyboard and mouse ReportCharacteristic instances from the app."""
        hid_svc = app._services[0]
        kbd_char   = hid_svc.characteristics[4]
        mouse_char = hid_svc.characteristics[5]
        assert isinstance(kbd_char,   ReportCharacteristic)
        assert isinstance(mouse_char, ReportCharacteristic)
        return kbd_char, mouse_char

    @staticmethod
    def _register_application(
        bus: dbus.SystemBus, adapter_path: str, app: _Application
    ) -> None:
        gatt_mgr = dbus.Interface(
            bus.get_object(BLUEZ_SERVICE, adapter_path), GATT_MGR_IFACE
        )
        gatt_mgr.RegisterApplication(
            app.get_path(),
            {},
            reply_handler=lambda: logger.info("BLE GATT application registered"),
            error_handler=lambda e: logger.error("RegisterApplication failed: %s", e),
        )

    @staticmethod
    def _register_advertisement(
        bus: dbus.SystemBus, adapter_path: str
    ) -> None:
        advert = _Advertisement(bus)
        adv_mgr = dbus.Interface(
            bus.get_object(BLUEZ_SERVICE, adapter_path), LE_ADV_MGR_IFACE
        )
        adv_mgr.RegisterAdvertisement(
            dbus.ObjectPath(_ADV_PATH),
            {},
            reply_handler=lambda: logger.info("BLE advertisement active"),
            error_handler=lambda e: logger.error("RegisterAdvertisement failed: %s", e),
        )
