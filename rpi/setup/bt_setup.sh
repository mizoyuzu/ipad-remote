#!/bin/bash
# Bluetooth HID setup (Raspberry Pi and standard Linux desktop)
# Configures bluetoothd for HID device operation via systemd drop-in override.
# Must be run as root: sudo bash bt_setup.sh
set -euo pipefail

echo "=== Bluetooth HID Setup ==="

if [ "$(id -u)" -ne 0 ]; then
    echo "Error: must run as root (sudo bash bt_setup.sh)"
    exit 1
fi

# 1. Install Python D-Bus dependencies
echo "Installing Python D-Bus dependencies..."
apt-get update -qq
apt-get install -y -qq python3-dbus python3-gi bluez

# 2. Detect the actual bluetoothd binary path from the active service
BTD_BIN=$(systemctl cat bluetooth.service 2>/dev/null \
    | grep '^ExecStart=' | head -1 \
    | sed 's/ExecStart=//' | awk '{print $1}')
if [ -z "$BTD_BIN" ]; then
    # Fallback: search common install paths
    for p in /usr/libexec/bluetooth/bluetoothd \
              /usr/lib/bluetooth/bluetoothd \
              /usr/libexec/bluetoothd \
              /usr/sbin/bluetoothd; do
        [ -x "$p" ] && BTD_BIN="$p" && break
    done
fi
if [ -z "$BTD_BIN" ]; then
    echo "Error: could not locate bluetoothd binary"
    exit 1
fi
echo "Found bluetoothd: $BTD_BIN"

# 3. Enable --compat --noplugin=input via systemd drop-in override
#    (avoids modifying the package-managed base unit file)
OVERRIDE_DIR="/etc/systemd/system/bluetooth.service.d"
OVERRIDE_FILE="$OVERRIDE_DIR/10-hid-compat.conf"
mkdir -p "$OVERRIDE_DIR"

CURRENT=""
[ -f "$OVERRIDE_FILE" ] && CURRENT=$(cat "$OVERRIDE_FILE")
DESIRED="[Service]
ExecStart=
ExecStart=$BTD_BIN --compat --noplugin=input"

if [ "$CURRENT" != "$DESIRED" ]; then
    printf '%s\n' "$DESIRED" > "$OVERRIDE_FILE"
    systemctl daemon-reload
    systemctl restart bluetooth
    echo "bluetoothd restarted with --compat --noplugin=input"
else
    echo "bluetoothd already configured"
fi

# 4. Ensure Bluetooth adapter is powered on and discoverable
hciconfig hci0 up 2>/dev/null || true
hciconfig hci0 piscan 2>/dev/null || true

echo ""
echo "=== Bluetooth HID setup complete ==="
echo "The HID profile registration is now handled by the Python service."
echo "Start with: python3 -m src.main --backend bt"
