"""BlueZ D-Bus agent that auto-accepts pairing requests.

This eliminates the need to manually type 'yes' in bluetoothctl.
"""

import logging
import os

import dbus
import dbus.service

logger = logging.getLogger(__name__)

AGENT_IFACE = "org.bluez.Agent1"
AGENT_MGR_IFACE = "org.bluez.AgentManager1"
AGENT_PATH = "/org/bluez/ipad_remote_agent"


def _device_path_to_mac(device_path: str) -> str | None:
    # Example: /org/bluez/hci0/dev_AA_BB_CC_DD_EE_FF
    tail = device_path.rsplit("/", 1)[-1]
    if not tail.startswith("dev_"):
        return None
    mac = tail[4:].replace("_", ":").upper()
    if len(mac.split(":")) != 6:
        return None
    return mac


class AutoAcceptAgent(dbus.service.Object):
    """BlueZ agent that auto-accepts all pairing and authorization requests."""

    def __init__(self, bus, object_path):
        super().__init__(bus, object_path)
        allowed = os.environ.get("IPAD_REMOTE_BT_ALLOWED_HOST", "").strip().upper()
        self._allowed_host = allowed or None
        if self._allowed_host:
            logger.info("BT agent policy: allow only host %s", self._allowed_host)
        else:
            logger.info("BT agent policy: allow any host")

    def _is_allowed_device(self, device_path: str) -> bool:
        if self._allowed_host is None:
            return True
        mac = _device_path_to_mac(device_path)
        return mac == self._allowed_host

    @dbus.service.method(AGENT_IFACE, in_signature="", out_signature="")
    def Release(self):
        logger.info("Agent released")

    @dbus.service.method(AGENT_IFACE, in_signature="os", out_signature="")
    def AuthorizeService(self, device, uuid):
        if not self._is_allowed_device(device):
            logger.warning("AuthorizeService: device=%s uuid=%s -> rejected by host policy", device, uuid)
            raise dbus.exceptions.DBusException("org.bluez.Error.Rejected", "Device not allowed")
        logger.info("AuthorizeService: device=%s uuid=%s -> auto-accept", device, uuid)

    @dbus.service.method(AGENT_IFACE, in_signature="o", out_signature="s")
    def RequestPinCode(self, device):
        logger.info("RequestPinCode: device=%s -> '0000'", device)
        return "0000"

    @dbus.service.method(AGENT_IFACE, in_signature="o", out_signature="u")
    def RequestPasskey(self, device):
        logger.info("RequestPasskey: device=%s -> 0", device)
        return dbus.UInt32(0)

    @dbus.service.method(AGENT_IFACE, in_signature="ouq", out_signature="")
    def DisplayPasskey(self, device, passkey, entered):
        if not self._is_allowed_device(device):
            logger.warning("DisplayPasskey: device=%s -> ignored by host policy", device)
            return
        logger.info("DisplayPasskey: device=%s passkey=%06d", device, passkey)

    @dbus.service.method(AGENT_IFACE, in_signature="ou", out_signature="")
    def RequestConfirmation(self, device, passkey):
        if not self._is_allowed_device(device):
            logger.warning("RequestConfirmation: device=%s passkey=%06d -> rejected by host policy", device, passkey)
            raise dbus.exceptions.DBusException("org.bluez.Error.Rejected", "Device not allowed")
        logger.info("RequestConfirmation: device=%s passkey=%06d -> auto-confirm", device, passkey)

    @dbus.service.method(AGENT_IFACE, in_signature="o", out_signature="")
    def RequestAuthorization(self, device):
        if not self._is_allowed_device(device):
            logger.warning("RequestAuthorization: device=%s -> rejected by host policy", device)
            raise dbus.exceptions.DBusException("org.bluez.Error.Rejected", "Device not allowed")
        logger.info("RequestAuthorization: device=%s -> auto-authorize", device)

    @dbus.service.method(AGENT_IFACE, in_signature="", out_signature="")
    def Cancel(self):
        logger.info("Agent cancelled")


def register_agent(bus: dbus.SystemBus) -> AutoAcceptAgent:
    """Register the auto-accept agent as the default agent."""
    agent = AutoAcceptAgent(bus, AGENT_PATH)

    agent_mgr = dbus.Interface(
        bus.get_object("org.bluez", "/org/bluez"), AGENT_MGR_IFACE
    )
    agent_mgr.RegisterAgent(AGENT_PATH, "NoInputNoOutput")
    agent_mgr.RequestDefaultAgent(AGENT_PATH)

    logger.info("Auto-accept agent registered as default")
    return agent
