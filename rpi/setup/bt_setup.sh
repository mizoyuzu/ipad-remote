#!/bin/bash
# Bluetooth HID setup for Raspberry Pi
# Configures bluetoothd for HID device operation.
# Must be run as root: sudo bash bt_setup.sh
set -euo pipefail

echo "=== Bluetooth HID Setup ==="

if [ "$(id -u)" -ne 0 ]; then
    echo "Error: must run as root (sudo bash bt_setup.sh)"
    exit 1
fi

NEEDS_RESTART=""

# 1. Install Python D-Bus dependencies
echo "Installing Python D-Bus dependencies..."
apt-get update -qq
apt-get install -y -qq python3-dbus python3-gi bluez

# 2. Enable bluetoothd --compat mode (needed for SDP record registration)
BTD_SERVICE="/lib/systemd/system/bluetooth.service"
if ! grep -q -- '--compat' "$BTD_SERVICE" 2>/dev/null; then
    echo "Enabling bluetoothd --compat mode..."
    sed -i 's|^ExecStart=.*bluetoothd.*|ExecStart=/usr/libexec/bluetoothd --compat --noplugin=input|' "$BTD_SERVICE" 2>/dev/null || \
    sed -i 's|^ExecStart=.*bluetoothd.*|ExecStart=/usr/lib/bluetooth/bluetoothd --compat --noplugin=input|' "$BTD_SERVICE"
    NEEDS_RESTART=1
fi

# 3. Disable the input plugin (conflicts with our L2CAP server)
if ! grep -q -- '--noplugin=input' "$BTD_SERVICE" 2>/dev/null; then
    sed -i 's|--compat|--compat --noplugin=input|' "$BTD_SERVICE"
    NEEDS_RESTART=1
fi

# 4. Restart bluetoothd if changed
if [ -n "$NEEDS_RESTART" ]; then
    systemctl daemon-reload
    systemctl restart bluetooth
    echo "bluetoothd restarted with --compat --noplugin=input"
else
    echo "bluetoothd already configured"
fi

# 5. Ensure Bluetooth is powered on
hciconfig hci0 up 2>/dev/null || true
hciconfig hci0 piscan 2>/dev/null || true

echo ""
echo "=== Bluetooth HID setup complete ==="
echo "The HID profile registration is now handled by the Python service."
echo "Start with: python3 -m src.main --backend bt"
