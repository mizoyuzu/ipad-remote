"""BlueZ D-Bus agent that auto-accepts pairing requests.

This eliminates the need to manually type 'yes' in bluetoothctl.
"""

import logging

import dbus
import dbus.service

logger = logging.getLogger(__name__)

AGENT_IFACE = "org.bluez.Agent1"
AGENT_MGR_IFACE = "org.bluez.AgentManager1"
AGENT_PATH = "/org/bluez/ipad_remote_agent"


class AutoAcceptAgent(dbus.service.Object):
    """BlueZ agent that auto-accepts all pairing and authorization requests."""

    @dbus.service.method(AGENT_IFACE, in_signature="", out_signature="")
    def Release(self):
        logger.info("Agent released")

    @dbus.service.method(AGENT_IFACE, in_signature="os", out_signature="")
    def AuthorizeService(self, device, uuid):
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
        logger.info("DisplayPasskey: device=%s passkey=%06d", device, passkey)

    @dbus.service.method(AGENT_IFACE, in_signature="ou", out_signature="")
    def RequestConfirmation(self, device, passkey):
        logger.info("RequestConfirmation: device=%s passkey=%06d -> auto-confirm", device, passkey)

    @dbus.service.method(AGENT_IFACE, in_signature="o", out_signature="")
    def RequestAuthorization(self, device):
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
