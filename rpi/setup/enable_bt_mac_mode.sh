#!/bin/bash
# Enable iPhone -> Raspberry Pi -> Bluetooth HID -> Mac mode
# Usage: sudo bash enable_bt_mac_mode.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

if [ "$(id -u)" -ne 0 ]; then
    echo "Error: must run as root (sudo bash enable_bt_mac_mode.sh)"
    exit 1
fi

echo "=== Configure Bluetooth HID stack ==="
bash "$SCRIPT_DIR/bt_setup.sh"

echo "=== Install BT-only systemd service ==="
cp "$SCRIPT_DIR/ipad-remote-bt.service" /etc/systemd/system/
systemctl daemon-reload

if systemctl is-enabled --quiet ipad-remote.service; then
    systemctl disable --now ipad-remote.service || true
fi

systemctl enable --now ipad-remote-bt.service

echo ""
echo "BT Mac mode enabled."
echo "Check logs with: sudo journalctl -u ipad-remote-bt -f"
echo "Pair on macOS: Settings > Bluetooth > select Raspberry Pi 'iPad Remote HID'."
