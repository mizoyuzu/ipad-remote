"""Register Bluetooth HID profile via D-Bus (BlueZ 5).

This registers an SDP record so that remote hosts discover the RPi
as a Bluetooth HID keyboard+mouse combo device and connect to
PSM 0x11 / 0x13.
"""

import logging
import subprocess

import dbus
import dbus.mainloop.glib
import dbus.service

logger = logging.getLogger(__name__)

# BlueZ D-Bus constants
BLUEZ_BUS = "org.bluez"
BLUEZ_PROFILE_MGR = "/org/bluez"
PROFILE_IFACE = "org.bluez.ProfileManager1"
ADAPTER_IFACE = "org.bluez.Adapter1"
PROPS_IFACE = "org.freedesktop.DBus.Properties"

# HID profile UUID
HID_UUID = "00001124-0000-1000-8000-00805f9b34fb"

# Class of Device: 0x0025C0
# Major class: Peripheral (0x0500)
# Minor class: Keyboard+Pointing combo (0x00C0)
# Service class: some bits
_COD_PERIPHERAL_COMBO = 0x0025C0

# Combined HID descriptor (keyboard report ID=1, mouse report ID=2)
# fmt: off
HID_REPORT_DESCRIPTOR = bytes([
    # ---- Keyboard (Report ID 1) ----
    0x05, 0x01,        # Usage Page (Generic Desktop)
    0x09, 0x06,        # Usage (Keyboard)
    0xA1, 0x01,        # Collection (Application)
    0x85, 0x01,        #   Report ID (1)
    0x05, 0x07,        #   Usage Page (Key Codes)
    0x19, 0xE0,        #   Usage Minimum (224)
    0x29, 0xE7,        #   Usage Maximum (231)
    0x15, 0x00,        #   Logical Minimum (0)
    0x25, 0x01,        #   Logical Maximum (1)
    0x75, 0x01,        #   Report Size (1)
    0x95, 0x08,        #   Report Count (8)
    0x81, 0x02,        #   Input (Data, Variable, Absolute)
    0x95, 0x01,        #   Report Count (1)
    0x75, 0x08,        #   Report Size (8)
    0x81, 0x01,        #   Input (Constant) — reserved
    0x95, 0x05,        #   Report Count (5)
    0x75, 0x01,        #   Report Size (1)
    0x05, 0x08,        #   Usage Page (LEDs)
    0x19, 0x01,        #   Usage Minimum (1)
    0x29, 0x05,        #   Usage Maximum (5)
    0x91, 0x02,        #   Output (Data, Variable, Absolute)
    0x95, 0x01,        #   Report Count (1)
    0x75, 0x03,        #   Report Size (3)
    0x91, 0x01,        #   Output (Constant) — padding
    0x95, 0x06,        #   Report Count (6)
    0x75, 0x08,        #   Report Size (8)
    0x15, 0x00,        #   Logical Minimum (0)
    0x25, 0x65,        #   Logical Maximum (101)
    0x05, 0x07,        #   Usage Page (Key Codes)
    0x19, 0x00,        #   Usage Minimum (0)
    0x29, 0x65,        #   Usage Maximum (101)
    0x81, 0x00,        #   Input (Data, Array)
    0xC0,              # End Collection

    # ---- Mouse (Report ID 2) ----
    0x05, 0x01,        # Usage Page (Generic Desktop)
    0x09, 0x02,        # Usage (Mouse)
    0xA1, 0x01,        # Collection (Application)
    0x85, 0x02,        #   Report ID (2)
    0x09, 0x01,        #   Usage (Pointer)
    0xA1, 0x00,        #   Collection (Physical)
    0x05, 0x09,        #     Usage Page (Buttons)
    0x19, 0x01,        #     Usage Minimum (1)
    0x29, 0x03,        #     Usage Maximum (3)
    0x15, 0x00,        #     Logical Minimum (0)
    0x25, 0x01,        #     Logical Maximum (1)
    0x95, 0x03,        #     Report Count (3)
    0x75, 0x01,        #     Report Size (1)
    0x81, 0x02,        #     Input (Data, Variable, Absolute)
    0x95, 0x01,        #     Report Count (1)
    0x75, 0x05,        #     Report Size (5)
    0x81, 0x01,        #     Input (Constant) — padding
    0x05, 0x01,        #     Usage Page (Generic Desktop)
    0x09, 0x30,        #     Usage (X)
    0x09, 0x31,        #     Usage (Y)
    0x09, 0x38,        #     Usage (Wheel)
    0x15, 0x81,        #     Logical Minimum (-127)
    0x25, 0x7F,        #     Logical Maximum (127)
    0x75, 0x08,        #     Report Size (8)
    0x95, 0x03,        #     Report Count (3)
    0x81, 0x06,        #     Input (Data, Variable, Relative)
    0xC0,              #   End Collection
    0xC0,              # End Collection
])
# fmt: on


def _set_adapter_discoverable(bus: dbus.SystemBus, adapter_path: str = "/org/bluez/hci0") -> None:
    """Make the adapter discoverable and pairable."""
    props = dbus.Interface(
        bus.get_object(BLUEZ_BUS, adapter_path), PROPS_IFACE
    )
    props.Set(ADAPTER_IFACE, "Powered", dbus.Boolean(True))
    props.Set(ADAPTER_IFACE, "Discoverable", dbus.Boolean(True))
    props.Set(ADAPTER_IFACE, "DiscoverableTimeout", dbus.UInt32(0))  # forever
    props.Set(ADAPTER_IFACE, "Pairable", dbus.Boolean(True))
    props.Set(ADAPTER_IFACE, "PairableTimeout", dbus.UInt32(0))
    logger.info("Adapter %s: discoverable + pairable", adapter_path)


def _set_device_class() -> None:
    """Set the Bluetooth Class of Device to peripheral (keyboard+mouse combo)."""
    try:
        # Use hciconfig to force CoD — BlueZ D-Bus doesn't expose this well
        subprocess.run(
            ["hciconfig", "hci0", "class", hex(_COD_PERIPHERAL_COMBO)],
            check=True,
            capture_output=True,
        )
        logger.info("Device class set to 0x%06X (peripheral combo)", _COD_PERIPHERAL_COMBO)
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        # Fallback: try bluetoothctl
        logger.warning("hciconfig class failed (%s), trying btmgmt", exc)
        try:
            subprocess.run(
                ["btmgmt", "class", "5", "0xC0"],
                check=True,
                capture_output=True,
            )
        except Exception as exc2:
            logger.error("Could not set device class: %s", exc2)


def register_hid_profile(bus: dbus.SystemBus) -> None:
    """Register the HID SDP profile with BlueZ via D-Bus."""
    profile_mgr = dbus.Interface(
        bus.get_object(BLUEZ_BUS, BLUEZ_PROFILE_MGR), PROFILE_IFACE
    )

    opts = {
        "Role": dbus.String("server"),
        "RequireAuthentication": dbus.Boolean(False),
        "RequireAuthorization": dbus.Boolean(False),
        "AutoConnect": dbus.Boolean(True),
        "ServiceRecord": dbus.String(_build_sdp_record()),
    }

    # Register a dummy profile object path — BlueZ needs it
    profile_path = "/org/bluez/ipad_remote_hid"

    try:
        profile_mgr.RegisterProfile(profile_path, HID_UUID, opts)
        logger.info("HID SDP profile registered")
    except dbus.exceptions.DBusException as exc:
        if "AlreadyExists" in str(exc):
            logger.info("HID profile already registered")
        else:
            raise


def _build_sdp_record() -> str:
    """Build an XML SDP record for Bluetooth HID."""
    desc_hex = " ".join(f"0x{b:02x}" for b in HID_REPORT_DESCRIPTOR)
    desc_len = len(HID_REPORT_DESCRIPTOR)

    return f"""<?xml version="1.0" encoding="UTF-8" ?>
<record>
  <!-- Service class: HID -->
  <attribute id="0x0001">
    <sequence>
      <uuid value="0x1124" />
    </sequence>
  </attribute>

  <!-- Protocol descriptor list: L2CAP (PSM 0x11), HIDP -->
  <attribute id="0x0004">
    <sequence>
      <sequence>
        <uuid value="0x0100" />
        <uint16 value="0x0011" />
      </sequence>
      <sequence>
        <uuid value="0x0011" />
      </sequence>
    </sequence>
  </attribute>

  <!-- Browse group -->
  <attribute id="0x0005">
    <sequence>
      <uuid value="0x1002" />
    </sequence>
  </attribute>

  <!-- Language -->
  <attribute id="0x0006">
    <sequence>
      <uint16 value="0x656E" />
      <uint16 value="0x006A" />
      <uint16 value="0x0100" />
    </sequence>
  </attribute>

  <!-- Additional protocol descriptor (interrupt channel PSM 0x13) -->
  <attribute id="0x000D">
    <sequence>
      <sequence>
        <sequence>
          <uuid value="0x0100" />
          <uint16 value="0x0013" />
        </sequence>
        <sequence>
          <uuid value="0x0011" />
        </sequence>
      </sequence>
    </sequence>
  </attribute>

  <!-- Service name -->
  <attribute id="0x0100">
    <text value="iPad Remote HID" />
  </attribute>

  <!-- Service description -->
  <attribute id="0x0101">
    <text value="Keyboard and Mouse" />
  </attribute>

  <!-- Provider name -->
  <attribute id="0x0102">
    <text value="iPad Remote" />
  </attribute>

  <!-- HID parser version -->
  <attribute id="0x0201">
    <uint16 value="0x0111" />
  </attribute>

  <!-- HID device subclass: combo keyboard+mouse -->
  <attribute id="0x0202">
    <uint8 value="0xC0" />
  </attribute>

  <!-- HID country code -->
  <attribute id="0x0203">
    <uint8 value="0x00" />
  </attribute>

  <!-- HID virtual cable -->
  <attribute id="0x0204">
    <boolean value="true" />
  </attribute>

  <!-- HID reconnect initiate -->
  <attribute id="0x0205">
    <boolean value="true" />
  </attribute>

  <!-- HID descriptor list -->
  <attribute id="0x0206">
    <sequence>
      <sequence>
        <uint8 value="0x22" />
        <text encoding="hex" value="{desc_hex}" />
      </sequence>
    </sequence>
  </attribute>

  <!-- HID LANGID base -->
  <attribute id="0x0207">
    <sequence>
      <sequence>
        <uint16 value="0x0409" />
        <uint16 value="0x0100" />
      </sequence>
    </sequence>
  </attribute>

  <!-- HID battery power -->
  <attribute id="0x0209">
    <boolean value="true" />
  </attribute>

  <!-- HID remote wake -->
  <attribute id="0x020A">
    <boolean value="true" />
  </attribute>

  <!-- HID supervision timeout -->
  <attribute id="0x020C">
    <uint16 value="0x0C80" />
  </attribute>

  <!-- HID normally connectable -->
  <attribute id="0x020D">
    <boolean value="true" />
  </attribute>

  <!-- HID boot device -->
  <attribute id="0x020E">
    <boolean value="true" />
  </attribute>

  <!-- HID profile version -->
  <attribute id="0x020F">
    <uint16 value="0x0100" />
  </attribute>
</record>
"""


def setup_bluetooth() -> dbus.SystemBus:
    """Full Bluetooth HID setup: device class, SDP record, discoverable.

    Returns the D-Bus system bus (keep a reference to prevent GC).
    """
    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
    bus = dbus.SystemBus()

    _set_device_class()
    register_hid_profile(bus)
    _set_adapter_discoverable(bus)

    logger.info("Bluetooth HID setup complete — device is discoverable")
    return bus
