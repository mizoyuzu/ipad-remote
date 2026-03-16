#!/bin/bash
# iPad Remote setup for standard Linux desktop (Bluetooth only)
# No USB Gadget or Raspberry Pi specific hardware required.
# Must be run as root: sudo bash linux_pc_setup.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
RPI_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "=== iPad Remote Linux PC Setup (Bluetooth only) ==="

if [ "$(id -u)" -ne 0 ]; then
    echo "Error: must run as root (sudo bash linux_pc_setup.sh)"
    exit 1
fi

# 1. Configure bluetoothd for HID device operation
bash "$SCRIPT_DIR/bt_setup.sh"

# 2. Install Avahi mDNS service so the iOS app can discover this PC
echo "Setting up Avahi mDNS service..."
apt-get install -y -qq avahi-daemon
cp "$SCRIPT_DIR/avahi/ipad-remote.service" /etc/avahi/services/
systemctl restart avahi-daemon
echo "Avahi service registered (_ipadremote._udp on port 5005)"

# 3. Print startup instructions
BT_ADDR=$(hciconfig hci0 2>/dev/null | awk '/BD Address/{print $3}' || echo "(unknown)")
echo ""
echo "=== Setup complete ==="
echo ""
echo "このPCのBluetoothアドレス: $BT_ADDR"
echo ""
echo "【起動・運用コマンド】"
echo "  cd $RPI_DIR"
echo "  sudo bash setup/bt_backend_ctl.sh service bt"
echo "  sudo bash setup/bt_backend_ctl.sh status"
echo ""
echo "【ペアリング手順】"
echo "  1. Mac 側 Bluetooth 画面でこのPCを選択してペアリング"
echo "  2. 必要なら次で手動ペアリング:"
echo "     sudo bash setup/bt_backend_ctl.sh scan 10"
echo "     sudo bash setup/bt_backend_ctl.sh pair AA:BB:CC:DD:EE:FF"
echo ""
echo "【解除・再接続】"
echo "  解除:   sudo bash setup/bt_backend_ctl.sh unpair AA:BB:CC:DD:EE:FF"
echo "  再接続: sudo bash setup/bt_backend_ctl.sh connect AA:BB:CC:DD:EE:FF"
echo ""
echo "【ログ確認】"
echo "  sudo bash setup/bt_backend_ctl.sh logs bt"
