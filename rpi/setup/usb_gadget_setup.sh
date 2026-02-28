#!/bin/bash
# USB Composite HID Gadget Setup for Raspberry Pi Zero 2W
# Creates mouse (hidg0) + keyboard (hidg1) endpoints
# Must be run as root.

set -euo pipefail

GADGET_DIR="/sys/kernel/config/usb_gadget/ipad_remote"

# Bail if already configured
if [ -d "$GADGET_DIR" ]; then
    echo "Gadget already configured at $GADGET_DIR"
    exit 0
fi

# Load required kernel modules
modprobe libcomposite

# Create gadget
mkdir -p "$GADGET_DIR"
cd "$GADGET_DIR"

# USB device descriptor
echo 0x1d6b > idVendor   # Linux Foundation
echo 0x0104 > idProduct  # Multifunction Composite Gadget
echo 0x0100 > bcdDevice  # v1.0.0
echo 0x0200 > bcdUSB     # USB 2.0

# Device strings
mkdir -p strings/0x409
echo "fedcba9876543210" > strings/0x409/serialnumber
echo "iPad Remote"       > strings/0x409/manufacturer
echo "Composite HID"     > strings/0x409/product

# Configuration
mkdir -p configs/c.1/strings/0x409
echo "Config 1: Mouse + Keyboard" > configs/c.1/strings/0x409/configuration
echo 250 > configs/c.1/MaxPower  # 250mA

# ---- HID Function 0: Mouse ----
mkdir -p functions/hid.usb0
echo 0 > functions/hid.usb0/protocol       # 0 = none (not boot protocol)
echo 0 > functions/hid.usb0/subclass       # 0 = no subclass
echo 4 > functions/hid.usb0/report_length  # 4-byte mouse reports

# Mouse HID Report Descriptor (52 bytes)
# Buttons(3-bit) + Padding(5-bit) + X(int8) + Y(int8) + Wheel(int8)
echo -ne '\x05\x01\x09\x02\xa1\x01\x09\x01\xa1\x00' \
         '\x05\x09\x19\x01\x29\x03\x15\x00\x25\x01' \
         '\x95\x03\x75\x01\x81\x02\x95\x01\x75\x05' \
         '\x81\x01\x05\x01\x09\x30\x09\x31\x09\x38' \
         '\x15\x81\x25\x7f\x75\x08\x95\x03\x81\x06' \
         '\xc0\xc0' > functions/hid.usb0/report_desc

# ---- HID Function 1: Keyboard ----
mkdir -p functions/hid.usb1
echo 1 > functions/hid.usb1/protocol       # 1 = keyboard
echo 1 > functions/hid.usb1/subclass       # 1 = boot interface
echo 8 > functions/hid.usb1/report_length  # 8-byte keyboard reports

# Keyboard HID Report Descriptor (63 bytes)
# Standard boot keyboard: modifier(1) + reserved(1) + keycodes(6)
echo -ne '\x05\x01\x09\x06\xa1\x01\x05\x07\x19\xe0' \
         '\x29\xe7\x15\x00\x25\x01\x75\x01\x95\x08' \
         '\x81\x02\x95\x01\x75\x08\x81\x01\x95\x05' \
         '\x75\x01\x05\x08\x19\x01\x29\x05\x91\x02' \
         '\x95\x01\x75\x03\x91\x01\x95\x06\x75\x08' \
         '\x15\x00\x25\x65\x05\x07\x19\x00\x29\x65' \
         '\x81\x00\xc0' > functions/hid.usb1/report_desc

# Link functions to configuration
ln -s functions/hid.usb0 configs/c.1/
ln -s functions/hid.usb1 configs/c.1/

# Activate gadget (bind to UDC)
ls /sys/class/udc > UDC

echo "USB gadget configured:"
echo "  Mouse:    /dev/hidg0 (4-byte reports)"
echo "  Keyboard: /dev/hidg1 (8-byte reports)"
