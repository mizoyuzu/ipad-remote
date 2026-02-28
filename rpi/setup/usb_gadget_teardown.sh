#!/bin/bash
# Tears down the USB gadget configuration.
set -euo pipefail

GADGET_DIR="/sys/kernel/config/usb_gadget/ipad_remote"

if [ ! -d "$GADGET_DIR" ]; then
    echo "No gadget configured."
    exit 0
fi

cd "$GADGET_DIR"

# Deactivate
echo "" > UDC

# Unlink functions from config
rm -f configs/c.1/hid.usb0
rm -f configs/c.1/hid.usb1

# Remove strings and configs
rmdir configs/c.1/strings/0x409
rmdir configs/c.1

# Remove functions
rmdir functions/hid.usb0
rmdir functions/hid.usb1

# Remove device strings
rmdir strings/0x409

# Remove gadget
cd /
rmdir "$GADGET_DIR"

echo "USB gadget torn down."
