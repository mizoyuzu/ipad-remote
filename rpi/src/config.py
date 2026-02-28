"""Central configuration constants."""

UDP_HOST = "0.0.0.0"
UDP_PORT = 5005

HIDG_MOUSE = "/dev/hidg0"
HIDG_KEYBOARD = "/dev/hidg1"

# Bluetooth HID - bind to any adapter by default (all-zeros = BDADDR_ANY)
BT_ADAPTER_ADDR = "00:00:00:00:00:00"

# Bluetooth HID report IDs (must match the HID descriptor in the SDP record)
REPORT_ID_KEYBOARD = 1
REPORT_ID_MOUSE = 2

# Packet constants
MODE_TRACKPAD = 0
MODE_SCROLL = 1
MODE_ARROW = 2

PACKET_SIZE = 6
