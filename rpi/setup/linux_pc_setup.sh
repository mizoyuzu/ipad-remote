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
echo "【起動方法】"
echo "  cd $RPI_DIR"
echo "  sudo python3 -m src.main --backend bt"
echo ""
echo "【手順】"
echo "  1. 上記コマンドでサービス起動"
echo "  2. iPad の Bluetooth 設定でこのPCとペアリング"
echo "  3. iPhone の ipadremote アプリを起動 → mDNS でPC自動検出"
echo ""
echo "【ログ確認】起動時に journalctl や標準出力でエラーを確認してください"
